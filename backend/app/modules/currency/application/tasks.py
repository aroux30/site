"""Currency sweep — one beat tick per minute, gated by the configured interval.

Why a per-minute tick that usually does nothing: the update interval is a
runtime-editable setting (the plugin's ``nobitex_update_interval``), and a
Celery beat schedule is fixed at process start. Reading the config inside the
task keeps the interval honest without a beat restart; the tick itself costs
one indexed read of a single settings row.

The task is idempotent per run (re-running the sweep recomputes the same
prices at the same rate; nothing accumulates) and never raises for an
expected failure — the failure is recorded on the config row and in the
history, so beat does not retry into a storm when the API is down.
"""

from __future__ import annotations

import asyncio
from typing import Any

import structlog

from app.core.database.session import async_session_factory
from app.modules.currency.application import rate_config
from app.modules.currency.application.price_update_service import run_price_update
from app.worker.celery_app import celery_app

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


async def _run_scheduled_update_async() -> dict[str, Any]:
    async with async_session_factory() as db:
        config = await rate_config.get_config(db)
        if not rate_config.is_due(config):
            return {"status": "skipped", "reason": "not_due"}
        result = await run_price_update(db, scheduled=True)
        await db.commit()
        await logger.ainfo("usd_rate_scheduled_run", **result)
        return result


@celery_app.task(name="app.modules.currency.application.tasks.run_usd_rate_update")
def run_usd_rate_update() -> dict[str, Any]:
    """Tick: run the USD→Toman sweep when the configured interval has passed."""
    return asyncio.run(_run_scheduled_update_async())
