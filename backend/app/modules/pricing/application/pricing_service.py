"""Unified pricing engine for products and digital goods.

Consolidates volume-based quantity tiers (Karta findPrice) with multi-level
customer segment price lists (Odoo product.pricelist concept).
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import select

from app.core.exceptions.handlers import ValidationError
from app.modules.inventory.domain.digital_models import PriceTier

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


async def calculate_dynamic_price(
    db: AsyncSession,
    product_id: uuid.UUID,
    quantity: int,
    base_unit_price: int,
) -> dict[str, Any]:
    """Calculate unit price based on tiered quantity brackets (Karta findPrice).

    Falls back to ``base_unit_price`` if no volume tier applies.
    """
    if quantity <= 0:
        raise ValidationError("Quantity must be positive")

    safe_product_id = uuid.UUID(str(product_id))

    stmt = (
        select(PriceTier)
        .where(PriceTier.product_id == safe_product_id)
        .order_by(PriceTier.from_qty.asc())
    )
    tiers = list((await db.execute(stmt)).scalars().all())

    applied_tier: PriceTier | None = None
    for tier in tiers:
        if quantity >= tier.from_qty and (tier.to_qty is None or quantity <= tier.to_qty):
            applied_tier = tier
            break

    unit_price = applied_tier.unit_price if applied_tier else base_unit_price
    total_price = unit_price * quantity

    return {
        "product_id": safe_product_id,
        "quantity": quantity,
        "unit_price": unit_price,
        "total_price": total_price,
        "tier_applied": applied_tier is not None,
        "from_qty": applied_tier.from_qty if applied_tier else None,
        "to_qty": applied_tier.to_qty if applied_tier else None,
    }


async def set_price_tier(
    db: AsyncSession,
    product_id: uuid.UUID,
    from_qty: int,
    to_qty: int | None,
    unit_price: int,
) -> PriceTier:
    """Create a volume pricing tier for a product with strict boundary validation."""
    if from_qty < 1:
        raise ValidationError("حداقل تعداد در پله قیمت‌گذاری باید حداقل ۱ باشد")
    if to_qty is not None and to_qty < from_qty:
        raise ValidationError("حداکثر تعداد نمی‌تواند کمتر از حداقل تعداد باشد")
    if unit_price < 0:
        raise ValidationError("قیمت واحد نمی‌تواند منفی باشد")

    safe_product_id = uuid.UUID(str(product_id))

    # Reject overlapping ranges for the same product to prevent ambiguous pricing
    existing_stmt = select(PriceTier).where(PriceTier.product_id == safe_product_id)
    existing_tiers = list((await db.execute(existing_stmt)).scalars().all())
    for existing in existing_tiers:
        overlap = False
        if to_qty is None:
            if existing.to_qty is None or existing.to_qty >= from_qty:
                overlap = True
        elif existing.to_qty is None:
            if from_qty >= existing.from_qty:
                overlap = True
        elif not (to_qty < existing.from_qty or from_qty > existing.to_qty):
            overlap = True

        if overlap:
            raise ValidationError(
                f"محدوده درخواستی ({from_qty} تا {to_qty or '∞'}) با پله موجود "
                f"({existing.from_qty} تا {existing.to_qty or '∞'}) تداخل دارد",
                error_code="PRICE_TIER_OVERLAP",
            )

    tier = PriceTier(
        product_id=safe_product_id,
        from_qty=from_qty,
        to_qty=to_qty,
        unit_price=unit_price,
    )
    db.add(tier)
    await db.commit()
    await db.refresh(tier)
    await logger.ainfo(
        "price_tier_created",
        tier_id=str(tier.id),
        product_id=str(safe_product_id),
        from_qty=from_qty,
        to_qty=to_qty,
        unit_price=unit_price,
    )
    return tier


async def list_price_tiers(
    db: AsyncSession,
    product_id: uuid.UUID,
) -> list[PriceTier]:
    """Return all price tiers for a product ordered by from_qty."""
    safe_product_id = uuid.UUID(str(product_id))
    stmt = (
        select(PriceTier)
        .where(PriceTier.product_id == safe_product_id)
        .order_by(PriceTier.from_qty.asc())
    )
    return list((await db.execute(stmt)).scalars().all())


async def resolve_unit_price(
    db: AsyncSession,
    product_id: uuid.UUID,
    base_unit_price: int,
    quantity: int,
    user_segment: Any | None = None,
    variant_id: uuid.UUID | None = None,
) -> int:
    """Single server-side unit-price resolver.

    Layers multi-level price lists (Odoo product.pricelist) on top of
    volume-tier pricing (Karta findPrice).
    """
    calc = await calculate_dynamic_price(
        db,
        product_id=product_id,
        quantity=quantity,
        base_unit_price=base_unit_price,
    )
    tier_price = int(calc["unit_price"])

    if user_segment is None:
        return tier_price

    from app.modules.pricing.application import pricelist_service

    return await pricelist_service.resolve_price_for_user(
        db,
        product_id=product_id,
        variant_id=variant_id,
        base_price=tier_price,
        quantity=quantity,
        user_segment=user_segment,
    )


__all__ = [
    "calculate_dynamic_price",
    "set_price_tier",
    "list_price_tiers",
    "resolve_unit_price",
]
