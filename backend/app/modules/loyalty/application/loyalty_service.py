"""Loyalty application service – points earn/redeem and tier management."""

from __future__ import annotations

import uuid
from typing import Any, Optional

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.loyalty.domain.models import (
    LoyaltyAccount,
    LoyaltyTier,
    LoyaltyTransaction,
    LoyaltyTransactionType,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger()

# Tier thresholds (cumulative earned points)
TIER_THRESHOLDS: dict[LoyaltyTier, int] = {
    LoyaltyTier.BRONZE: 0,
    LoyaltyTier.SILVER: 500,
    LoyaltyTier.GOLD: 2000,
    LoyaltyTier.PLATINUM: 5000,
}

TIER_BENEFITS: dict[LoyaltyTier, list[str]] = {
    LoyaltyTier.BRONZE: ["Basic member benefits"],
    LoyaltyTier.SILVER: ["5% bonus points", "Priority support"],
    LoyaltyTier.GOLD: ["10% bonus points", "Free shipping", "Exclusive offers"],
    LoyaltyTier.PLATINUM: [
        "15% bonus points",
        "Free express shipping",
        "VIP support",
        "Early access to sales",
    ],
}


def _calculate_tier(total_earned: int) -> LoyaltyTier:
    """Determine the tier based on total earned points."""
    tier = LoyaltyTier.BRONZE
    for t, threshold in TIER_THRESHOLDS.items():
        if total_earned >= threshold:
            tier = t
    return tier


class LoyaltyService:
    """Manages loyalty accounts, points, and tier upgrades."""

    # ── Account Management ────────────────────────────────────────────

    @staticmethod
    async def get_or_create_account(
        db: AsyncSession, user_id: uuid.UUID
    ) -> LoyaltyAccount:
        """Get or create a loyalty account for a user."""
        stmt = select(LoyaltyAccount).where(LoyaltyAccount.user_id == user_id)
        result = await db.execute(stmt)
        account = result.scalar_one_or_none()

        if account:
            return account

        account = LoyaltyAccount(
            user_id=user_id,
            points=0,
            tier=LoyaltyTier.BRONZE,
        )
        db.add(account)
        await db.flush()
        await logger.ainfo("loyalty_account_created", user_id=str(user_id))
        return account

    # ── Earn Points ───────────────────────────────────────────────────

    @staticmethod
    async def earn_points(
        db: AsyncSession,
        user_id: uuid.UUID,
        points: int,
        reference_type: Optional[str] = None,
        reference_id: Optional[uuid.UUID] = None,
        description: Optional[str] = None,
    ) -> tuple[LoyaltyTransaction, LoyaltyAccount]:
        """Add points to a user's loyalty account and recalculate tier."""
        account = await LoyaltyService.get_or_create_account(db, user_id)

        account.points += points

        transaction = LoyaltyTransaction(
            account_id=account.id,
            points=points,
            type=LoyaltyTransactionType.EARN,
            reference_type=reference_type,
            reference_id=reference_id,
            description=description or f"Earned {points} points",
        )
        db.add(transaction)

        # Recalculate tier
        total_earned = await LoyaltyService._get_total_earned(db, account.id)
        new_tier = _calculate_tier(total_earned + points)
        old_tier = account.tier
        if new_tier != old_tier:
            account.tier = new_tier
            await logger.ainfo(
                "loyalty_tier_upgraded",
                user_id=str(user_id),
                old_tier=old_tier.value,
                new_tier=new_tier.value,
            )

        await db.flush()
        await logger.ainfo(
            "loyalty_points_earned",
            user_id=str(user_id),
            points=points,
            new_balance=account.points,
        )
        return transaction, account

    # ── Redeem Points ─────────────────────────────────────────────────

    @staticmethod
    async def redeem_points(
        db: AsyncSession,
        user_id: uuid.UUID,
        points: int,
        reference_type: Optional[str] = None,
        reference_id: Optional[uuid.UUID] = None,
        description: Optional[str] = None,
    ) -> tuple[LoyaltyTransaction, LoyaltyAccount]:
        """Deduct points from a user's loyalty account."""
        account = await LoyaltyService.get_or_create_account(db, user_id)

        if account.points < points:
            raise ValueError(
                f"Insufficient points. Available: {account.points}, requested: {points}"
            )

        account.points -= points

        transaction = LoyaltyTransaction(
            account_id=account.id,
            points=-points,
            type=LoyaltyTransactionType.REDEEM,
            reference_type=reference_type,
            reference_id=reference_id,
            description=description or f"Redeemed {points} points",
        )
        db.add(transaction)
        await db.flush()

        await logger.ainfo(
            "loyalty_points_redeemed",
            user_id=str(user_id),
            points=points,
            new_balance=account.points,
        )
        return transaction, account

    # ── Queries ───────────────────────────────────────────────────────

    @staticmethod
    async def get_transactions(
        db: AsyncSession,
        user_id: uuid.UUID,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[LoyaltyTransaction], int]:
        """Return paginated loyalty transactions for a user."""
        account = await LoyaltyService.get_or_create_account(db, user_id)

        count_stmt = (
            select(func.count())
            .select_from(LoyaltyTransaction)
            .where(LoyaltyTransaction.account_id == account.id)
        )
        total = (await db.execute(count_stmt)).scalar_one()

        stmt = (
            select(LoyaltyTransaction)
            .where(LoyaltyTransaction.account_id == account.id)
            .order_by(LoyaltyTransaction.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all()), total

    @staticmethod
    async def get_tier_info() -> list[dict[str, Any]]:
        """Return tier information with thresholds and benefits."""
        return [
            {
                "tier": tier,
                "min_points": TIER_THRESHOLDS[tier],
                "benefits": TIER_BENEFITS[tier],
            }
            for tier in LoyaltyTier
        ]

    # ── Internal helpers ──────────────────────────────────────────────

    @staticmethod
    async def _get_total_earned(db: AsyncSession, account_id: uuid.UUID) -> int:
        """Get total earned points for tier calculation."""
        stmt = select(
            func.coalesce(func.sum(LoyaltyTransaction.points), 0)
        ).where(
            LoyaltyTransaction.account_id == account_id,
            LoyaltyTransaction.type == LoyaltyTransactionType.EARN,
        )
        result = await db.execute(stmt)
        return result.scalar_one()
