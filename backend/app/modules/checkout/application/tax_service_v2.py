"""Tax engine v1 — async, DB-facing service layer.

Loads effective-dated v2 rules and buyer context, delegates the math to the
pure engine in ``tax_engine.py`` (zero I/O there), and persists the immutable
per-order :class:`OrderTaxObservation`.

The legacy :class:`~app.modules.checkout.application.tax_service.TaxService`
stays untouched for existing callers; new orders route here.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import func, select

from app.modules.checkout.application.tax_engine import (
    OrderLineInput,
    OrderTaxResult,
    TaxRuleData,
    calculate_order_tax,
)
from app.modules.checkout.domain.tax_models import (
    OrderTaxObservation,
    TaxRuleScope,
    TaxRuleType,
    TaxRuleV2,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# Seed code of the always-present default VAT rule (migration x6y7z8a9b0c1).
DEFAULT_VAT_RULE_CODE = "IR-VAT-DEFAULT"


# ── Rule loading / mapping ───────────────────────────────────────────────────


def _to_rule_data(rule: TaxRuleV2) -> TaxRuleData:
    return TaxRuleData(
        id=rule.id,
        code=rule.code,
        rule_type=rule.rule_type.value,
        scope=rule.scope.value,
        rate_basis_points=rule.rate_basis_points,
        priority=rule.priority,
        category_id=rule.category_id,
        product_id=rule.product_id,
        is_active=rule.is_active,
        effective_from=rule.effective_from,
        effective_to=rule.effective_to,
        exempt_reason=rule.exempt_reason,
    )


async def load_active_rules(db: AsyncSession) -> list[TaxRuleData]:
    """Load all active v2 rules (the pure engine filters by effective date)."""
    stmt = select(TaxRuleV2).where(TaxRuleV2.is_active.is_(True))
    result = await db.execute(stmt)
    return [_to_rule_data(r) for r in result.scalars().all()]


async def get_default_rule(
    db: AsyncSession, effective_at: datetime | None = None
) -> TaxRuleV2 | None:
    """Return the winning active DEFAULT rule at ``effective_at`` (or None)."""
    now = effective_at or datetime.now(UTC)
    stmt = (
        select(TaxRuleV2)
        .where(
            TaxRuleV2.is_active.is_(True),
            TaxRuleV2.scope == TaxRuleScope.DEFAULT,
        )
        .order_by(TaxRuleV2.priority.desc(), TaxRuleV2.effective_from.desc().nulls_last())
    )
    result = await db.execute(stmt)
    for rule in result.scalars().all():
        if rule.is_effective_at(now):
            return rule
    return None


async def has_active_default_rule(db: AsyncSession) -> bool:
    """Healthcheck invariant: exactly one default rule must always apply."""
    return (await get_default_rule(db)) is not None


# ── Buyer context ────────────────────────────────────────────────────────────


async def resolve_buyer_tax_context(
    db: AsyncSession, user_id: uuid.UUID
) -> dict[str, Any]:
    """Resolve the buyer's B2B flag and tax-exemption certificate reference.

    Reads the additive columns on ``user_profiles`` (is_b2b,
    tax_exemption_certificate_no). Missing profile → retail buyer.
    """
    from app.modules.users.domain.models import UserProfile

    stmt = select(UserProfile).where(UserProfile.user_id == user_id)
    result = await db.execute(stmt)
    profile = result.scalar_one_or_none()
    if profile is None:
        return {"customer_is_b2b": False, "exemption_certificate": None}
    cert = getattr(profile, "tax_exemption_certificate_no", None)
    is_b2b = bool(getattr(profile, "is_b2b", False))
    return {
        "customer_is_b2b": is_b2b,
        # A certificate only counts for actual B2B buyers.
        "exemption_certificate": cert if is_b2b else None,
    }


# ── Order-level calculation (new checkout path) ──────────────────────────────


async def calculate_order_tax_v2(
    db: AsyncSession,
    *,
    lines: list[OrderLineInput],
    user_id: uuid.UUID | None = None,
    customer_is_b2b: bool | None = None,
    exemption_certificate: str | None = None,
    shipping_rial: int = 0,
    subtotal_rial: int = 0,
    discount_rial: int = 0,
    effective_at: datetime | None = None,
) -> OrderTaxResult:
    """Full order tax calculation through the v1 engine.

    Buyer context may be passed explicitly (tests, reseller flow) or resolved
    from ``user_id`` via the profile's additive B2B columns.
    """
    if customer_is_b2b is None and user_id is not None:
        ctx = await resolve_buyer_tax_context(db, user_id)
        customer_is_b2b = ctx["customer_is_b2b"]
        if exemption_certificate is None:
            exemption_certificate = ctx["exemption_certificate"]

    rules = await load_active_rules(db)
    result = calculate_order_tax(
        lines=lines,
        rules=rules,
        shipping_rial=shipping_rial,
        subtotal_rial=subtotal_rial,
        discount_rial=discount_rial,
        customer_is_b2b=bool(customer_is_b2b),
        exemption_certificate=exemption_certificate,
        effective_at=effective_at,
    )

    await logger.ainfo(
        "order_tax_calculated_v2",
        lines=len(result.lines),
        vat_total_rial=result.vat_total_rial,
        withholding_total_rial=result.withholding_total_rial,
        b2b=bool(customer_is_b2b),
    )
    return result


async def persist_tax_observation(
    db: AsyncSession,
    *,
    order_id: uuid.UUID,
    result: OrderTaxResult,
    customer_is_b2b: bool = False,
    exemption_certificate_ref: str | None = None,
    currency: str = "IRR",
) -> OrderTaxObservation:
    """Persist the immutable per-order tax observation (same transaction)."""
    observation = OrderTaxObservation(
        order_id=order_id,
        currency=currency,
        customer_is_b2b=customer_is_b2b,
        exemption_certificate_ref=exemption_certificate_ref,
        lines=[b.to_snapshot_dict() for b in result.lines],
        vat_total_rial=result.vat_total_rial,
        withholding_total_rial=result.withholding_total_rial,
        tax_total_rial=result.tax_total_rial,
        grand_total_rial=result.grand_total_rial,
    )
    db.add(observation)
    await db.flush()
    await logger.ainfo(
        "order_tax_observation_persisted",
        order_id=str(order_id),
        vat_total_rial=result.vat_total_rial,
        withholding_total_rial=result.withholding_total_rial,
    )
    return observation


# ── VAT report aggregation ───────────────────────────────────────────────────

#: Order statuses that count as "posted" for tax reporting. The order's own
#: ``paid_at`` does not exist on the model; payment completion moves the order
#: past PENDING, so everything at or beyond CONFIRMED (minus cancelled /
#: refunded terminal states) is treated as fiscally relevant. Documented in
#: the admin report endpoint.
REPORTABLE_ORDER_STATUSES = (
    "confirmed",
    "processing",
    "packing",
    "shipped",
    "delivered",
    "completed",
)


async def aggregate_vat_report(
    db: AsyncSession,
    *,
    date_from: datetime,
    date_to: datetime,
    group_by: str = "period",  # period | rule | category
) -> list[dict[str, Any]]:
    """Aggregate persisted order tax observations for the VAT report.

    Source: ``order_tax_observations`` joined to ``orders`` filtered to
    reportable (paid-and-beyond) statuses and the requested window. We do NOT
    join invoicing posted invoices: the observation is written at checkout
    for every order, whereas invoice rows exist only for backfilled/posted
    documents — the observation is the single complete source.
    """
    from app.modules.orders.domain.models import Order

    stmt = (
        select(OrderTaxObservation, Order.status, Order.created_at)
        .join(Order, Order.id == OrderTaxObservation.order_id)
        .where(
            Order.created_at >= date_from,
            Order.created_at <= date_to,
            Order.status.in_(REPORTABLE_ORDER_STATUSES),
        )
    )
    result = await db.execute(stmt)
    rows = result.all()

    buckets: dict[str, dict[str, Any]] = {}
    for observation, _status, created_at in rows:
        line_rows = observation.lines or []
        if not line_rows:
            # Header-only observation (shouldn't happen, but stay lossless).
            line_rows = [
                {
                    "rule_code": None,
                    "rule_type": None,
                    "category_id": None,
                    "taxable_amount_rial": 0,
                    "tax_amount_rial": observation.tax_total_rial,
                    "vat_amount_rial": observation.vat_total_rial,
                    "withholding_amount_rial": observation.withholding_total_rial,
                }
            ]
        for line in line_rows:
            if group_by == "rule":
                key = str(line.get("rule_code") or "UNRULED")
            elif group_by == "category":
                key = str(line.get("category_id") or "UNCATEGORIZED")
            else:  # period → YYYY-MM bucket of the order date
                key = created_at.strftime("%Y-%m") if created_at else "UNKNOWN"

            bucket = buckets.setdefault(
                key,
                {
                    "bucket": key,
                    "order_ids": set(),
                    "taxable_total_rial": 0,
                    "vat_total_rial": 0,
                    "withholding_total_rial": 0,
                    "tax_total_rial": 0,
                },
            )
            bucket["order_ids"].add(observation.order_id)
            bucket["taxable_total_rial"] += int(line.get("taxable_amount_rial") or 0)
            bucket["vat_total_rial"] += int(line.get("vat_amount_rial") or 0)
            bucket["withholding_total_rial"] += int(
                line.get("withholding_amount_rial") or 0
            )
            bucket["tax_total_rial"] += int(line.get("tax_amount_rial") or 0)

    report = []
    for key in sorted(buckets):
        b = buckets[key]
        report.append(
            {
                "bucket": b["bucket"],
                "order_count": len(b["order_ids"]),
                "taxable_total_rial": b["taxable_total_rial"],
                "vat_total_rial": b["vat_total_rial"],
                "withholding_total_rial": b["withholding_total_rial"],
                "tax_total_rial": b["tax_total_rial"],
            }
        )
    return report


async def count_active_rules(db: AsyncSession) -> int:
    """Number of active v2 rules (admin list header / healthcheck context)."""
    result = await db.execute(
        select(func.count()).select_from(TaxRuleV2).where(TaxRuleV2.is_active.is_(True))
    )
    return int(result.scalar() or 0)


__all__ = [
    "DEFAULT_VAT_RULE_CODE",
    "REPORTABLE_ORDER_STATUSES",
    "TaxRuleScope",
    "TaxRuleType",
    "TaxRuleV2",
    "OrderTaxObservation",
    "aggregate_vat_report",
    "calculate_order_tax_v2",
    "count_active_rules",
    "get_default_rule",
    "has_active_default_rule",
    "load_active_rules",
    "persist_tax_observation",
    "resolve_buyer_tax_context",
]
