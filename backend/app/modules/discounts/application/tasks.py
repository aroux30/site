"""Discount and coupon background Celery tasks."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any, cast

import structlog
from sqlalchemy import CursorResult, update

from app.core.database.session import async_session_factory
from app.modules.discounts.domain.models import Coupon, Discount
from app.worker.celery_app import celery_app

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


async def _expire_discount_codes_async() -> dict[str, Any]:
    """Deactivate discounts and coupons that have passed their ends_at date."""
    now = datetime.now(UTC)

    async with async_session_factory() as db:
        try:
            # Deactivate expired discounts
            disc_stmt = (
                update(Discount)
                .where(
                    Discount.is_active.is_(True),
                    Discount.ends_at <= now,
                )
                .values(is_active=False)
            )
            disc_res = cast("CursorResult[Any]", await db.execute(disc_stmt))
            expired_discounts = int(disc_res.rowcount or 0)

            # Deactivate expired coupons
            coup_stmt = (
                update(Coupon)
                .where(
                    Coupon.is_active.is_(True),
                    Coupon.ends_at <= now,
                )
                .values(is_active=False)
            )
            coup_res = cast("CursorResult[Any]", await db.execute(coup_stmt))
            expired_coupons = int(coup_res.rowcount or 0)

            await db.commit()
            await logger.ainfo(
                "discounts_expired_check_complete",
                expired_discounts=expired_discounts,
                expired_coupons=expired_coupons,
            )
            return {
                "status": "success",
                "expired_discounts": expired_discounts,
                "expired_coupons": expired_coupons,
            }
        except Exception as exc:
            await db.rollback()
            await logger.aerror("discounts_expired_check_failed", error=str(exc))
            return {"status": "error", "message": str(exc)}


# Retry policy (audit R5): this task is idempotent (re-running cannot
# duplicate money movement or state transitions), so transient
# DB/Elasticsearch/Redis errors are retried with exponential backoff.
@celery_app.task(
    name="app.modules.discounts.application.tasks.expire_discount_codes",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=5,
)
def expire_discount_codes() -> dict[str, Any]:
    """Celery beat task entrypoint for expiring discount codes."""
    return asyncio.run(_expire_discount_codes_async())
