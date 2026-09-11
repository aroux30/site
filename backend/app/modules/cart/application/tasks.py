"""Cart background Celery tasks.

Handles scheduled cart expiration and expired stock reservation release.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database.session import async_session_factory
from app.modules.cart.domain.models import Cart, CartStatus
from app.modules.inventory.domain.models import (
    InventoryItem,
    InventoryReservation,
    InventoryTransaction,
    ReservationStatus,
    TransactionType,
)
from app.worker.celery_app import celery_app

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


async def _expire_stale_carts_async() -> dict[str, Any]:
    """Async execution logic for expiring stale shopping carts."""
    now = datetime.now(UTC)
    abandoned_count = 0
    deleted_count = 0

    async with async_session_factory() as db:
        try:
            # Query active carts whose expiration time has passed
            stmt = (
                select(Cart)
                .options(selectinload(Cart.items))
                .where(
                    Cart.status == CartStatus.ACTIVE,
                    Cart.expires_at.is_not(None),
                    Cart.expires_at <= now,
                )
            )
            result = await db.execute(stmt)
            stale_carts = list(result.scalars().all())

            for cart in stale_carts:
                # Also release any pending reservations tied to this cart
                res_stmt = select(InventoryReservation).where(
                    InventoryReservation.cart_id == cart.id,
                    InventoryReservation.status == ReservationStatus.PENDING,
                )
                res_result = await db.execute(res_stmt)
                reservations = list(res_result.scalars().all())

                for res in reservations:
                    item_stmt = (
                        select(InventoryItem)
                        .where(InventoryItem.id == res.inventory_item_id)
                        .with_for_update()
                    )
                    item_res = await db.execute(item_stmt)
                    item = item_res.scalar_one_or_none()
                    if item:
                        item.available += res.quantity
                        item.reserved = max(0, item.reserved - res.quantity)
                    res.status = ReservationStatus.EXPIRED
                    db.add(
                        InventoryTransaction(
                            inventory_item_id=res.inventory_item_id,
                            quantity=res.quantity,
                            type=TransactionType.RELEASED,
                            reference_type="cart_expiration",
                            reference_id=cart.id,
                            notes=f"Released reservation {res.id} for expired cart {cart.id}",
                        )
                    )

                if not cart.items:
                    # Delete empty stale carts to prevent clutter
                    await db.delete(cart)
                    deleted_count += 1
                else:
                    # Mark non-empty carts as abandoned
                    cart.status = CartStatus.ABANDONED
                    abandoned_count += 1

            await db.commit()
            await logger.ainfo(
                "stale_carts_processed",
                abandoned=abandoned_count,
                deleted=deleted_count,
                total_checked=len(stale_carts),
            )
        except Exception:
            await db.rollback()
            await logger.aexception("expire_stale_carts_failed")
            raise

    return {
        "status": "success",
        "abandoned_carts": abandoned_count,
        "deleted_empty_carts": deleted_count,
    }


async def _release_expired_reservations_async() -> dict[str, Any]:
    """Async execution logic for releasing expired stock reservations."""
    now = datetime.now(UTC)
    released_count = 0

    async with async_session_factory() as db:
        try:
            stmt = (
                select(InventoryReservation)
                .where(
                    InventoryReservation.status == ReservationStatus.PENDING,
                    InventoryReservation.expires_at <= now,
                )
                .with_for_update()
            )
            result = await db.execute(stmt)
            expired_reservations = list(result.scalars().all())

            for res in expired_reservations:
                item_stmt = (
                    select(InventoryItem)
                    .where(InventoryItem.id == res.inventory_item_id)
                    .with_for_update()
                )
                item_res = await db.execute(item_stmt)
                item = item_res.scalar_one_or_none()

                if item:
                    item.available += res.quantity
                    item.reserved = max(0, item.reserved - res.quantity)

                res.status = ReservationStatus.EXPIRED

                db.add(
                    InventoryTransaction(
                        inventory_item_id=res.inventory_item_id,
                        quantity=res.quantity,
                        type=TransactionType.RELEASED,
                        reference_type="reservation",
                        reference_id=res.id,
                        notes=f"Released expired reservation {res.id}",
                    )
                )
                released_count += 1

            await db.commit()
            await logger.ainfo(
                "expired_reservations_released",
                released_count=released_count,
            )
        except Exception:
            await db.rollback()
            await logger.aexception("release_expired_reservations_failed")
            raise

    return {
        "status": "success",
        "released_reservations": released_count,
    }


@celery_app.task(name="app.modules.cart.application.tasks.expire_stale_carts")
def expire_stale_carts() -> dict[str, Any]:
    """Query carts where status='active' and expires_at < now.

    Marks non-empty stale carts as 'abandoned' and deletes empty stale carts.
    Also releases any associated reservations.
    """
    return asyncio.run(_expire_stale_carts_async())


@celery_app.task(name="app.modules.cart.application.tasks.release_expired_reservations")
def release_expired_reservations() -> dict[str, Any]:
    """Release inventory reservations that have passed their TTL."""
    return asyncio.run(_release_expired_reservations_async())
