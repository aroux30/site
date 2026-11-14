"""Referral & bonus reward background tasks.

One sweep does all four payout passes (commission creation, commission
payout, signup gifts, recharge-bonus catch-up). Every pass is idempotent —
the wallet partial unique index and the per-order unique constraint are the
at-most-once backstops, and anything unpaid stays PENDING for the next run
(at-least-once).
"""

from __future__ import annotations

import asyncio
from typing import Any

import structlog

from app.core.database.session import async_session_factory
from app.modules.referrals.application.referral_service import ReferralService
from app.worker.celery_app import celery_app

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


async def _process_referral_rewards_async() -> dict[str, Any]:
    async with async_session_factory() as db:
        try:
            result = await ReferralService.run_reward_sweep(db)
            await db.commit()
            await logger.ainfo("referral_reward_sweep_done", **result)
            return {"status": "success", **result}
        except Exception:
            await db.rollback()
            await logger.aexception("referral_reward_sweep_failed")
            raise


@celery_app.task(
    name="app.modules.referrals.application.tasks.process_referral_rewards",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    max_retries=3,
)
def process_referral_rewards() -> dict[str, Any]:
    """Sweep pending referral/bonus rewards: create commissions, pay out,
    settle signup gifts, and catch up missed recharge bonuses."""
    return asyncio.run(_process_referral_rewards_async())
