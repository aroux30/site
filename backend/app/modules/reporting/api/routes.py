"""Reporting API routes (admin-guarded).

Endpoints:
- ``GET /admin/reports/{report_type}`` — parameterized report data (JSON).
- ``GET /admin/reports/{report_type}/export.csv`` — same data as a
  UTF-8-BOM, formula-injection-safe CSV download.
- ``/admin/saved-reports`` CRUD + ``/{id}/run`` + ``/{id}/runs[/{run_id}/download]``
  for saved definitions, manual runs, and archived artifacts.

Permission model: ``reports:read`` (data, CSV, runs, downloads) and
``reports:write`` (saved-report CRUD, run-now). Separate from
``analytics:read`` so dashboard consumers are untouched.
"""

from __future__ import annotations

import uuid
from datetime import date
from pathlib import Path

import structlog
from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.settings import get_settings
from app.core.database.session import get_db
from app.core.exceptions.handlers import NotFoundError, ValidationError
from app.core.security.dependencies import RequirePermissions, get_current_user_id
from app.modules.reporting.application import saved_report_service
from app.modules.reporting.application.csv_builder import build_csv_bytes
from app.modules.reporting.application.report_service import (
    ReportResult,
    generate_report,
)
from app.modules.reporting.domain.models import ReportRun, ReportType
from app.modules.reporting.schemas.reporting import (
    ReportColumnSchema,
    ReportResponse,
    ReportRunListResponse,
    ReportRunResponse,
    SavedReportCreate,
    SavedReportListResponse,
    SavedReportResponse,
    SavedReportUpdate,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

REPORT_TYPES = tuple(t.value for t in ReportType)

# Admin-only surface: mounted directly under the API prefix as
# ``admin_router`` (see api/__init__.py), producing /api/v1/admin/reports/*
# and /api/v1/admin/saved-reports/*.
router = APIRouter(prefix="/admin")

# Empty public router — the registry in main.py requires a module-level
# ``router`` attribute on every registered module; reporting has no
# customer-facing endpoints, so this deliberately mounts nothing.
public_router = APIRouter()

_require_read = Depends(RequirePermissions("reports:read"))
_require_write = Depends(RequirePermissions("reports:write"))


def _parse_report_type(report_type: str) -> ReportType:
    try:
        return ReportType(report_type)
    except ValueError:
        raise ValidationError(
            detail="نوع گزارش نامعتبر است؛ مقادیر مجاز: sales، stock، vendor_settlement، tax_vat",
            error_code="INVALID_REPORT_TYPE",
        ) from None


async def _generate(
    db: AsyncSession,
    report_type: str,
    *,
    date_from: date,
    date_to: date,
    group_by: str | None,
    warehouse_id: uuid.UUID | None,
    vendor_id: uuid.UUID | None,
    category_id: uuid.UUID | None,
    low_stock_only: bool,
) -> ReportResult:
    _parse_report_type(report_type)
    return await generate_report(
        db,
        report_type,
        date_from=date_from,
        date_to=date_to,
        group_by=group_by,
        warehouse_id=warehouse_id,
        vendor_id=vendor_id,
        category_id=category_id,
        low_stock_only=low_stock_only,
    )


def _to_run_response(run: ReportRun) -> ReportRunResponse:
    return ReportRunResponse(
        id=run.id,
        saved_report_id=run.saved_report_id,
        status=run.status.value,
        started_at=run.started_at,
        finished_at=run.finished_at,
        error_message=run.error_message,
        row_count=run.row_count,
        delivery_result=run.delivery_result,
        has_csv=bool(run.artifact_path),
        has_html=bool(run.html_path),
    )


# ── Parameterized reports ─────────────────────────────────────────────────


@router.get(
    "/reports/{report_type}",
    response_model=ReportResponse,
    summary="Parameterized admin report (sales/stock/vendor_settlement/tax_vat)",
    dependencies=[_require_read],
)
async def get_report(
    report_type: str,
    date_from: date = Query(..., alias="from", description="ISO start date (required)"),
    date_to: date = Query(..., alias="to", description="ISO end date (required)"),
    group_by: str | None = Query(None),
    warehouse_id: uuid.UUID | None = Query(None),
    vendor_id: uuid.UUID | None = Query(None),
    category_id: uuid.UUID | None = Query(None),
    low_stock_only: bool = Query(False),
    db: AsyncSession = Depends(get_db),
) -> ReportResponse:
    result = await _generate(
        db,
        report_type,
        date_from=date_from,
        date_to=date_to,
        group_by=group_by,
        warehouse_id=warehouse_id,
        vendor_id=vendor_id,
        category_id=category_id,
        low_stock_only=low_stock_only,
    )
    return ReportResponse(
        report_type=result.report_type,
        date_from=result.date_from,
        date_to=result.date_to,
        group_by=result.group_by,
        columns=[ReportColumnSchema(**vars(c)) for c in result.columns],
        rows=result.rows,
        totals=result.totals,
        notes=result.notes,
    )


@router.get(
    "/reports/{report_type}/export.csv",
    summary="CSV export of a parameterized report (UTF-8 BOM, injection-safe)",
    dependencies=[_require_read],
    responses={200: {"content": {"text/csv": {}}}},
)
async def export_report_csv(
    report_type: str,
    date_from: date = Query(..., alias="from"),
    date_to: date = Query(..., alias="to"),
    group_by: str | None = Query(None),
    warehouse_id: uuid.UUID | None = Query(None),
    vendor_id: uuid.UUID | None = Query(None),
    category_id: uuid.UUID | None = Query(None),
    low_stock_only: bool = Query(False),
    db: AsyncSession = Depends(get_db),
) -> Response:
    result = await _generate(
        db,
        report_type,
        date_from=date_from,
        date_to=date_to,
        group_by=group_by,
        warehouse_id=warehouse_id,
        vendor_id=vendor_id,
        category_id=category_id,
        low_stock_only=low_stock_only,
    )
    csv_bytes = build_csv_bytes(
        [col.label for col in result.columns],
        ([row.get(col.key) for col in result.columns] for row in result.rows),
    )
    filename = (
        f"{report_type}-report-{date_from:%Y%m%d}-{date_to:%Y%m%d}"
        f"-{result.group_by}.csv"
    )
    return Response(
        content=csv_bytes,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── Saved report CRUD ─────────────────────────────────────────────────────


@router.get(
    "/saved-reports",
    response_model=SavedReportListResponse,
    summary="List saved report definitions (admin)",
    dependencies=[_require_read],
)
async def list_saved_reports(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> SavedReportListResponse:
    rows, total = await saved_report_service.list_saved_reports(
        db, page=page, page_size=page_size
    )
    return SavedReportListResponse(
        items=[SavedReportResponse.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/saved-reports",
    response_model=SavedReportResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a saved report definition (admin)",
    dependencies=[_require_write],
)
async def create_saved_report(
    payload: SavedReportCreate,
    db: AsyncSession = Depends(get_db),
    owner_id: uuid.UUID = Depends(get_current_user_id),
) -> SavedReportResponse:
    report_type = _parse_report_type(payload.report_type)
    saved = await saved_report_service.create_saved_report(
        db,
        owner_id=owner_id,
        name=payload.name,
        report_type=report_type,
        filters=payload.filters,
        schedule_cron=payload.schedule_cron,
        delivery_channels=payload.delivery_channels,
        recipients=payload.recipients,
        is_active=payload.is_active,
    )
    await db.commit()
    return SavedReportResponse.model_validate(saved)


@router.get(
    "/saved-reports/{saved_report_id}",
    response_model=SavedReportResponse,
    summary="Saved report detail (admin)",
    dependencies=[_require_read],
)
async def get_saved_report(
    saved_report_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> SavedReportResponse:
    saved = await saved_report_service.get_saved_report(db, saved_report_id)
    return SavedReportResponse.model_validate(saved)


@router.patch(
    "/saved-reports/{saved_report_id}",
    response_model=SavedReportResponse,
    summary="Update a saved report definition (admin)",
    dependencies=[_require_write],
)
async def update_saved_report(
    saved_report_id: uuid.UUID,
    payload: SavedReportUpdate,
    db: AsyncSession = Depends(get_db),
) -> SavedReportResponse:
    saved = await saved_report_service.get_saved_report(db, saved_report_id)
    saved = await saved_report_service.update_saved_report(
        db,
        saved,
        name=payload.name,
        filters=payload.filters,
        schedule_cron=(
            payload.schedule_cron
            if "schedule_cron" in payload.model_fields_set
            else ...
        ),
        delivery_channels=payload.delivery_channels,
        recipients=payload.recipients,
        is_active=payload.is_active,
    )
    await db.commit()
    return SavedReportResponse.model_validate(saved)


@router.delete(
    "/saved-reports/{saved_report_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a saved report definition (admin)",
    dependencies=[_require_write],
)
async def delete_saved_report(
    saved_report_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    saved = await saved_report_service.get_saved_report(db, saved_report_id)
    await db.delete(saved)
    await db.commit()


# ── Runs ──────────────────────────────────────────────────────────────────


@router.post(
    "/saved-reports/{saved_report_id}/run",
    response_model=ReportRunResponse,
    summary="Run a saved report now (admin)",
    dependencies=[_require_write],
)
async def run_saved_report(
    saved_report_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> ReportRunResponse:
    run = await saved_report_service.run_saved_report_now(db, saved_report_id)
    await db.commit()
    return _to_run_response(run)


@router.get(
    "/saved-reports/{saved_report_id}/runs",
    response_model=ReportRunListResponse,
    summary="List runs of a saved report (admin)",
    dependencies=[_require_read],
)
async def list_saved_report_runs(
    saved_report_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> ReportRunListResponse:
    await saved_report_service.get_saved_report(db, saved_report_id)
    rows, total = await saved_report_service.list_report_runs(
        db, saved_report_id, page=page, page_size=page_size
    )
    return ReportRunListResponse(
        items=[_to_run_response(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


def _resolve_artifact(path_str: str, suffix: str) -> Path:
    """Resolve a stored artifact path inside the uploads root (traversal-safe)."""
    base_dir = Path(getattr(get_settings(), "UPLOAD_DIR", "media")).resolve()
    file_path = Path(path_str).resolve()
    if not str(file_path).startswith(str(base_dir)) or file_path.suffix != suffix:
        raise NotFoundError("ReportArtifact", detail="فایل خروجی گزارش یافت نشد")
    if not file_path.exists():
        raise NotFoundError("ReportArtifact", detail="فایل خروجی گزارش یافت نشد")
    return file_path


@router.get(
    "/saved-reports/{saved_report_id}/runs/{run_id}/download",
    summary="Download a run's archived CSV (admin)",
    dependencies=[_require_read],
    responses={200: {"content": {"text/csv": {}}}},
)
async def download_run_artifact(
    saved_report_id: uuid.UUID,
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> Response:
    run = await saved_report_service.get_report_run(db, saved_report_id, run_id)
    if not run.artifact_path:
        raise NotFoundError("ReportArtifact", detail="این اجرا خروجی CSV ندارد")
    file_path = _resolve_artifact(run.artifact_path, ".csv")
    return Response(
        content=file_path.read_bytes(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="report-run-{run.id.hex[:12]}.csv"'
        },
    )


@router.get(
    "/saved-reports/{saved_report_id}/runs/{run_id}/download.html",
    summary="Download a run's archived HTML rendering (PDF-deferred fallback)",
    dependencies=[_require_read],
    responses={200: {"content": {"text/html": {}}}},
)
async def download_run_html(
    saved_report_id: uuid.UUID,
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> Response:
    run = await saved_report_service.get_report_run(db, saved_report_id, run_id)
    if not run.html_path:
        raise NotFoundError("ReportArtifact", detail="این اجرا خروجی HTML ندارد")
    file_path = _resolve_artifact(run.html_path, ".html")
    return Response(
        content=file_path.read_bytes(),
        media_type="text/html; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="report-run-{run.id.hex[:12]}.html"'
        },
    )
