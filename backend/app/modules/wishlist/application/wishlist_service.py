"""Wishlist application service.

Manages a user's default wishlist: adding, removing, and querying items.
Each user has a single "default" wishlist, created lazily on first access.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import and_, select
from sqlalchemy.orm import joinedload

from app.core.exceptions.handlers import ConflictError, NotFoundError
from app.modules.catalog.domain.models import Product
from app.modules.wishlist.domain.models import Wishlist, WishlistItem
from app.modules.wishlist.schemas.wishlist import (
    WishlistCheckResponse,
    WishlistItemResponse,
    WishlistResponse,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
logger: structlog.stdlib.BoundLogger = structlog.get_logger()


class WishlistService:
    """Application service for wishlist operations."""

    # ── Get / create default wishlist ─────────────────────────────────

    async def _get_or_create_wishlist(self, db: AsyncSession, user_id: uuid.UUID) -> Wishlist:
        """Return the user's default wishlist, creating it if needed."""
        result = await db.execute(
            select(Wishlist)
            .where(
                and_(
                    Wishlist.user_id == user_id,
                    Wishlist.name == "default",
                )
            )
            .options(
                joinedload(Wishlist.items),
            )
        )
        wishlist = result.unique().scalar_one_or_none()

        if wishlist is None:
            wishlist = Wishlist(user_id=user_id, name="default")
            db.add(wishlist)
            await db.flush()
            await db.refresh(wishlist)
            await logger.ainfo(
                "wishlist_created",
                wishlist_id=str(wishlist.id),
                user_id=str(user_id),
            )

        return wishlist

    # ── Get wishlist ──────────────────────────────────────────────────

    async def get_wishlist(self, db: AsyncSession, user_id: uuid.UUID) -> WishlistResponse:
        """Return the user's wishlist with product details."""
        wishlist = await self._get_or_create_wishlist(db, user_id)

        # Load items with product details
        items_stmt = (
            select(WishlistItem)
            .where(WishlistItem.wishlist_id == wishlist.id)
            .order_by(WishlistItem.created_at.desc())
        )
        items_result = await db.execute(items_stmt)
        items = items_result.scalars().all()

        # Fetch product info for each item
        item_responses: list[WishlistItemResponse] = []
        for item in items:
            product_info = await self._get_product_info(db, item.product_id)
            item_responses.append(
                WishlistItemResponse(
                    id=str(item.id),
                    product_id=str(item.product_id),
                    product_name=product_info.get("name"),
                    product_slug=product_info.get("slug"),
                    product_image_url=product_info.get("image_url"),
                    product_price=product_info.get("price"),
                    product_is_active=product_info.get("is_active"),
                    added_at=item.created_at,
                )
            )

        return WishlistResponse(
            id=str(wishlist.id),
            name=wishlist.name,
            items=item_responses,
            total_items=len(item_responses),
        )

    # ── Add item ──────────────────────────────────────────────────────

    async def add_item(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        product_id: uuid.UUID,
    ) -> WishlistItemResponse:
        """Add a product to the user's wishlist."""
        wishlist = await self._get_or_create_wishlist(db, user_id)

        # Check if already in wishlist
        existing = await db.execute(
            select(WishlistItem).where(
                and_(
                    WishlistItem.wishlist_id == wishlist.id,
                    WishlistItem.product_id == product_id,
                )
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise ConflictError("Product is already in your wishlist")

        # Verify product exists
        product = await db.execute(select(Product).where(Product.id == product_id))
        if product.scalar_one_or_none() is None:
            raise NotFoundError("Product")

        item = WishlistItem(
            wishlist_id=wishlist.id,
            product_id=product_id,
        )
        db.add(item)
        await db.flush()
        await db.refresh(item)

        product_info = await self._get_product_info(db, product_id)

        await logger.ainfo(
            "wishlist_item_added",
            wishlist_id=str(wishlist.id),
            product_id=str(product_id),
            user_id=str(user_id),
        )

        return WishlistItemResponse(
            id=str(item.id),
            product_id=str(item.product_id),
            product_name=product_info.get("name"),
            product_slug=product_info.get("slug"),
            product_image_url=product_info.get("image_url"),
            product_price=product_info.get("price"),
            product_is_active=product_info.get("is_active"),
            added_at=item.created_at,
        )

    # ── Remove item ───────────────────────────────────────────────────

    async def remove_item(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        product_id: uuid.UUID,
    ) -> None:
        """Remove a product from the user's wishlist."""
        wishlist = await self._get_or_create_wishlist(db, user_id)

        result = await db.execute(
            select(WishlistItem).where(
                and_(
                    WishlistItem.wishlist_id == wishlist.id,
                    WishlistItem.product_id == product_id,
                )
            )
        )
        item = result.scalar_one_or_none()

        if item is None:
            raise NotFoundError("Wishlist item")

        await db.delete(item)
        await db.flush()

        await logger.ainfo(
            "wishlist_item_removed",
            wishlist_id=str(wishlist.id),
            product_id=str(product_id),
            user_id=str(user_id),
        )

    # ── Check membership ──────────────────────────────────────────────

    async def is_in_wishlist(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        product_id: uuid.UUID,
    ) -> WishlistCheckResponse:
        """Check if a product is in the user's wishlist."""
        wishlist_result = await db.execute(
            select(Wishlist).where(
                and_(
                    Wishlist.user_id == user_id,
                    Wishlist.name == "default",
                )
            )
        )
        wishlist = wishlist_result.scalar_one_or_none()

        if wishlist is None:
            return WishlistCheckResponse(
                in_wishlist=False,
                product_id=str(product_id),
            )

        item_result = await db.execute(
            select(WishlistItem.id).where(
                and_(
                    WishlistItem.wishlist_id == wishlist.id,
                    WishlistItem.product_id == product_id,
                )
            )
        )
        in_wishlist = item_result.scalar_one_or_none() is not None

        return WishlistCheckResponse(
            in_wishlist=in_wishlist,
            product_id=str(product_id),
        )

    # ── Private helpers ───────────────────────────────────────────────

    async def _get_product_info(self, db: AsyncSession, product_id: uuid.UUID) -> dict:
        """Fetch minimal product info for display in the wishlist."""
        result = await db.execute(
            select(Product)
            .where(Product.id == product_id)
            .options(
                joinedload(Product.images),
                joinedload(Product.variants),
            )
        )
        product = result.unique().scalar_one_or_none()

        if product is None:
            return {}

        # Primary image
        image_url = None
        if product.images:
            primary = next((img for img in product.images if img.is_primary), None)
            image_url = (primary or product.images[0]).url

        # Cheapest variant price
        price = None
        if product.variants:
            cheapest = min(product.variants, key=lambda v: v.price)
            price = cheapest.price

        return {
            "name": product.name,
            "slug": product.slug,
            "image_url": image_url,
            "price": price,
            "is_active": product.is_active,
        }
