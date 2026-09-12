"""Tiered volume pricing engine for digital products (Karta findPrice / rynk_prices).

Calculates dynamic unit prices based on quantity brackets (e.g. wholesale / bulk purchase).
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
    """Create a volume pricing tier for a product."""
    safe_product_id = uuid.UUID(str(product_id))
    tier = PriceTier(
        product_id=safe_product_id,
        from_qty=from_qty,
        to_qty=to_qty,
        unit_price=unit_price,
    )
    db.add(tier)
    await db.flush()
    return tier


async def list_price_tiers(
    db: AsyncSession,
    product_id: uuid.UUID,
) -> list[PriceTier]:
    """Get all pricing tiers for a product ordered by bracket start."""
    safe_product_id = uuid.UUID(str(product_id))
    stmt = (
        select(PriceTier)
        .where(PriceTier.product_id == safe_product_id)
        .order_by(PriceTier.from_qty.asc())
    )
    return list((await db.execute(stmt)).scalars().all())
