"""Saved report definitions: CRUD, scheduling, execution, and delivery.

Scheduling model:

- ``schedule_cron`` is a strict five-field cron (see ``cron.py``) evaluated
  in Asia/Tehran (the Celery app timezone).
- On create/update with a schedule, ``next_run_at`` is computed
  immediately; a Celery beat dispatcher (``tasks.dispatch_due_reports``)
  fires reports whose ``next_run_at`` has passed.
- Execution is **idempotent**: a run row is created with status PENDING and
  claimed via an atomic PENDING→RUNNING transition; a dispatcher tick that
  loses the race (or a re-fired "run now" on an in-flight run) sees the
  existing run and returns it unchanged.

Delivery: recipients are emailed the CSV artifact through the real
notification email service (``email_service.send_email``, which writes an
``EmailDeliveryLog``). When SMTP is not configured the service's
documented mock fallback reports success with a simulated marker — the run
then records ``email: skipped_not_configured`` and completes with
``completed_no_delivery`` so ops can see nothing actually went out.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.settings import get_settings
from app.core.exceptions.handlers import NotFoundError, ValidationError
from app.modules.notifications.application import email_service
from app.modules.reporting.application import cron as cron_util
from app.modules.reporting.application.csv_builder import build_csv_bytes
from app.modules.reporting.application.renderers import HtmlReportRenderer
from app.modules.reporting.application.report_service import (
    ReportResult,
    generate_report,
)
from app.modules.reporting.domain.models import (
    ReportRun,
    ReportRunStatus,
    ReportType,
    SavedReport,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

TZ_TEHRAN = ZoneInfo("Asia/Tehran")

REPORT_TYPE_LABELS: dict[str, str] = {
    "sales": "گزارش فروش",
    "stock": "گزارش موجودی انبار",
    "vendor_settlement": "گزارش تسویه فروشندگان",
    "tax_vat": "گزارش مالیات بر ارزش افزوده",
}

DELIVERY_CHANNELS = ("email", "in_app")

_FILTER_KEYS = (
    "date_from",
    "date_to",
    "group_by",
    "warehouse_id",
    "vendor_id",
    "category_id",
    "low_stock_only",
)


def _artifacts_dir() -> Path:
    settings = get_settings()
    base = Path(getattr(settings, "UPLOAD_DIR", "media")).resolve() / "report-runs"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _parse_iso_date(value: Any, field_name: str) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        raise ValidationError(
            detail=f"تاریخ {field_name} باید به قالب ISO (مثلاً 2026-09-01) باشد",
            error_code="INVALID_DATE",
        ) from None


def _parse_optional_uuid(value: Any, field_name: str) -> uuid.UUID | None:
    if value in (None, ""):
        return None
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError):
        raise ValidationError(
            detail=f"شناسه {field_name} نامعتبر است",
            error_code="INVALID_FILTER",
        ) from None


def _validate_filters(report_type: ReportType, filters: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize a saved-report filters payload."""
    if not isinstance(filters, dict):
        raise ValidationError(
            detail="فیلترهای گزارش باید یک شیء JSON باشد",
            error_code="INVALID_FILTERS",
        )
    unknown = set(filters) - set(_FILTER_KEYS)
    if unknown:
        raise ValidationError(
            detail=f"فیلدهای ناشناخته در فیلتر گزارش: {', '.join(sorted(unknown))}",
            error_code="INVALID_FILTERS",
        )
    if not filters.get("date_from") or not filters.get("date_to"):
        raise ValidationError(
            detail="تعیین بازه تاریخ (date_from و date_to) برای گزارش الزامی است",
            error_code="DATE_RANGE_REQUIRED",
        )
    normalized: dict[str, Any] = {
        "date_from": _parse_iso_date(filters["date_from"], "date_from").isoformat(),
        "date_to": _parse_iso_date(filters["date_to"], "date_to").isoformat(),
    }
    if filters.get("group_by") is not None:
        normalized["group_by"] = str(filters["group_by"])
    for key in ("warehouse_id", "vendor_id", "category_id"):
        parsed = _parse_optional_uuid(filters.get(key), key)
        if parsed is not None:
            normalized[key] = str(parsed)
    if report_type == ReportType.STOCK and filters.get("low_stock_only"):
        normalized["low_stock_only"] = True
    return normalized


def _validate_schedule(schedule_cron: str | None) -> str | None:
    if schedule_cron is None or str(schedule_cron).strip() == "":
        return None
    expression = str(schedule_cron).strip()
    try:
        cron_util.validate_cron(expression)
    except ValueError as exc:
        raise ValidationError(
            detail=str(exc),
            error_code="INVALID_CRON",
        ) from None
    return expression


