"""Celery background worker task for processing transactional outbox messages."""

from __future__ import annotations

import asyncio
from typing import Any

import structlog

from app.core.database.session import async_session_factory
from app.shared.events.outbox_service import OutboxService
from app.worker.celery_app import celery_app

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


async def _handle_message(db: Any, event_type: str, payload: dict[str, Any]) -> None:
    """Route outbox message to the appropriate module handler."""
    if event_type in ("ProductCreated", "ProductUpdated", "ProductDeleted"):
        # Search index sync
        product_id = payload.get("product_id") or payload.get("id")
        if product_id:
            try:
                from app.modules.search.application.tasks import sync_single_product
                sync_single_product.delay(str(product_id))
            except Exception as e:
                logger.warning("outbox_search_dispatch_failed", error=str(e))

    elif event_type == "OrderConfirmed":
        # Order confirmation notification
        order_id = payload.get("order_id")
        logger.info("outbox_order_confirmed_handled", order_id=order_id)

    elif event_type == "PaymentCompleted":
        # Payment receipt notification
        payment_id = payload.get("payment_id")
        logger.info("outbox_payment_completed_handled", payment_id=payment_id)


async def _drain_outbox_async(batch_size: int = 50) -> dict[str, Any]:
    """Claim and dispatch a batch of pending outbox messages."""
    processed = 0
    failed = 0

    async with async_session_factory() as db:
        try:
            messages = await OutboxService.claim_batch(db, batch_size=batch_size)
            await db.commit()
        except Exception as e:
            await db.rollback()
            await logger.aerror("outbox_claim_failed", error=str(e))
            return {"status": "error", "message": str(e)}

    # Process each claimed message
    for msg in messages:
        async with async_session_factory() as db:
            try:
                await _handle_message(db, msg.event_type, msg.payload)
                await OutboxService.mark_processed(db, msg.id)
                await db.commit()
                processed += 1
            except Exception as e:
                await db.rollback()
                await OutboxService.mark_failed(db, msg.id, str(e))
                await db.commit()
                failed += 1

    return {"status": "success", "processed": processed, "failed": failed}


@celery_app.task(name="app.modules.automation.application.outbox_worker.process_outbox_queue")
def process_outbox_queue() -> dict[str, Any]:
    """Periodic Celery worker task to process outbox queue."""
    return asyncio.run(_drain_outbox_async())
