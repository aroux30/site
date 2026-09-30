"""Inventory background Celery tasks."""

from __future__ import annotations

import asyncio
from typing import Any

import structlog
from sqlalchemy import select

from app.core.database.session import async_session_factory
from app.modules.inventory.domain.models import InventoryItem
from app.worker.celery_app import celery_app

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


async def _evaluate_reorder_rules_async() -> dict[str, Any]:
    """Evaluate reorder rules and emit replenishment suggestions."""
    from app.modules.inventory.application import reorder_service

    async with async_session_factory() as db:
        try:
            result = await reorder_service.evaluate_rules(db)
            await db.commit()
            return {"status": "success", **result}
        except Exception:
            await db.rollback()
            await logger.aexception("evaluate_reorder_rules_failed")
            raise


# Retry policy (audit R5): evaluation is idempotent (the suggestion is
# deduped by rule id + trigger state), so transient failures retry with
# exponential backoff.
@celery_app.task(
    name="app.modules.inventory.application.tasks.evaluate_reorder_rules",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=5,
)
def evaluate_reorder_rules() -> dict[str, Any]:
    """Suggest replenishment for variants that have hit their reorder point."""
    return asyncio.run(_evaluate_reorder_rules_async())


async def _check_low_stock_async() -> dict[str, Any]:
    """Scan inventory items and log/alert on stock below threshold."""
    async with async_session_factory() as db:
        try:
            stmt = select(InventoryItem).where(
                InventoryItem.track_inventory.is_(True),
                InventoryItem.available <= InventoryItem.low_stock_threshold,
            )
            items = list((await db.execute(stmt)).scalars().all())

            low_stock_variants = []
            for item in items:
                low_stock_variants.append(
                    {
                        "inventory_item_id": str(item.id),
                        "variant_id": str(item.variant_id),
                        "available": item.available,
                        "threshold": item.low_stock_threshold,
                    }
                )
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
    """Release pending inventory reservations that have passed their TTL.

    Stock movement stays inside ``inventory_service.expire_stale_reservations``
    so the Celery beat job and the in-process cleanup loop cannot drift apart.
    """
    from app.modules.inventory.application.inventory_service import (
        expire_stale_reservations,
    )

    async with async_session_factory() as db:
        try:
            released_count = await expire_stale_reservations(
                db,
                reference_type="reservation_expiry",
                notes="Automatic release of expired cart reservation",
            )
            await db.commit()
            await logger.ainfo("expired_reservations_released", count=released_count)
            return {"status": "success", "released_count": released_count}
        except Exception as exc:
            await db.rollback()
            await logger.aerror("release_reservations_failed", error=str(exc))
            return {"status": "error", "message": str(exc)}


# Retry policy (audit R5): this task is idempotent (re-running cannot
# duplicate money movement or state transitions), so transient
# DB/Elasticsearch/Redis errors are retried with exponential backoff.
@celery_app.task(
    name="app.modules.inventory.application.tasks.check_low_stock_task",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=5,
)
def check_low_stock_task() -> dict[str, Any]:
    """Celery task entrypoint to check low stock items."""
    return asyncio.run(_check_low_stock_async())


# Retry policy (audit R5): this task is idempotent (re-running cannot
# duplicate money movement or state transitions), so transient
# DB/Elasticsearch/Redis errors are retried with exponential backoff.
@celery_app.task(
    name="app.modules.inventory.application.tasks.release_expired_reservations",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=5,
)
def release_expired_reservations() -> dict[str, Any]:
    """Celery task entrypoint to release expired stock reservations."""
    return asyncio.run(_release_expired_reservations_async())
