"""Media background Celery tasks: trash retention.

P0 "مدیا: سطل زباله" shipped a trash, and a trash nobody empties is a slow leak
rather than a feature: every deleted file keeps its bytes forever. This is the
scheduled half.

It is a separate job rather than a column default because a purge deletes
files, and a job that deletes files should have a retention window, a visible
task name, and a retry policy — not be a side effect of writing a row.
"""

from __future__ import annotations

import asyncio
from typing import Any

import structlog

from app.core.database.session import async_session_factory
from app.modules.media.application.media_service import MediaService
from app.worker.celery_app import celery_app

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# WordPress's EMPTY_TRASH_DAYS default. Long enough that an operator who
# deletes an image by mistake has a realistic chance of noticing and restoring
# it before it is gone for good.
DEFAULT_RETENTION_DAYS = 30


async def _purge_expired_media_trash_async(
    older_than_days: int = DEFAULT_RETENTION_DAYS,
) -> dict[str, Any]:
    """Purge trashed media assets older than the retention window."""
    async with async_session_factory() as db:
        try:
            purged = await MediaService.empty_trash(
                db, older_than_days=older_than_days
            )
            await db.commit()
        except Exception:
            await db.rollback()
            await logger.aexception("media_trash_purge_failed")
            raise

    if purged:
        await logger.ainfo("media_trash_purged", purged=purged)
    return {"status": "success", "purged": purged}


# Idempotent by construction: a second run finds nothing that is both trashed
# and older than the window, so a retry cannot delete something twice.
@celery_app.task(
    name="app.modules.media.application.tasks.purge_expired_media_trash",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=5,
)
def purge_expired_media_trash(
    older_than_days: int = DEFAULT_RETENTION_DAYS,
) -> dict[str, Any]:
    """Empty the media trash of anything trashed more than N days ago."""
    return asyncio.run(_purge_expired_media_trash_async(older_than_days))
