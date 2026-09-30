"""Admin tax API — rule CRUD, VAT report, healthcheck (tax engine v1).

Guarded by ``tax:read`` / ``tax:write`` permissions (RequirePermissions
pattern, same as invoicing).

Immutability contract: a rule that has entered its effective window is
financial history — it may only be deactivated (``is_active=false``), never
edited in place. To "change" an effective rule, create a new effective-dated
row (versioning by insertion); the resolver already prefers the later
``effective_from`` inside a scope bucket. The API enforces this server-side.
"""

from __future__ import annotations

import csv
import io
import uuid
from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.exceptions.handlers import ConflictError, NotFoundError, ValidationError
from app.core.security.dependencies import RequirePermissions
from app.modules.checkout.application import tax_service_v2
from app.modules.checkout.domain.tax_models import (
    TaxRuleScope,
    TaxRuleType,
    TaxRuleV2,
)
from app.modules.checkout.schemas.tax import (
    TaxHealthResponse,
    TaxReportBucket,
    TaxReportResponse,
    TaxRuleCreate,
    TaxRuleListResponse,
    TaxRuleResponse,
    TaxRuleUpdate,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

router = APIRouter(prefix="/admin/tax", tags=["admin-tax"])

_require_read = Depends(RequirePermissions("tax:read"))
_require_write = Depends(RequirePermissions("tax:write"))


# ── Helpers ──────────────────────────────────────────────────────────────────


def _to_response(rule: TaxRuleV2) -> TaxRuleResponse:
    return TaxRuleResponse(
        id=rule.id,
        name=rule.name,
        code=rule.code,
        rule_type=rule.rule_type.value,
        scope=rule.scope.value,
        category_id=rule.category_id,
        product_id=rule.product_id,
        rate_basis_points=rule.rate_basis_points,
        is_active=rule.is_active,
        priority=rule.priority,
        effective_from=rule.effective_from,
        effective_to=rule.effective_to,
        exempt_reason=rule.exempt_reason,
        description=rule.description,
        created_at=rule.created_at,
    )


def _validate_rule_payload(
    rule_type: str,
    scope: str,
    rate_basis_points: int,
    category_id: uuid.UUID | None,
    product_id: uuid.UUID | None,
) -> None:
    if rate_basis_points < 0 or rate_basis_points > 10_000:
        raise ValidationError(
            detail="نرخ مالیات باید بین ۰ تا ۱۰۰۰۰ واحد پایه (۰ تا ۱۰۰٪) باشد",
            error_code="INVALID_RATE",
        )
    if scope == TaxRuleScope.CATEGORY.value and category_id is None:
        raise ValidationError(
            detail="برای قاعده دسته‌بندی، شناسه دسته‌بندی الزامی است",
            error_code="CATEGORY_REQUIRED",
        )
    if scope == TaxRuleScope.PRODUCT.value and product_id is None:
        raise ValidationError(
            detail="برای قاعده کالا، شناسه کالا الزامی است",
            error_code="PRODUCT_REQUIRED",
        )
    if rule_type == TaxRuleType.EXEMPT.value and rate_basis_points != 0:
        raise ValidationError(
            detail="قاعده معافیت باید نرخ صفر داشته باشد",
            error_code="EXEMPT_RATE_MUST_BE_ZERO",
        )


async def _get_rule_or_404(db: AsyncSession, rule_id: uuid.UUID) -> TaxRuleV2:
    rule = await db.get(TaxRuleV2, rule_id)
    if rule is None:
        raise NotFoundError(resource="TaxRuleV2", detail="قاعده مالیاتی یافت نشد")
    return rule


def _is_effective(rule: TaxRuleV2) -> bool:
    """A rule that has entered its effective window is immutable history."""
    now = datetime.now(UTC)
    return rule.effective_from is not None and rule.effective_from <= now


# ── Healthcheck ──────────────────────────────────────────────────────────────


@router.get(
    "/health",
    response_model=TaxHealthResponse,
    summary="Tax engine healthcheck — warns when no default rule is active",
    dependencies=[_require_read],
)
async def tax_health(db: AsyncSession = Depends(get_db)) -> TaxHealthResponse:
    default_rule = await tax_service_v2.get_default_rule(db)
    active_count = await tax_service_v2.count_active_rules(db)
    has_default = default_rule is not None
    warnings: list[str] = []
    if not has_default:
        warnings.append(
            "هیچ قاعده مالیاتی پیش‌فرض فعالی وجود ندارد — سفارش‌های جدید بدون مالیات ثبت می‌شوند"
        )
    return TaxHealthResponse(
        ok=has_default,
        has_active_default_rule=has_default,
        active_rules_count=active_count,
        default_rule_code=default_rule.code if default_rule else None,
        warnings=warnings,
    )


# ── Rules CRUD ───────────────────────────────────────────────────────────────


@router.get(
    "/rules",
    response_model=TaxRuleListResponse,
    summary="List tax rules (admin)",
    dependencies=[_require_read],
)
async def list_rules(
    rule_type: str | None = Query(None),
    scope: str | None = Query(None),
    is_active: bool | None = Query(None),
    category_id: uuid.UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> TaxRuleListResponse:
    stmt = select(TaxRuleV2).order_by(
        TaxRuleV2.scope, TaxRuleV2.priority.desc(), TaxRuleV2.created_at.desc()
    )
    if rule_type:
        stmt = stmt.where(TaxRuleV2.rule_type == TaxRuleType(rule_type))
    if scope:
        stmt = stmt.where(TaxRuleV2.scope == TaxRuleScope(scope))
    if is_active is not None:
        stmt = stmt.where(TaxRuleV2.is_active.is_(is_active))
    if category_id is not None:
        stmt = stmt.where(TaxRuleV2.category_id == category_id)
    result = await db.execute(stmt)
    rules = list(result.scalars().all())
    return TaxRuleListResponse(
        items=[_to_response(r) for r in rules], total=len(rules)
    )


@router.post(
    "/rules",
    response_model=TaxRuleResponse,
    status_code=201,
    summary="Create a tax rule (admin)",
    dependencies=[_require_write],
)
async def create_rule(
    body: TaxRuleCreate,
    db: AsyncSession = Depends(get_db),
) -> TaxRuleResponse:
    _validate_rule_payload(
        body.rule_type, body.scope, body.rate_basis_points,
        body.category_id, body.product_id,
    )
    existing = await db.execute(select(TaxRuleV2).where(TaxRuleV2.code == body.code))
    if existing.scalar_one_or_none() is not None:
        raise ConflictError(
            detail=f"قاعده‌ای با کد «{body.code}» از قبل وجود دارد",
            error_code="DUPLICATE_RULE_CODE",
        )
    rule = TaxRuleV2(
        name=body.name,
        code=body.code,
        rule_type=TaxRuleType(body.rule_type),
        scope=TaxRuleScope(body.scope),
        category_id=body.category_id,
        product_id=body.product_id,
        rate_basis_points=body.rate_basis_points,
        is_active=body.is_active,
        priority=body.priority,
        effective_from=body.effective_from,
        effective_to=body.effective_to,
        exempt_reason=body.exempt_reason,
        description=body.description,
    )
    db.add(rule)
    await db.flush()
    await logger.ainfo("tax_rule_created", code=rule.code, type=rule.rule_type.value)
    return _to_response(rule)


@router.get(
    "/rules/{rule_id}",
    response_model=TaxRuleResponse,
    summary="Get one tax rule (admin)",
    dependencies=[_require_read],
)
async def get_rule(
    rule_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> TaxRuleResponse:
    return _to_response(await _get_rule_or_404(db, rule_id))


@router.patch(
    "/rules/{rule_id}",
    response_model=TaxRuleResponse,
    summary="Update a tax rule (admin) — only before it becomes effective",
    dependencies=[_require_write],
)
async def update_rule(
    rule_id: uuid.UUID,
    body: TaxRuleUpdate,
    db: AsyncSession = Depends(get_db),
) -> TaxRuleResponse:
    """Edit a not-yet-effective rule.

    Once a rule has entered its effective window it is immutable financial
    history: the only allowed change is deactivation (``is_active=false``).
    To revise a live rule, create a new effective-dated row instead.
    """
    rule = await _get_rule_or_404(db, rule_id)
    changes = body.model_dump(exclude_unset=True)
    if not changes:
        return _to_response(rule)

    if _is_effective(rule):
        non_deactivation = {k for k in changes if k != "is_active"}
        if non_deactivation or changes.get("is_active") is not False:
            raise ConflictError(
                detail=(
                    "قاعده مؤثر قابل ویرایش نیست — برای تغییر، قاعده جدیدی با "
                    "تاریخ اثر جدید ایجاد کنید (نسخه‌بندی با درج ردیف جدید)"
                ),
                error_code="RULE_IMMUTABLE_AFTER_EFFECTIVE",
            )

    new_type = changes.get("rule_type", rule.rule_type.value)
    new_scope = changes.get("scope", rule.scope.value)
    new_rate = changes.get("rate_basis_points", rule.rate_basis_points)
    new_category = changes.get("category_id", rule.category_id)
    new_product = changes.get("product_id", rule.product_id)
    _validate_rule_payload(new_type, new_scope, new_rate, new_category, new_product)

    if "code" in changes and changes["code"] != rule.code:
        dup = await db.execute(
            select(TaxRuleV2).where(TaxRuleV2.code == changes["code"])
        )
        if dup.scalar_one_or_none() is not None:
            raise ConflictError(
                detail=f"قاعده‌ای با کد «{changes['code']}» از قبل وجود دارد",
                error_code="DUPLICATE_RULE_CODE",
            )

    for key, value in changes.items():
        if key == "rule_type":
            value = TaxRuleType(value)
        elif key == "scope":
            value = TaxRuleScope(value)
        setattr(rule, key, value)

    await db.flush()
    await logger.ainfo("tax_rule_updated", code=rule.code, fields=sorted(changes))
    return _to_response(rule)


@router.delete(
    "/rules/{rule_id}",
    status_code=204,
    summary="Deactivate a tax rule (admin) — soft delete, history is kept",
    dependencies=[_require_write],
)
async def deactivate_rule(
    rule_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    rule = await _get_rule_or_404(db, rule_id)
    if rule.code == tax_service_v2.DEFAULT_VAT_RULE_CODE and rule.is_active:
        raise ConflictError(
            detail="قاعده پیش‌فرض مالیات بر ارزش افزوده را نمی‌توان غیرفعال کرد",
            error_code="DEFAULT_RULE_REQUIRED",
        )
    rule.is_active = False
    await db.flush()
    await logger.ainfo("tax_rule_deactivated", code=rule.code)


# ── VAT report ───────────────────────────────────────────────────────────────

_CSV_HEADER = [
    "bucket",
    "order_count",
    "taxable_total_rial",
    "vat_total_rial",
    "withholding_total_rial",
    "tax_total_rial",
]


async def _build_report(
    db: AsyncSession,
    date_from: datetime,
    date_to: datetime,
    group_by: str,
) -> list[dict]:
    if date_from > date_to:
        raise ValidationError(
            detail="بازه زمانی نامعتبر است: «از» بعد از «تا» است",
            error_code="INVALID_DATE_RANGE",
        )
    if group_by not in ("period", "rule", "category"):
        raise ValidationError(
            detail="group_by باید یکی از period، rule یا category باشد",
            error_code="INVALID_GROUP_BY",
        )
    return await tax_service_v2.aggregate_vat_report(
        db, date_from=date_from, date_to=date_to, group_by=group_by
    )


@router.get(
    "/report",
    response_model=TaxReportResponse,
    summary="VAT report — aggregated order tax observations (admin)",
    dependencies=[_require_read],
)
async def vat_report(
    date_from: datetime = Query(..., alias="from"),
    date_to: datetime = Query(..., alias="to"),
    group_by: str = Query("period"),
    db: AsyncSession = Depends(get_db),
) -> TaxReportResponse:
    rows = await _build_report(db, date_from, date_to, group_by)
    return TaxReportResponse(
        date_from=date_from,
        date_to=date_to,
        group_by=group_by,
        buckets=[TaxReportBucket(**r) for r in rows],
        vat_total_rial=sum(r["vat_total_rial"] for r in rows),
        withholding_total_rial=sum(r["withholding_total_rial"] for r in rows),
        tax_total_rial=sum(r["tax_total_rial"] for r in rows),
        order_count=sum(r["order_count"] for r in rows),
    )


@router.get(
    "/report.csv",
    summary="VAT report as CSV download (admin)",
    dependencies=[_require_read],
)
async def vat_report_csv(
    date_from: datetime = Query(..., alias="from"),
    date_to: datetime = Query(..., alias="to"),
    group_by: str = Query("period"),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    rows = await _build_report(db, date_from, date_to, group_by)
    buffer = io.StringIO()
    # utf-8-sig BOM so Persian/Excel consumers read the CSV correctly,
    # matching the dataexchange export convention.
    buffer.write("﻿")
    writer = csv.writer(buffer)
    writer.writerow(_CSV_HEADER)
    for r in rows:
        writer.writerow([r[col] for col in _CSV_HEADER])
    buffer.seek(0)
    filename = f"vat-report-{date_from:%Y%m%d}-{date_to:%Y%m%d}-{group_by}.csv"
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
