"""Celery tasks for the automation rules engine.

Trigger call-sites (commerce code) never import the engine directly: they
call :func:`queue_automation_trigger`, which is fire-and-forget — a broker
outage or serialisation failure is logged and swallowed so the business
transaction is never impacted.
"""

from __future__ import annotations

import asyncio
from typing import Any

import structlog

from app.core.database.session import async_session_factory
from app.worker.celery_app import celery_app

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


def queue_automation_trigger(trigger_type: str, context: dict[str, Any]) -> None:
    """Enqueue a trigger evaluation (best-effort, never raises).

    Called inline from the commerce flows (order paid transition, user
    registration). The ``.delay`` failure mode — broker down, payload not
    JSON-serialisable — is logged with structlog and dropped: automation is
    an additive side-effect and commerce must never break because of it.
    """
    try:
        dispatch_automation_trigger.delay(str(trigger_type), dict(context))
    except Exception as exc:
        logger.warning(
            "automation_trigger_enqueue_failed",
            trigger_type=str(trigger_type),
            error=str(exc),
        )


async def _evaluate_async(trigger_type: str, context: dict[str, Any]) -> dict[str, Any]:
    """Open a session, run the engine, commit; report the summary."""
    from app.modules.automation.application import rules_engine

    async with async_session_factory() as db:
        try:
            summary = await rules_engine.evaluate(db, trigger_type, context)
            await db.commit()
            return summary
        except Exception as exc:
            await db.rollback()
            await logger.aerror(
                "automation_trigger_evaluation_failed",
                trigger_type=str(trigger_type),
                error=str(exc),
            )
            return {
                "trigger": str(trigger_type),
                "fired": [],
                "skipped": [],
                "failed": [],
                "error": str(exc),
            }


@celery_app.task(name="app.modules.automation.application.tasks.dispatch_automation_trigger")
def dispatch_automation_trigger(trigger_type: str, context: dict[str, Any]) -> dict[str, Any]:
    """Evaluate all active rules bound to *trigger_type* (Celery entrypoint)."""
    return asyncio.run(_evaluate_async(trigger_type, context))


# The outbox drain lives in ``outbox_worker`` rather than this module, so
# autodiscover — which only ever imports ``<pkg>.application.tasks`` — never
# reached it. The beat entry existed and looked correct, but the task was not
# in the worker's registry, so nothing drained the queue: notifications, email,
# accounting and loyalty all hung behind 2700+ PENDING rows. Imported here for
# the registration side effect only, at the bottom so the import cycle back
# into celery_app is already resolved. The name is bound to ``_outbox_worker``
# rather than left dangling so linters and readers can see it is deliberate.
from app.modules.automation.application import outbox_worker as _outbox_worker  # noqa: E402,F401

