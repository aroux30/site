"""Celery background tasks for Broadcast Messaging."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

import structlog

from app.core.database.session import async_session_factory
from app.modules.messaging.application.broadcast_service import send_campaign
from app.worker.celery_app import celery_app

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


async def _async_send_campaign(campaign_id_str: str) -> dict[str, Any]:
    """Execute broadcast campaign within async database session."""
    campaign_id = uuid.UUID(campaign_id_str)
    async with async_session_factory() as db:
        try:
            campaign = await send_campaign(db, campaign_id)
            await db.commit()
            return {
                "status": "success",
                "campaign_id": str(campaign.id),
                "campaign_status": campaign.status.value,
                "total_recipients": campaign.total_recipients,
                "success_count": campaign.success_count,
                "fail_count": campaign.fail_count,
            }
        except Exception as exc:
            await db.rollback()
            await logger.aerror("celery_campaign_send_failed", campaign_id=campaign_id_str, error=str(exc))
            return {"status": "error", "message": str(exc)}


@celery_app.task(name="app.modules.messaging.application.tasks.send_campaign_task")
def send_campaign_task(campaign_id: str) -> dict[str, Any]:
    """Celery task to asynchronously execute a broadcast campaign."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Nested loop or running inside event loop
            import nest_asyncio
            nest_asyncio.apply()
            return loop.run_until_complete(_async_send_campaign(campaign_id))
        else:
            return loop.run_until_complete(_async_send_campaign(campaign_id))
    except RuntimeError:
        return asyncio.run(_async_send_campaign(campaign_id))
