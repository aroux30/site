"""Blog background Celery tasks.

Handles scheduled publication of blog posts whose scheduled_for time has
passed (WordPress-style "scheduled" posts).
"""

from __future__ import annotations

import asyncio
from typing import Any

import structlog

from app.core.database.session import async_session_factory
from app.modules.blog.application.blog_service import BlogService
from app.worker.celery_app import celery_app

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


async def _publish_due_scheduled_posts_async() -> dict[str, Any]:
    """Publish draft posts whose scheduled_for timestamp has passed."""
    async with async_session_factory() as db:
        try:
            svc = BlogService(db)
            published = await svc.publish_due_scheduled()
        except Exception:
            await db.rollback()
            await logger.aexception("publish_due_scheduled_posts_failed")
            raise

    return {
        "status": "success",
        "published_posts": published,
    }


# Idempotent: publishing only flips draft→published for posts already due, so
# re-running cannot double-publish or corrupt state. Safe to autoretry.
@celery_app.task(
    name="app.modules.blog.application.tasks.publish_due_scheduled_posts",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=5,
)
def publish_due_scheduled_posts() -> dict[str, Any]:
    """Promote scheduled blog posts that have reached their publish time."""
    return asyncio.run(_publish_due_scheduled_posts_async())
