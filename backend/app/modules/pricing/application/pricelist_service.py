"""Price list application service (Odoo product.pricelist concept, clean-room).

Layered price resolution. The rule order, from most to least specific, is:

1. a *variant-scoped* rule for the buying segment,
2. a *product-scoped* rule for the buying segment,
3. the volume-tier price (Karta ``PriceTier``), and
4. the list price.

All money stays integer Rial; a percentage discount is applied in basis
points and floored, so a fractional Rial never appears.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import and_, or_, select

from app.modules.pricing.domain.models import CustomerSegment, PriceList, PriceListRule

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


async def _load_active_rules(
    db: AsyncSession,
    *,
    segment: CustomerSegment,
    product_id: uuid.UUID,
    variant_id: uuid.UUID | None,
) -> list[tuple[PriceListRule, int]]:
    """Active rules matching this segment and this product/variant.

    Returns ``(rule, list_priority)`` pairs. A rule matches when it names the
    exact variant, or the exact product with no variant scope, or neither
    (a catalog-wide rule for the segment).
    """
    now = datetime.now(UTC)
    scope = or_(
        PriceListRule.variant_id == variant_id,
        and_(PriceListRule.product_id == product_id, PriceListRule.variant_id.is_(None)),
        and_(PriceListRule.product_id.is_(None), PriceListRule.variant_id.is_(None)),
    )
    stmt = (
        select(PriceListRule, PriceList.priority)
        .join(PriceList, PriceList.id == PriceListRule.price_list_id)
        .where(
            PriceList.is_active.is_(True),
            PriceList.segment == segment,
            or_(PriceList.valid_from.is_(None), PriceList.valid_from <= now),
            or_(PriceList.valid_to.is_(None), PriceList.valid_to >= now),
            scope,
        )
        .order_by(PriceList.priority.asc(), PriceListRule.min_quantity.desc())
    )
    result = await db.execute(stmt)
    return [(row[0], row[1]) for row in result.all()]


def _apply_rule(base_price: int, rule: PriceListRule) -> int:
    """Apply one rule to a base price, in integer Rial."""
    if rule.fixed_price_rial is not None:
        return rule.fixed_price_rial
    if rule.discount_bp is not None:
        # Integer floor: (base * (10000 - bp)) // 10000. Never rounds up.
        return (base_price * (10_000 - rule.discount_bp)) // 10_000
    return base_price


async def resolve_price_for_segment(
    db: AsyncSession,
    *,
    product_id: uuid.UUID,
    variant_id: uuid.UUID | None,
    base_price: int,
    quantity: int,
    segment: CustomerSegment,
) -> int:
    """Price for one segment, falling back to ``base_price`` when no rule matches.

    The best rule is the most specific scope, then the lowest list priority,
    then the highest min_quantity that the order satisfies (a bigger bracket
    is a better deal).
    """
    if quantity <= 0:
        return base_price

    rules = await _load_active_rules(
        db, segment=segment, product_id=product_id, variant_id=variant_id
    )

    # Specificity: variant rule > product rule > catalog-wide.
    def specificity(rule: PriceListRule) -> int:
        if rule.variant_id is not None:
            return 3
        if rule.product_id is not None:
            return 2
        return 1

    eligible = [r for r, _p in rules if quantity >= r.min_quantity]
    if not eligible:
        return base_price

    # Highest specificity first; within a tier, lowest list priority; within
    # that, the largest satisfied min_quantity (best bulk bracket).
    best = max(
        eligible,
        key=lambda r: (specificity(r), -_priority_of(r, rules), r.min_quantity),
    )
    resolved = _apply_rule(base_price, best)
    if resolved != base_price:
        await logger.ainfo(
            "pricelist_rule_applied",
            product_id=str(product_id),
            variant_id=str(variant_id) if variant_id else None,
            segment=segment.value,
            base_price=base_price,
            resolved_price=resolved,
            rule_id=str(best.id),
        )
    return resolved


def _priority_of(rule: PriceListRule, rules: list[tuple[PriceListRule, int]]) -> int:
    for r, p in rules:
        if r is rule:
            return p
    return 100


async def resolve_price_for_user(
    db: AsyncSession,
    *,
    product_id: uuid.UUID,
    variant_id: uuid.UUID | None,
    base_price: int,
    quantity: int,
    user_segment: CustomerSegment | None,
) -> int:
    """Public entry: pick the segment's price, else fall back to base.

    ``user_segment=None`` means a guest/retail shopper; the RETAIL list is
    tried and the base price returned when nothing matches.
    """
    segment = user_segment or CustomerSegment.RETAIL
    return await resolve_price_for_segment(
        db,
        product_id=product_id,
        variant_id=variant_id,
        base_price=base_price,
        quantity=quantity,
        segment=segment,
    )