def _validate_channels(
    channels: list[Any] | None, recipients: list[Any] | None
) -> tuple[list[str], list[str]]:
    normalized_channels: list[str] = []
    for channel in channels or []:
        channel_str = str(channel)
        if channel_str not in DELIVERY_CHANNELS:
            raise ValidationError(
                detail=f"کانال تحویل نامعتبر است: {channel_str} (مجاز: email، in_app)",
                error_code="INVALID_DELIVERY_CHANNEL",
            )
        normalized_channels.append(channel_str)
    normalized_recipients = [str(r).strip() for r in recipients or [] if str(r).strip()]
    if "email" in normalized_channels and not normalized_recipients:
        raise ValidationError(
            detail="برای کانال ایمیل دست‌کم یک گیرنده الزامی است",
            error_code="RECIPIENTS_REQUIRED",
        )
    return normalized_channels, normalized_recipients


def _compute_next_run(
    schedule_cron: str | None, *, now: datetime | None = None
) -> datetime | None:
    if not schedule_cron:
        return None
    reference = now or datetime.now(TZ_TEHRAN)
    return cron_util.next_run_after(reference, schedule_cron)


# ── CRUD ──────────────────────────────────────────────────────────────────


async def create_saved_report(
    db: AsyncSession,
    *,
    owner_id: uuid.UUID,
    name: str,
    report_type: ReportType,
    filters: dict[str, Any],
    schedule_cron: str | None = None,
    delivery_channels: list[Any] | None = None,
    recipients: list[Any] | None = None,
    is_active: bool = True,
) -> SavedReport:
    name = name.strip()
    if not name:
        raise ValidationError(
            detail="نام گزارش نمی‌تواند خالی باشد",
            error_code="NAME_REQUIRED",
        )
    normalized_filters = _validate_filters(report_type, filters)
    cron_expression = _validate_schedule(schedule_cron)
    channels, recipient_list = _validate_channels(delivery_channels, recipients)

    saved = SavedReport(
        owner_id=owner_id,
        name=name,
        report_type=report_type,
        filters=normalized_filters,
        schedule_cron=cron_expression,
        delivery_channels=channels,
        recipients=recipient_list,
        is_active=is_active,
        next_run_at=_compute_next_run(cron_expression) if is_active else None,
    )
    db.add(saved)
    await db.flush()
    await logger.ainfo(
        "saved_report_created",
        saved_report_id=str(saved.id),
        report_type=report_type.value,
        scheduled=bool(cron_expression),
    )
    return saved


async def update_saved_report(
    db: AsyncSession,
    saved: SavedReport,
    *,
    name: str | None = None,
    filters: dict[str, Any] | None = None,
    schedule_cron: str | None | object = ...,  # sentinel: ... = unchanged
    delivery_channels: list[Any] | None = None,
    recipients: list[Any] | None = None,
    is_active: bool | None = None,
) -> SavedReport:
    if name is not None:
        if not name.strip():
            raise ValidationError(
                detail="نام گزارش نمی‌تواند خالی باشد",
                error_code="NAME_REQUIRED",
            )
        saved.name = name.strip()
    if filters is not None:
        saved.filters = _validate_filters(saved.report_type, filters)
    if schedule_cron is not ...:
        saved.schedule_cron = _validate_schedule(schedule_cron)  # type: ignore[arg-type]
    if delivery_channels is not None or recipients is not None:
        channels, recipient_list = _validate_channels(
            delivery_channels if delivery_channels is not None else saved.delivery_channels,
            recipients if recipients is not None else saved.recipients,
        )
        saved.delivery_channels = channels
        saved.recipients = recipient_list
    if is_active is not None:
        saved.is_active = is_active

    saved.next_run_at = (
        _compute_next_run(saved.schedule_cron) if saved.is_active else None
    )
    await db.flush()
    return saved


async def get_saved_report(db: AsyncSession, saved_report_id: uuid.UUID) -> SavedReport:
    saved = await db.get(SavedReport, saved_report_id)
    if saved is None:
        raise NotFoundError("SavedReport", detail="گزارش ذخیره‌شده یافت نشد")
    return saved


