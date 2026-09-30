"""Newsletter background Celery tasks.

Two tasks, following the module task convention
(``<pkg>.application.tasks`` with explicit names):

- ``send_newsletter_campaign(campaign_id)`` — the actual sender. Enqueued by
  the admin API (send-now or ETA schedule); re-sent ``failed`` campaigns are
  safe because recipient rows are snapshotted idempotently and sent rows are
  never re-visited.
- ``dispatch_due_scheduled_campaigns()`` — the beat sweep that enqueues
  every scheduled campaign whose ``scheduled_at`` has passed (one-minute
  go-live guarantee, same as blog/CMS scheduled publishing). Duplicate or
  late ticks are harmless: the send guard rejects a campaign that is not
  draft/scheduled/failed.

WIRING NOTE (kept in sync with app/worker/celery_app.py): the worker's
autodiscover package list and the ``beat_schedule`` dict must reference this
module — add ``"app.modules.newsletter"`` to ``celery_app.autodiscover_tasks``
and a beat entry for ``dispatch_due_scheduled_campaigns``. Until then the
tasks register whenever the module is imported (the API process imports it
on first schedule/send call), and the beat sweep is unavailable.
"""

from __future__ import annotations

import asyncio
from typing import Any

import structlog

from app.core.database.session import async_session_factory
from app.worker.celery_app import celery_app

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


async def _send_campaign_async(campaign_id: str) -> dict[str, Any]:
    """Send one campaign in its own session, committing per batch."""
    from app.core.exceptions.handlers import AppException
    from app.modules.newsletter.application import campaign_service

    async with async_session_factory() as db:
        try:
            return await campaign_service.send_campaign(
                db, campaign_id, commit_between_batches=True
            )
        except AppException as exc:
            # Already sending/sent, or nobody to send to: a state conflict,
            # not a transport failure — never autoretry these.
            await db.rollback()
            await logger.awarning(
                "newsletter_campaign_send_skipped",
                campaign_id=campaign_id,
                reason=str(exc.detail),
            )
            return {"status": "skipped", "campaign_id": campaign_id, "reason": str(exc.detail)}
        except Exception:
            await db.rollback()
            await logger.aexception("newsletter_campaign_send_failed", campaign_id=campaign_id)
            raise


@celery_app.task(
    name="app.modules.newsletter.application.tasks.send_newsletter_campaign",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=3,
    # A large list sends 50 SMTP messages per pass; the default 10-minute
    # celery time limit is too tight for a genuinely big list on a slow relay.
    time_limit=3600,
    soft_time_limit=3300,
)
def send_newsletter_campaign(campaign_id: str) -> dict[str, Any]:
    """Send one newsletter campaign (send-now and scheduled sends)."""
    return asyncio.run(_send_campaign_async(campaign_id))


async def _dispatch_due_scheduled_async() -> dict[str, Any]:
    from app.modules.newsletter.application import campaign_service

    async with async_session_factory() as db:
        try:
            dispatched = await campaign_service.dispatch_due_scheduled(db)
            await db.commit()
        except Exception:
            await db.rollback()
            await logger.aexception("newsletter_dispatch_due_scheduled_failed")
            raise
    return {"status": "success", "dispatched": dispatched}


@celery_app.task(
    name="app.modules.newsletter.application.tasks.dispatch_due_scheduled_campaigns",
)
def dispatch_due_scheduled_campaigns() -> dict[str, Any]:
    """Beat sweep: enqueue scheduled campaigns whose send time has passed."""
    return asyncio.run(_dispatch_due_scheduled_async())
