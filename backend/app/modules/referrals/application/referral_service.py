"""Referral application service – code generation, tracking, and commissions."""

from __future__ import annotations

import secrets
import uuid
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import func, select

from app.modules.referrals.domain.models import (
    CommissionStatus,
    Referral,
    ReferralCommission,
    ReferralStatus,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
logger: structlog.stdlib.BoundLogger = structlog.get_logger()

# Commission rates per level (percentage of order total)
LEVEL1_COMMISSION_RATE = 5.0  # 5%
LEVEL2_COMMISSION_RATE = 2.0  # 2%
MAX_REFERRAL_LEVEL = 2


def _generate_referral_code(length: int = 8) -> str:
    """Generate a URL-safe unique referral code."""
    return secrets.token_urlsafe(length)[:length].upper()


class ReferralService:
    """Handles referral code generation, tracking, and commission calculation."""

    # ── Referral Code ─────────────────────────────────────────────────

    @staticmethod
    async def get_or_create_referral_code(db: AsyncSession, user_id: uuid.UUID) -> str:
        """Return existing referral code for the user or create a new one."""
        stmt = select(Referral.code).where(Referral.referrer_id == user_id).limit(1)
        result = await db.execute(stmt)
        existing_code = result.scalar_one_or_none()

        if existing_code:
            return existing_code

        # Generate unique code
        for _ in range(10):
            code = _generate_referral_code()
            check = await db.execute(select(Referral.id).where(Referral.code == code).limit(1))
            if check.scalar_one_or_none() is None:
                break
        else:
            code = _generate_referral_code(12)

        await logger.ainfo("referral_code_generated", user_id=str(user_id), code=code)
        return code

    # ── Track Referral ────────────────────────────────────────────────

    @staticmethod
    async def track_referral(
        db: AsyncSession,
        referrer_id: uuid.UUID,
        referred_id: uuid.UUID,
        code: str,
    ) -> Referral:
        """Record a level-1 referral and, if applicable, a level-2 referral."""
        # Check if referred user already has a referral
        existing = await db.execute(
            select(Referral).where(Referral.referred_id == referred_id).limit(1)
        )
        if existing.scalar_one_or_none():
            await logger.awarn("referral_already_exists", referred_id=str(referred_id))
            raise ValueError("User already has a referral record.")

        # Level 1 referral
        level1 = Referral(
            referrer_id=referrer_id,
            referred_id=referred_id,
            code=code,
            level=1,
            status=ReferralStatus.PENDING,
        )
        db.add(level1)
        await db.flush()

        await logger.ainfo(
            "referral_tracked",
            referral_id=str(level1.id),
            referrer_id=str(referrer_id),
            referred_id=str(referred_id),
            level=1,
        )

        # Check for level 2: who referred the referrer?
        stmt = (
            select(Referral)
            .where(
                Referral.referred_id == referrer_id,
                Referral.level == 1,
            )
            .limit(1)
        )
        result = await db.execute(stmt)
        parent_referral = result.scalar_one_or_none()

        if parent_referral and parent_referral.referrer_id != referred_id:
            level2 = Referral(
                referrer_id=parent_referral.referrer_id,
                referred_id=referred_id,
                code=code,
                level=2,
                status=ReferralStatus.PENDING,
            )
            db.add(level2)
            await db.flush()
            await logger.ainfo(
                "referral_tracked",
                referral_id=str(level2.id),
                referrer_id=str(parent_referral.referrer_id),
                referred_id=str(referred_id),
                level=2,
            )

        return level1

    # ── Commission Calculation ────────────────────────────────────────

    @staticmethod
    async def calculate_and_credit_commission(
        db: AsyncSession,
        order_id: uuid.UUID,
        buyer_id: uuid.UUID,
        order_total: int,
    ) -> list[ReferralCommission]:
        """Calculate commissions for all referrers of a buyer on order completion."""
        stmt = select(Referral).where(
            Referral.referred_id == buyer_id,
            Referral.level <= MAX_REFERRAL_LEVEL,
        )
        result = await db.execute(stmt)
        referrals = result.scalars().all()

        commissions: list[ReferralCommission] = []
        for referral in referrals:
            rate = LEVEL1_COMMISSION_RATE if referral.level == 1 else LEVEL2_COMMISSION_RATE
            amount = int(order_total * rate / 100)
            if amount <= 0:
                continue

            commission = ReferralCommission(
                referral_id=referral.id,
                order_id=order_id,
                amount=amount,
                level=referral.level,
                status=CommissionStatus.PENDING,
            )
            db.add(commission)
            commissions.append(commission)

            # Mark referral as completed/rewarded
            if referral.status == ReferralStatus.PENDING:
                referral.status = ReferralStatus.COMPLETED

            await logger.ainfo(
                "commission_credited",
                referral_id=str(referral.id),
                order_id=str(order_id),
                amount=amount,
                level=referral.level,
            )

        await db.flush()
        return commissions

    # ── Queries ───────────────────────────────────────────────────────

    @staticmethod
    async def get_referrals(
        db: AsyncSession,
        user_id: uuid.UUID,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[Referral], int]:
        """Return paginated referrals where the user is the referrer."""
        count_stmt = (
            select(func.count()).select_from(Referral).where(Referral.referrer_id == user_id)
        )
        total = (await db.execute(count_stmt)).scalar_one()

        stmt = (
            select(Referral)
            .where(Referral.referrer_id == user_id)
            .order_by(Referral.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all()), total

    @staticmethod
    async def get_referral_stats(db: AsyncSession, user_id: uuid.UUID) -> dict[str, Any]:
        """Aggregate referral statistics for a user."""
        # Total / status counts
        stmt = select(
            func.count().label("total"),
            func.count().filter(Referral.status == ReferralStatus.COMPLETED).label("completed"),
            func.count().filter(Referral.status == ReferralStatus.PENDING).label("pending"),
            func.count().filter(Referral.level == 1).label("level1"),
            func.count().filter(Referral.level == 2).label("level2"),
        ).where(Referral.referrer_id == user_id)
        row = (await db.execute(stmt)).one()

        # Commission totals
        earned_stmt = (
            select(func.coalesce(func.sum(ReferralCommission.amount), 0))
            .join(Referral, Referral.id == ReferralCommission.referral_id)
            .where(
                Referral.referrer_id == user_id,
                ReferralCommission.status == CommissionStatus.PAID,
            )
        )
        earned = (await db.execute(earned_stmt)).scalar_one()

        pending_stmt = (
            select(func.coalesce(func.sum(ReferralCommission.amount), 0))
            .join(Referral, Referral.id == ReferralCommission.referral_id)
            .where(
                Referral.referrer_id == user_id,
                ReferralCommission.status == CommissionStatus.PENDING,
            )
        )
        pending_amount = (await db.execute(pending_stmt)).scalar_one()

        return {
            "total_referrals": row.total,
            "completed_referrals": row.completed,
            "pending_referrals": row.pending,
            "level1_count": row.level1,
            "level2_count": row.level2,
            "total_commission_earned": earned,
            "total_commission_pending": pending_amount,
        }

    @staticmethod
    async def get_commissions(
        db: AsyncSession,
        user_id: uuid.UUID,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[ReferralCommission], int]:
        """Return paginated commissions for a referrer."""
        base = (
            select(ReferralCommission)
            .join(Referral, Referral.id == ReferralCommission.referral_id)
            .where(Referral.referrer_id == user_id)
        )

        count_stmt = select(func.count()).select_from(base.subquery())
        total = (await db.execute(count_stmt)).scalar_one()

        stmt = base.order_by(ReferralCommission.created_at.desc()).offset(skip).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all()), total
