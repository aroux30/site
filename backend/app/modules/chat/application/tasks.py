"""Celery tasks for the chat module.

One daily job: delete sessions idle longer than the configured ``auto_delete_days``
(the plugin's ``n8n_chat_daily_cleanup`` cron). Registered in
``app.worker.celery_app`` (``TASK_MODULES`` + ``beat_schedule``).
"""

from __future__ import annotations

import structlog
from celery import shared_task

from app.core.database.session import async_session_factory

logger: structlog.stdlib.BoundLogger = structlog.get_logger()


@shared_task(name="app.modules.chat.application.tasks.cleanup_old_chat_sessions")
async def cleanup_old_chat_sessions() -> dict[str, int]:
    """Delete chat sessions idle past ``auto_delete_days`` and stale presence."""
    from app.modules.chat.application import chat_config
    from app.modules.chat.application.chat_service import ChatService

    async with async_session_factory() as db:
        config = await chat_config.get_config(db)
        days = int(config.get("auto_delete_days", 60) or 0)
        deleted = await ChatService.cleanup_old_sessions(db, days)
        await db.commit()
    logger.info("chat_cleanup_done", deleted=deleted, days=days)
    return {"deleted": deleted, "days": days}
