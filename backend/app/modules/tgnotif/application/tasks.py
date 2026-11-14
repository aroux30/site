"""Celery tasks for the tgnotif module.

Pattern mirrors app.modules.chat.application.tasks:
- @shared_task with explicit name= for reliable routing
- asyncio.run() wrapper for async body
- Best-effort: failures logged, never re-raised to avoid poisoning the queue
"""

from __future__ import annotations

import asyncio
from typing import Any

import structlog
from celery import shared_task

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


async def _send_notification_async(order_id: str) -> dict[str, Any]:
    from app.core.database.session import async_session_factory
    from app.core.config.settings import get_settings
    from app.modules.tgnotif.application.tgnotif_service import send_order_notification

    settings = get_settings()
    site_url = getattr(settings, "SITE_URL", "") or getattr(settings, "FRONTEND_URL", "") or ""

    async with async_session_factory() as db:
        ok = await send_order_notification(db, order_id, site_url=site_url)
    return {"ok": ok, "order_id": order_id}


@shared_task(
    name="app.modules.tgnotif.application.tasks.send_tgnotif_order",
    bind=False,
    max_retries=0,  # best-effort; the outbox already retries delivery
    ignore_result=True,
)
def send_tgnotif_order(order_id: str) -> None:
    """Send Telegram order notification for the given order_id (sync wrapper)."""
    try:
        asyncio.run(_send_notification_async(order_id))
    except Exception as exc:
        # Best-effort: log and return so the outbox item still marks as processed
        logger.error("tgnotif_task_failed", order_id=order_id, error=str(exc))
