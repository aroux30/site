"""Cross-sell / accessory application service (Odoo website_sale
``accessory_product_ids`` concept, rebuilt clean-room).

A "product accessory" is a directional link: "when viewing or buying product
X, also offer accessory Y". The service enforces three invariants:

* a product cannot be its own accessory (no self-loop),
* the pair is unique (the DB unique constraint is the source of truth; the
  service pre-checks to return a clean ConflictError instead of an IntegrityError),
* both ends must reference real products.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import delete, func, select

from app.core.exceptions.handlers import ConflictError, NotFoundError, ValidationError
from app.modules.catalog.domain.models import (
    Product,
    ProductAccessory,
    ProductImage,
    ProductVariant,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


async def _ensure_product_exists(db: AsyncSession, product_id: uuid.UUID) -> Product:
    stmt = select(Product).where(Product.id == product_id)
    product = (await db.execute(stmt)).scalar_one_or_none()
    if product is None:
        raise NotFoundError(resource="Product", detail=f"Product {product_id} not found")
    return product


async def add_accessory(
    db: AsyncSession,
    *,
    product_id: uuid.UUID,
    accessory_id: uuid.UUID,
    position: int = 0,
) -> ProductAccessory:
    """Link ``accessory_id`` as an accessory of ``product_id`` (idempotent).

    Adding an already-linked pair returns the existing row rather than raising,
    so the admin UI "save" action is safe to repeat.
    """
    if product_id == accessory_id:
        raise ValidationError("A product cannot be its own accessory")
    await _ensure_product_exists(db, product_id)
    await _ensure_product_exists(db, accessory_id)

    existing_stmt = select(ProductAccessory).where(
        ProductAccessory.product_id == product_id,
        ProductAccessory.accessory_id == accessory_id,
    )
    existing = (await db.execute(existing_stmt)).scalar_one_or_none()
    if existing is not None:
        await logger.ainfo(
            "accessory_already_linked",
            product_id=str(product_id),
            accessory_id=str(accessory_id),
        )
        return existing

    link = ProductAccessory(
        product_id=product_id, accessory_id=accessory_id, position=position
    )
    db.add(link)
    await db.flush()
    await logger.ainfo(
        "accessory_linked",
        product_id=str(product_id),
        accessory_id=str(accessory_id),
    )
    return link


async def remove_accessory(
    db: AsyncSession,
    *,
    product_id: uuid.UUID,
    accessory_id: uuid.UUID,
) -> bool:
    """Remove one accessory link. Returns False when the link did not exist."""
    stmt = delete(ProductAccessory).where(
        ProductAccessory.product_id == product_id,
        ProductAccessory.accessory_id == accessory_id,
    )
    result = await db.execute(stmt)
    removed = result.rowcount > 0  # type: ignore[attr-defined]
    if removed:
        await logger.ainfo(
            "accessory_unlinked",
            product_id=str(product_id),
            accessory_id=str(accessory_id),
        )
    return removed


async def list_accessories(
    db: AsyncSession,
    product_id: uuid.UUID,
) -> list[Product]:
    """Active accessories of a product, ordered for the upsell rail.

    Only active, published products are offered to a shopper; an accessory
    that was since disabled or unpublished is filtered out here, not deleted,
    so re-enabling it restores the link.
    """
    stmt = (
        select(Product)
        .join(ProductAccessory, ProductAccessory.accessory_id == Product.id)
        .where(
            ProductAccessory.product_id == product_id,
            Product.is_active.is_(True),
        )
        .order_by(ProductAccessory.position.asc(), ProductAccessory.created_at.asc())
    )
    result = await db.execute(stmt)
    accessories = list(result.scalars().all())

    # Enrich for the storefront rail in two batched queries (no N+1):
    # lowest active variant price in Toman, and the primary image URL.
    ids = [p.id for p in accessories]
    if ids:
        price_stmt = (
            select(ProductVariant.product_id, func.min(ProductVariant.price))
            .where(
                ProductVariant.product_id.in_(ids),
                ProductVariant.is_active.is_(True),
            )
            .group_by(ProductVariant.product_id)
        )
        price_by_product: dict[uuid.UUID, int] = {
            row[0]: row[1] for row in await db.execute(price_stmt)
        }

        image_stmt = (
            select(ProductImage.product_id, ProductImage.url)
            .where(ProductImage.product_id.in_(ids))
            .order_by(ProductImage.is_primary.desc(), ProductImage.position.asc())
        )
        image_by_product: dict[uuid.UUID, str] = {}
        for row in await db.execute(image_stmt):
            # First row per product is its primary (or lowest-position) image.
            image_by_product.setdefault(row[0], row[1])

        # ``price`` in ProductAccessoryResponse is Toman (matches the rest of
        # the catalog API); the variant row stores Rial, so convert once here.
        for p in accessories:
            price_rial = price_by_product.get(p.id)
            p.upsell_price = None if price_rial is None else price_rial // 10
            p.upsell_image_url = image_by_product.get(p.id)

    return accessories


async def set_accessories(
    db: AsyncSession,
    *,
    product_id: uuid.UUID,
    accessory_ids: list[uuid.UUID],
) -> list[ProductAccessory]:
    """Replace a product's accessory set atomically.

    Idempotent by construction: the final set is exactly ``accessory_ids``
    regardless of how many times this runs. Self-links are dropped silently.
    """
    await _ensure_product_exists(db, product_id)

    # Dedupe and drop self-links while preserving order.
    wanted: list[uuid.UUID] = []
    seen: set[uuid.UUID] = set()
    for aid in accessory_ids:
        if aid == product_id or aid in seen:
            continue
        seen.add(aid)
        wanted.append(aid)

    # Remove links no longer wanted.
    if wanted:
        del_stmt = delete(ProductAccessory).where(
            ProductAccessory.product_id == product_id,
            ProductAccessory.accessory_id.not_in(wanted),
        )
    else:
        del_stmt = delete(ProductAccessory).where(ProductAccessory.product_id == product_id)
    await db.execute(del_stmt)

    # Add the missing ones in order.
    existing_stmt = select(ProductAccessory.accessory_id).where(
        ProductAccessory.product_id == product_id
    )
    existing = {row[0] for row in await db.execute(existing_stmt)}
    for position, aid in enumerate(wanted):
        if aid in existing:
            continue
        db.add(ProductAccessory(product_id=product_id, accessory_id=aid, position=position))

    await db.flush()
    await logger.ainfo(
        "accessories_set", product_id=str(product_id), count=len(wanted)
    )
    final_stmt = select(ProductAccessory).where(ProductAccessory.product_id == product_id)
    final_result = await db.execute(final_stmt)
    return list(final_result.scalars().all())


async def count_accessories(db: AsyncSession, product_id: uuid.UUID) -> int:
    stmt = (
        select(func.count())
        .select_from(ProductAccessory)
        .where(ProductAccessory.product_id == product_id)
    )
    return int((await db.execute(stmt)).scalar_one())
