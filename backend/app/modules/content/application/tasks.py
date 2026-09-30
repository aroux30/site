"""CMS content background tasks: scheduled publish/unpublish of pages.

Mirrors the blog scheduler: beat fires every minute, and pages whose
``scheduled_publish_at`` / ``scheduled_unpublish_at`` has passed transition
state. Idempotent — firing clears the schedule column.
"""

from __future__ import annotations

import asyncio
from typing import Any

import structlog

from app.core.database.session import async_session_factory
from app.modules.content.application import cms_page_service
from app.worker.celery_app import celery_app

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


async def _process_scheduled_pages_async() -> dict[str, Any]:
    from app.modules.content.application import entry_revision_service

    async with async_session_factory() as db:
        try:
            counts = await cms_page_service.process_scheduled_pages(db)
            entry_counts = await entry_revision_service.process_scheduled_entries(db)
            await db.commit()
        except Exception:
            await db.rollback()
            await logger.aexception("process_scheduled_cms_pages_failed")
            raise
    return {
        "status": "success",
        **counts,
        "entries_published": entry_counts["published"],
        "entries_unpublished": entry_counts["unpublished"],
    }


@celery_app.task(
    name="app.modules.content.application.tasks.process_scheduled_cms_pages",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=5,
)
def process_scheduled_cms_pages() -> dict[str, Any]:
    """Promote/demote CMS pages whose schedule is due."""
    return asyncio.run(_process_scheduled_pages_async())
