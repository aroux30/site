"""Scheduled Celery tasks for the privacy module.

P0 "حریم خصوصی: حذف خودکار داده‌های منقضی". The admin route that purges
expired data exports existed and worked, but nothing ever called it: an export
requested and never collected kept its full payload forever, which is the one
case the retention window exists to cover. A privacy control that depends on
somebody remembering a button is not a control.
"""

from __future__ import annotations

import asyncio
from typing import Any

import structlog
from celery import shared_task

from app.core.database.session import async_session_factory
from app.modules.settings.application.comment_ip_retention_service import (
    CommentIpRetentionService,
)
from app.modules.settings.application.privacy_request_service import (
    PrivacyRequestService,
)
from app.worker.celery_app import celery_app

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# Once a day. The retention window these rows carry is measured in days, so an
# hourly job would do the same work 24 times and change nothing between runs.
PURGE_HOUR = 4


async def _purge_expired_privacy_results_async() -> dict[str, Any]:
    """Clear the result payloads whose retention window has closed."""
    async with async_session_factory() as db:
        try:
            purged = await PrivacyRequestService.purge_expired(db)
        except Exception:
            await db.rollback()
            await logger.aexception("privacy_results_purge_failed")
            raise

    if purged:
        await logger.ainfo("privacy_request_results_purged", purged=purged)
    return {"status": "success", "purged": purged}


# Idempotent by construction: a row whose payload is already NULL is filtered
# out, so a retry after a partial run cannot double-count or fail.
@celery_app.task(
    name="app.modules.settings.application.tasks.purge_expired_privacy_results",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=5,
)
def purge_expired_privacy_results() -> dict[str, Any]:
    """Purge expired data-export payloads (GDPR retention)."""
    return asyncio.run(_purge_expired_privacy_results_async())


# ── Comment IP retention ───────────────────────────────────────────────────
#
# P0 "حریم خصوصی: نگه‌داشت IP دیدگاه". The erasure path masks an address only for
# the one subject who asked for it. Every other comment kept its exact IP forever,
# in a table the storefront can read, with no time limit — so the gap was not
# that masking existed but that nothing applied it with time.


async def _mask_expired_comment_ips_async() -> dict[str, Any]:
    """Reduce past-the-window comment IPs to their network."""
    async with async_session_factory() as db:
        try:
            masked = await CommentIpRetentionService.mask_expired_ips(db)
        except Exception:
            await db.rollback()
            await logger.aexception("comment_ip_mask_failed")
            raise

    if masked:
        await logger.ainfo("comment_ips_masked_by_schedule", masked=masked)
    return {"status": "success", "masked": masked}


@celery_app.task(
    name="app.modules.settings.application.tasks.mask_expired_comment_ips",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=5,
)
def mask_expired_comment_ips() -> dict[str, Any]:
    """Mask comment IPs past the retention window to their network."""
    return asyncio.run(_mask_expired_comment_ips_async())


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
