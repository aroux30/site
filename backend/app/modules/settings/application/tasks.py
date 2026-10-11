"""Scheduled Celery tasks for the settings module."""

from __future__ import annotations

from typing import Any

import structlog
from celery import shared_task

from app.core.database.session import async_session_factory

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


# ── Scheduled Site Health ──────────────────────────────────────────────────
#
# Restored 2026-10-02: another session's rewrite of this file dropped it while
# the beat entry in celery_app.py stayed, so the daily job fired into
# "unregistered task" again — the exact failure this module was added to fix,
# and the one `check_scheduled_tasks.py` exists to catch.


@shared_task(name="app.modules.settings.application.tasks.run_site_health")
async def run_site_health() -> dict[str, str]:
    """Record one site-health run.

    WordPress runs Site Health twice a day. Once is what this store needs: the
    checks that matter here (disk filling, the database being unreachable, the
    scheduler being dead) do not change inside a day, and a check that only runs
    twice a day cannot notice a full disk at 3am before someone notices the site
    is down.

    A failure is swallowed deliberately. A health check that raises when the
    database is down — which is exactly when it matters — would show up in the
    worker's error log and nowhere else; the run row is where the operator
    looks, so the task makes sure that row exists.
    """
    try:
        async with async_session_factory() as db:
            from app.modules.settings.application.site_health_service import (
                SiteHealthService,
            )

            report = await SiteHealthService.record_run(db, trigger="scheduled")
        worst = report.get("worst_status")
        logger.info("site_health_scheduled_run", worst=worst)
        return {"status": "ok", "worst": str(worst)}
    except Exception as exc:  # noqa: BLE001 — a failed check must not fail the beat
        logger.error("site_health_scheduled_run_failed", error=str(exc))
        return {"status": "failed", "error": str(exc)[:200]}
