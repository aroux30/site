"""Subscriptions Celery task — the recurring billing runner.

Beat fires this every 15 minutes; each run bills every subscription whose
``next_billing_at`` has passed. Billing is idempotent per period (unique
``(subscription_id, period_index)``), so a duplicate tick or a manual
``run-due`` call cannot double-charge a customer.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

import structlog

from app.core.database.session import async_session_factory
from app.modules.subscriptions.application import subscription_service
from app.worker.celery_app import celery_app

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


async def _run_due_billings_async() -> dict[str, Any]:
    async with async_session_factory() as db:
        try:
            summary = await subscription_service.run_due_billings(
                db, now=datetime.now(UTC)
            )
            await db.commit()
            return {"status": "success", **summary}
        except Exception:
            await db.rollback()
            await logger.aexception("subscription_billing_run_failed")
            raise


@celery_app.task(
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    max_retries=3,
    name="app.modules.subscriptions.application.tasks.run_due_subscription_billings"
)
def run_due_subscription_billings() -> dict[str, Any]:
    """Bill every subscription whose billing date has arrived."""
    return asyncio.run(_run_due_billings_async())
