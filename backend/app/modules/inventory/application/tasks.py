"""Inventory background Celery tasks."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

import structlog
from sqlalchemy import select, update

from app.core.database.session import async_session_factory
from app.modules.inventory.domain.models import (
    InventoryItem,
    InventoryReservation,
    InventoryTransaction,
    ReservationStatus,
    TransactionType,
)
from app.worker.celery_app import celery_app

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


async def _check_low_stock_async() -> dict[str, Any]:
    """Scan inventory items and log/alert on stock below threshold."""
    async with async_session_factory() as db:
        try:
            stmt = select(InventoryItem).where(
                InventoryItem.track_inventory == True,  # noqa: E712
                InventoryItem.available <= InventoryItem.low_stock_threshold,
            )
            items = list((await db.execute(stmt)).scalars().all())

            low_stock_variants = []
            for item in items:
                low_stock_variants.append({
                    "inventory_item_id": str(item.id),
                    "variant_id": str(item.variant_id),
                    "available": item.available,
                    "threshold": item.low_stock_threshold,
                })
                await logger.awarning(
                    "low_stock_alert",
                    inventory_item_id=str(item.id),
                    variant_id=str(item.variant_id),
                    available=item.available,
                    threshold=item.low_stock_threshold,
                )

            return {
                "status": "success",
                "low_stock_count": len(items),
                "items": low_stock_variants,
            }
        except Exception as exc:
            await logger.aerror("low_stock_check_failed", error=str(exc))
            return {"status": "error", "message": str(exc)}


async def _release_expired_reservations_async() -> dict[str, Any]:
    """Release pending inventory reservations that have passed their TTL."""
    now = datetime.now(timezone.utc)
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
            reservations = list((await db.execute(stmt)).scalars().all())

            for res in reservations:
                item_stmt = (
                    select(InventoryItem)
                    .where(InventoryItem.id == res.inventory_item_id)
                    .with_for_update()
                )
                item = (await db.execute(item_stmt)).scalar_one_or_none()

                if item:
                    item.reserved = max(0, item.reserved - res.quantity)
                    item.available += res.quantity

                    tx = InventoryTransaction(
                        inventory_item_id=item.id,
                        quantity=res.quantity,
                        type=TransactionType.RELEASED,
                        reference_type="reservation_expiry",
                        reference_id=res.id,
                        notes="Automatic release of expired cart reservation",
                    )
                    db.add(tx)

                res.status = ReservationStatus.EXPIRED
                released_count += 1

            await db.commit()
            await logger.ainfo("expired_reservations_released", count=released_count)
            return {"status": "success", "released_count": released_count}
        except Exception as exc:
            await db.rollback()
            await logger.aerror("release_reservations_failed", error=str(exc))
            return {"status": "error", "message": str(exc)}


@celery_app.task(name="app.modules.inventory.application.tasks.check_low_stock_task")
def check_low_stock_task() -> dict[str, Any]:
    """Celery task entrypoint to check low stock items."""
    return asyncio.run(_check_low_stock_async())


@celery_app.task(name="app.modules.inventory.application.tasks.release_expired_reservations")
def release_expired_reservations() -> dict[str, Any]:
    """Celery task entrypoint to release expired stock reservations."""
    return asyncio.run(_release_expired_reservations_async())
