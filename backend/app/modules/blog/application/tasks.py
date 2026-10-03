"""Scheduled publishing for custom post type entries.

The other content-entry system has this; this one did not, so an entry dated
forward through the blog admin's content-types tab stayed a draft forever with
no signal that anything was pending — `scheduled_publish_at` was a column an
operator could fill and a site that would never act on.

Fires every minute like the other schedulers, and the work is idempotent:
`publish_scheduled` clears the schedule column as it goes, so a run that
crashes halfway does not republish on the next tick.
"""

from __future__ import annotations

import asyncio
from typing import Any

import structlog

from app.core.database.session import async_session_factory
from app.modules.blog.application import custom_post_revision_service
from app.worker.celery_app import celery_app

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


async def _publish_scheduled_cpt_entries_async() -> dict[str, Any]:
    async with async_session_factory() as db:
        return await custom_post_revision_service.publish_scheduled(db)


@celery_app.task(
    name="app.modules.blog.application.tasks.publish_scheduled_cpt_entries",
    acks_late=True,
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=5,
)
def publish_scheduled_cpt_entries() -> dict[str, Any]:
    """Move custom post entries whose scheduled time has arrived to published."""
    return asyncio.run(_publish_scheduled_cpt_entries_async())


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