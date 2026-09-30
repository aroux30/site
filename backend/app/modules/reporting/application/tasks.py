"""Reporting Celery tasks — scheduled report dispatcher.

The beat entry (every minute, Asia/Tehran — the Celery app timezone) scans
``saved_reports`` for active schedules whose ``next_run_at`` has passed and
executes them through ``execute_saved_report``, which is idempotent against
duplicate ticks via its atomic PENDING→RUNNING claim.
"""

from __future__ import annotations

import asyncio
from typing import Any

import structlog

from app.core.database.session import async_session_factory
from app.modules.reporting.application import saved_report_service
from app.worker.celery_app import celery_app

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


async def _dispatch_due_reports_async() -> dict[str, Any]:
    async with async_session_factory() as db:
        try:
            started = await saved_report_service.dispatch_due_reports(db)
            await db.commit()
            await logger.ainfo("scheduled_reports_dispatched", started=started)
            return {"status": "success", "started": started}
        except Exception:
            await db.rollback()
            await logger.aexception("scheduled_reports_dispatch_failed")
            raise


@celery_app.task(
    name="app.modules.reporting.application.tasks.dispatch_due_reports",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    max_retries=3,
)
def dispatch_due_reports() -> dict[str, Any]:
    """Run scheduled saved reports whose next_run_at has passed."""
    return asyncio.run(_dispatch_due_reports_async())
