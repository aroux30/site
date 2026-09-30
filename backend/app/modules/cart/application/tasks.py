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
from app.modules.cart.application import recovery_service
from app.modules.inventory.application import inventory_service
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
                # Delegate releasing any pending stock reservations to inventory domain service
                await inventory_service.release_reservations_for_cart(db, cart.id)

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


async def _send_abandoned_cart_reminders_async() -> dict[str, Any]:
    """Scan active, non-empty carts past a recovery-stage window and queue reminders."""
    async with async_session_factory() as db:
        try:
            result = await recovery_service.process_recoverable_carts(db)
            await db.commit()
            return {"status": "success", **result}
        except Exception:
            await db.rollback()
            await logger.aexception("abandoned_cart_reminders_failed")
            raise


# Retry policy (audit R5): queuing is idempotent by (cart, stage), so a
# transient failure is retried with exponential backoff and the reminder goes
# out exactly once even if the first attempt died mid-batch.
@celery_app.task(
    name="app.modules.cart.application.tasks.send_abandoned_cart_reminders",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=5,
)
def send_abandoned_cart_reminders() -> dict[str, Any]:
    """Find abandoned carts due for the next recovery stage and queue reminders."""
    return asyncio.run(_send_abandoned_cart_reminders_async())


# Retry policy (audit R5): this task is idempotent (re-running cannot
# duplicate money movement or state transitions), so transient
# DB/Elasticsearch/Redis errors are retried with exponential backoff.
@celery_app.task(
    name="app.modules.cart.application.tasks.expire_stale_carts",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=5,
)
def expire_stale_carts() -> dict[str, Any]:
    """Query carts where status='active' and expires_at < now.

    Marks non-empty stale carts as 'abandoned' and deletes empty stale carts.
    Also releases any associated reservations.
    """
    return asyncio.run(_expire_stale_carts_async())
