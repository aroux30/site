"""SEO background tasks: the broken-link crawler.

The crawler is a scheduled job rather than a request-time scan: fetching a
hundred third-party URLs takes minutes and must not run inside an HTTP request.
The task is a thin wrapper — the logic lives in
:mod:`app.modules.seo.application.link_audit_service`, and beat calls it
periodically. A manual run is available from the admin (the "check now" button),
which calls the same service through the API, so an automatic and a manual run
cannot behave differently.
"""

from __future__ import annotations

import asyncio
from typing import Any

import structlog

from app.core.database.session import async_session_factory
from app.worker.celery_app import celery_app

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


async def _run_link_audit_async(force: bool = False) -> dict[str, Any]:
    from app.modules.seo.application.link_audit_service import run_audit

    async with async_session_factory() as db:
        try:
            return await run_audit(db, force=force)
        except Exception:
            await db.rollback()
            await logger.aexception("link_audit_failed")
            raise


@celery_app.task(
    name="app.modules.seo.application.tasks.run_link_audit",
    acks_late=True,
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=3,
)
def run_link_audit(force: bool = False) -> dict[str, Any]:
    """Check the next batch of due URLs and record the results.

    Named in the beat schedule; a missing definition would make the worker
    answer "Received unregistered task" every run while the audit table stayed
    empty and nothing said why.
    """
    return asyncio.run(_run_link_audit_async(force=force))
