"""Scheduled publishing for blog posts.

Fires every minute like the other schedulers, and the work is idempotent:
`publish_due_scheduled` clears the schedule column as it goes, so a run that
crashes halfway does not republish on the next tick.

(The custom-post-type scheduler that used to live here was removed on
2026-10-09 with the rest of the content-type builders — archive:
`_archived/content-types-removal-2026-10-09/`.)
"""

from __future__ import annotations

import asyncio
from typing import Any

import structlog

from app.core.database.session import async_session_factory
from app.worker.celery_app import celery_app

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


async def _publish_due_scheduled_posts_async() -> int:
    from app.modules.blog.application.blog_service import BlogService

    async with async_session_factory() as db:
        return await BlogService(db).publish_due_scheduled()


@celery_app.task(
    name="app.modules.blog.application.tasks.publish_due_scheduled_posts",
    acks_late=True,
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=5,
)
def publish_due_scheduled_posts() -> int:
    """Move blog posts whose scheduled time has arrived to published.

    The logic lives in `BlogService.publish_due_scheduled` and this is only the
    celery wrapper — beat has named this task since it was scheduled, so a
    missing definition is not a quiet degradation: every minute the worker
    accepts the message and answers "Received unregistered task", and the posts
    whose time came stay drafts with no signal that anything was waiting.
    """
    return asyncio.run(_publish_due_scheduled_posts_async())