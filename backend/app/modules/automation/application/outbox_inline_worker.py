"""In-process outbox poller — runs the transactional outbox without Celery.

The catalog publishes ProductCreated/Updated/Deleted to the outbox; the
Elasticsearch projection only catches up when something drains that outbox.
In the Docker stack the `ecommerce-worker` container (Celery beat) drains it.
Native/dev launches — uvicorn straight on the host, the way this project is
actually developed — have no Celery worker, so outbox rows piled up forever
and products created in the admin panel never appeared in storefront search
or the faceted filters (found live 2026-11-01: ES count 0, Postgres 6 active
products, storefront "۰ کالا" with an empty filter sidebar).

This poller claims batches with the same SKIP LOCKED lease the Celery worker
uses (OutboxService.claim_batch), so running alongside the Docker worker is
safe: every message is processed exactly once by whoever claims it. Product
events sync their search document INLINE (no Celery round-trip); every other
event routes through the shared `_handle_message`, whose DB-side work
(notifications, wallet, blog) runs inline too.
"""

from __future__ import annotations

import asyncio

import structlog

from app.core.database.session import async_session_factory
from app.modules.automation.application.outbox_worker import _handle_message
from app.shared.events.outbox_service import OutboxService

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

POLL_INTERVAL_SECONDS = 5.0
BATCH_SIZE = 50

_PRODUCT_EVENTS = ("ProductCreated", "ProductUpdated", "ProductDeleted")


async def _poll_once() -> tuple[int, int]:
    """Claim and dispatch one batch; returns (processed, failed)."""
    async with async_session_factory() as db:
        try:
            messages = await OutboxService.claim_batch(db, batch_size=BATCH_SIZE)
            await db.commit()
        except Exception as e:  # noqa: BLE001 — the poller must never die
            await db.rollback()
            await logger.awarning("outbox_inline_claim_failed", error=str(e))
            return (0, 0)

    processed = 0
    failed = 0
    for msg in messages:
        async with async_session_factory() as db:
            try:
                if msg.event_type in _PRODUCT_EVENTS:
                    payload = msg.payload or {}
                    product_id = payload.get("product_id") or payload.get("id")
                    if product_id:
                        from app.modules.search.application.tasks import (
                            _sync_single_product_async,
                        )

                        await _sync_single_product_async(str(product_id))
                else:
                    await _handle_message(db, msg.event_type, msg.payload, msg.id)
                await OutboxService.mark_processed(db, msg.id)
                await db.commit()
                processed += 1
            except Exception as e:  # noqa: BLE001 — per-message isolation
                await db.rollback()
                try:
                    await OutboxService.mark_failed(db, msg.id, str(e))
                    await db.commit()
                except Exception:  # noqa: BLE001
                    await db.rollback()
                failed += 1
    return (processed, failed)


async def run_outbox_poller() -> None:
    """Long-lived loop: drain the outbox every POLL_INTERVAL_SECONDS."""
    await logger.ainfo("outbox_inline_poller_started")
    while True:
        try:
            processed, failed = await _poll_once()
            if processed or failed:
                await logger.ainfo(
                    "outbox_inline_poller_batch",
                    processed=processed,
                    failed=failed,
                )
        except asyncio.CancelledError:
            await logger.ainfo("outbox_inline_poller_stopped")
            raise
        except Exception as e:  # noqa: BLE001 — the loop must never die
            await logger.awarning("outbox_inline_poller_error", error=str(e))
        await asyncio.sleep(POLL_INTERVAL_SECONDS)
