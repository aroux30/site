"""Admin-facing CRUD for price lists (Odoo product.pricelist concept).

Kept separate from the resolver so the read-path service stays lean and the
write path can validate and build the nested rule set in one transaction.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.modules.pricing.domain.models import PriceList, PriceListRule
from app.modules.pricing.schemas.pricing import PriceListCreate

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


async def list_price_lists(db: AsyncSession) -> list[PriceList]:
    stmt = select(PriceList).order_by(PriceList.priority.asc(), PriceList.created_at.desc())
    return list((await db.execute(stmt)).scalars().all())


async def get_price_list(db: AsyncSession, price_list_id: uuid.UUID) -> PriceList | None:
    stmt = (
        select(PriceList)
        .options(selectinload(PriceList.rules))
        .where(PriceList.id == price_list_id)
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def create_price_list(db: AsyncSession, data: PriceListCreate) -> PriceList:
    """Create a price list and its rules in one transaction.

    The nested rules are validated by the schema (mutually exclusive pricing
    strategy, product-xor-variant scope), so this only needs to map them.
    """
    price_list = PriceList(
        name=data.name,
        segment=data.segment,
        priority=data.priority,
        is_active=data.is_active,
        valid_from=data.valid_from,
        valid_to=data.valid_to,
    )
    db.add(price_list)
    await db.flush()  # get price_list.id before adding rules

    for rule_data in data.rules:
        db.add(
            PriceListRule(
                price_list_id=price_list.id,
                product_id=rule_data.product_id,
                variant_id=rule_data.variant_id,
                min_quantity=rule_data.min_quantity,
                fixed_price_rial=rule_data.fixed_price_rial,
                discount_bp=rule_data.discount_bp,
            )
        )

    await db.flush()
    await logger.ainfo(
        "price_list_created",
        price_list_id=str(price_list.id),
        segment=data.segment.value,
        rule_count=len(data.rules),
    )

    # Re-fetch with rules loaded for the response.
    fresh = await get_price_list(db, price_list.id)
    return fresh if fresh is not None else price_list