async def list_saved_reports(
    db: AsyncSession,
    *,
    owner_id: uuid.UUID | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[SavedReport], int]:
    stmt = select(SavedReport).order_by(SavedReport.created_at.desc())
    count_stmt = select(func.count(SavedReport.id))
    if owner_id is not None:
        stmt = stmt.where(SavedReport.owner_id == owner_id)
        count_stmt = count_stmt.where(SavedReport.owner_id == owner_id)
    total = (await db.execute(count_stmt)).scalar_one()
    rows = (
        await db.execute(
            stmt.offset((max(page, 1) - 1) * page_size).limit(min(page_size, 100))
        )
    ).scalars().all()
    return list(rows), int(total)


# ── Execution ─────────────────────────────────────────────────────────────


def _filters_to_kwargs(filters: dict[str, Any]) -> dict[str, Any]:
    return {
        "date_from": _parse_iso_date(filters["date_from"], "date_from"),
        "date_to": _parse_iso_date(filters["date_to"], "date_to"),
        "group_by": filters.get("group_by"),
        "warehouse_id": _parse_optional_uuid(filters.get("warehouse_id"), "warehouse_id"),
        "vendor_id": _parse_optional_uuid(filters.get("vendor_id"), "vendor_id"),
        "category_id": _parse_optional_uuid(filters.get("category_id"), "category_id"),
        "low_stock_only": bool(filters.get("low_stock_only")),
    }


async def _try_claim_run(db: AsyncSession, run_id: uuid.UUID) -> bool:
    """Atomically claim a PENDING run; False when another worker got there.

    Kept as one helper so unit tests can fake the race by returning False
    without simulating SQLAlchemy update rowcounts.
    """
    result = await db.execute(
        update(ReportRun)
        .where(ReportRun.id == run_id, ReportRun.status == ReportRunStatus.PENDING)
        .values(status=ReportRunStatus.RUNNING, started_at=datetime.now(UTC))
    )
    rowcount = result.rowcount  # type: ignore[attr-defined]
    return bool(rowcount if rowcount is not None else True)


async def _persist_artifacts(run: ReportRun, result: ReportResult, title: str) -> None:
    """Write CSV + HTML artifacts under the uploads/report-runs directory."""
    base = _artifacts_dir()
    csv_bytes = build_csv_bytes(
        [col.label for col in result.columns],
        ([row.get(col.key) for col in result.columns] for row in result.rows),
    )
    csv_path = base / f"{run.id}.csv"
    csv_path.write_bytes(csv_bytes)
    run.artifact_path = str(csv_path)

    html_bytes = HtmlReportRenderer().render(result, title=title)
    html_path = base / f"{run.id}.html"
    html_path.write_bytes(html_bytes)
    run.html_path = str(html_path)


async def _deliver_email(
    db: AsyncSession,
    *,
    saved: SavedReport,
    run: ReportRun,
    title: str,
) -> str:
    """Send the CSV artifact to recipients; returns a delivery outcome tag."""
    config = email_service.get_smtp_config()
    if not config.is_configured:
        await logger.awarning(
            "saved_report_email_skipped_not_configured",
            saved_report_id=str(saved.id),
            run_id=str(run.id),
        )
        return "skipped_not_configured"

    subject = f"{title} — {saved.filters['date_from']} تا {saved.filters['date_to']}"
    text_body = (
        f"{title}\nبازه: {saved.filters['date_from']} تا {saved.filters['date_to']}\n"
        f"تعداد ردیف‌ها: {run.row_count}\nفایل CSV پیوست/بایگانی شد: {run.artifact_path}"
    )
    html_body = (
        f"<h2>{title}</h2>"
        f"<p>بازه: {saved.filters['date_from']} تا {saved.filters['date_to']}</p>"
        f"<p>تعداد ردیف‌ها: {run.row_count}</p>"
        f"<p>خروجی CSV در مسیر بایگانی گزارش ذخیره شد.</p>"
    )
    all_ok = True
    for recipient in saved.recipients:
        success, _log = await email_service.send_email(
            db,
            recipient=recipient,
            subject=subject,
            html_body=html_body,
            text_body=text_body,
            template="saved_report_delivery",
        )
        all_ok = all_ok and success
    return "sent" if all_ok else "failed"


