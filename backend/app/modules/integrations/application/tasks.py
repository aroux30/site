"""Webhook delivery Celery tasks.

Beat drains the pending-delivery queue every minute. Deliveries are idempotent
consumers of their own queue row: a retried attempt only re-POSTs the same
event payload (external receivers must tolerate duplicates, per webhook
convention — X-Webhook-Delivery header is the idempotency key).
"""

from __future__ import annotations

import asyncio
from typing import Any

import structlog

from app.core.database.session import async_session_factory
from app.modules.integrations.application import webhook_service
from app.worker.celery_app import celery_app

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


async def _process_pending_async() -> dict[str, Any]:
    async with async_session_factory() as db:
        try:
            results = await webhook_service.process_pending_deliveries(db)
            await db.commit()
        except Exception:
            await db.rollback()
            await logger.aexception("process_pending_webhooks_failed")
            raise
    return {"status": "success", **results}


@celery_app.task(
    name="app.modules.integrations.application.tasks.process_pending_webhooks",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=5,
)
def process_pending_webhooks() -> dict[str, Any]:
    """Deliver due outbound webhooks (HMAC-signed POSTs with backoff)."""
    return asyncio.run(_process_pending_async())