async def execute_saved_report(
    db: AsyncSession,
    saved: SavedReport,
    *,
    trigger: str = "manual",
) -> ReportRun:
    """Generate the report, persist artifacts, and deliver via channels.

    Idempotency: the run row is created PENDING, then claimed by an atomic
    PENDING→RUNNING conditional update. A second dispatcher tick or a
    duplicate "run now" for a run already claimed returns the existing run
    without re-generating artifacts.
    """
    run = ReportRun(
        saved_report_id=saved.id,
        status=ReportRunStatus.PENDING,
        delivery_result={"trigger": trigger},
    )
    db.add(run)
    await db.flush()

    claimed = await _try_claim_run(db, run.id)
    if not claimed:
        # Another worker claimed it first — hand back the run as-is.
        return run
    run.status = ReportRunStatus.RUNNING
    run.started_at = datetime.now(UTC)
    await db.flush()

    type_label = REPORT_TYPE_LABELS.get(
        saved.report_type.value, saved.report_type.value
    )
    title = f"{type_label} — {saved.name}"
    try:
        result = await generate_report(
            db,
            saved.report_type.value,
            **_filters_to_kwargs(saved.filters),
        )
        run.row_count = result.row_count
        await _persist_artifacts(run, result, title)

        delivery: dict[str, Any] = dict(run.delivery_result or {})
        email_requested = "email" in (saved.delivery_channels or [])
        if email_requested:
            delivery["email"] = await _deliver_email(db, saved=saved, run=run, title=title)
        else:
            delivery["email"] = "not_requested"

        run.delivery_result = delivery
        run.finished_at = datetime.now(UTC)
        if email_requested and delivery["email"] in ("skipped_not_configured", "failed"):
            run.status = (
                ReportRunStatus.COMPLETED_NO_DELIVERY
                if delivery["email"] == "skipped_not_configured"
                else ReportRunStatus.FAILED
            )
            if run.status == ReportRunStatus.FAILED:
                run.error_message = "ارسال ایمیل گزارش ناموفق بود"
        else:
            run.status = ReportRunStatus.SUCCEEDED
    except Exception as exc:
        run.status = ReportRunStatus.FAILED
        run.error_message = str(exc)[:1900]
        run.finished_at = datetime.now(UTC)
        await logger.aexception(
            "saved_report_run_failed",
            saved_report_id=str(saved.id),
            run_id=str(run.id),
        )

    saved.last_run_at = run.finished_at or datetime.now(UTC)
    if saved.schedule_cron and saved.is_active:
        saved.next_run_at = _compute_next_run(saved.schedule_cron)
    await db.flush()
    await db.refresh(run)
    await logger.ainfo(
        "saved_report_run_finished",
        saved_report_id=str(saved.id),
        run_id=str(run.id),
        status=run.status.value,
        row_count=run.row_count,
    )
    return run


async def run_saved_report_now(db: AsyncSession, saved_report_id: uuid.UUID) -> ReportRun:
    """Manual "run now" — the same path the scheduler takes."""
    saved = await get_saved_report(db, saved_report_id)
    return await execute_saved_report(db, saved, trigger="manual")


async def list_report_runs(
    db: AsyncSession,
    saved_report_id: uuid.UUID,
    *,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[ReportRun], int]:
    total = (
        await db.execute(
            select(func.count(ReportRun.id)).where(
                ReportRun.saved_report_id == saved_report_id
            )
        )
    ).scalar_one()
    rows = (
        await db.execute(
            select(ReportRun)
            .where(ReportRun.saved_report_id == saved_report_id)
            .order_by(ReportRun.created_at.desc())
            .offset((max(page, 1) - 1) * page_size)
            .limit(min(page_size, 100))
        )
    ).scalars().all()
    return list(rows), int(total)


async def get_report_run(
    db: AsyncSession,
    saved_report_id: uuid.UUID,
    run_id: uuid.UUID,
) -> ReportRun:
    run = await db.get(ReportRun, run_id)
    if run is None or run.saved_report_id != saved_report_id:
        raise NotFoundError("ReportRun", detail="اجرای گزارش یافت نشد")
    return run


async def dispatch_due_reports(db: AsyncSession, *, now: datetime | None = None) -> int:
    """Execute all active scheduled reports whose ``next_run_at`` has passed.

    Called by the Celery beat dispatcher (every minute, Tehran time).
    Returns the number of runs started.
    """
    moment = now or datetime.now(TZ_TEHRAN)
    stmt = (
        select(SavedReport)
        .where(
            SavedReport.is_active.is_(True),
            SavedReport.schedule_cron.is_not(None),
            SavedReport.next_run_at.is_not(None),
            SavedReport.next_run_at <= moment,
        )
        .order_by(SavedReport.next_run_at)
        .limit(50)
    )
    due = list((await db.execute(stmt)).scalars().all())
    started = 0
    for saved in due:
        await execute_saved_report(db, saved, trigger="schedule")
        started += 1
    return started
