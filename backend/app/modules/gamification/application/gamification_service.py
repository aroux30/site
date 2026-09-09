"""Gamification application service.

Manages gamification rules, evaluates user events, awards points,
integrates with the loyalty program, and handles reward redemptions.
"""

import uuid
from typing import Any

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.gamification.domain.models import (
    GamificationEvent,
    GamificationRule,
    Reward,
)
from app.modules.gamification.schemas.gamification import (
    ClaimRewardResponse,
    GamificationRuleCreate,
    GamificationRuleUpdate,
    RewardCreate,
    RewardUpdate,
)
from app.modules.loyalty.application.loyalty_service import LoyaltyService
from app.modules.loyalty.domain.models import LoyaltyTransaction, LoyaltyTransactionType

logger: structlog.stdlib.BoundLogger = structlog.get_logger()


def _matches_conditions(
    conditions: dict[str, Any] | None,
    event_data: dict[str, Any] | None,
) -> bool:
    """Evaluate whether the rule conditions match the provided event_data.

    Supports:
    - None or empty conditions -> matches unconditionally
    - Direct key-value equality
    - Prefix-based comparison: 'min_<key>', 'max_<key>'
    - Operator dicts: {'gte': X, 'lte': Y, 'gt': X, 'lt': Y, 'eq': X, 'in': [...]}
    """
    if not conditions:
        return True

    if not event_data or not isinstance(event_data, dict):
        return False

    for cond_key, expected_val in conditions.items():
        if cond_key.startswith("min_"):
            field = cond_key[4:]
            actual = event_data.get(field, event_data.get(cond_key))
            if actual is None or actual < expected_val:
                return False
        elif cond_key.startswith("max_"):
            field = cond_key[4:]
            actual = event_data.get(field, event_data.get(cond_key))
            if actual is None or actual > expected_val:
                return False
        elif isinstance(expected_val, dict):
            actual = event_data.get(cond_key)
            for op, target in expected_val.items():
                if op in ("gte", ">="):
                    if actual is None or actual < target:
                        return False
                elif op in ("gt", ">"):
                    if actual is None or actual <= target:
                        return False
                elif op in ("lte", "<="):
                    if actual is None or actual > target:
                        return False
                elif op in ("lt", "<"):
                    if actual is None or actual >= target:
                        return False
                elif op in ("eq", "=="):
                    if actual != target:
                        return False
                elif op in ("in",) and actual not in target:
                    return False
        else:
            if event_data.get(cond_key) != expected_val:
                return False

    return True


class GamificationService:
    """Gamification business logic service."""

    # -----------------------------------------------------------------------
    # Points Awarding & Event Processing
    # -----------------------------------------------------------------------

    @staticmethod
    async def award_points_for_event(
        db: AsyncSession,
        user_id: uuid.UUID,
        event_type: str,
        event_data: dict[str, Any] | None = None,
    ) -> list[GamificationEvent]:
        """Check matching active rules, award points, record events, and credit loyalty points."""
        stmt = select(GamificationRule).where(
            GamificationRule.event_type == event_type,
            GamificationRule.is_active.is_(True),
        )
        result = await db.execute(stmt)
        rules = list(result.scalars().all())

        matching_rules = [
            rule for rule in rules if _matches_conditions(rule.conditions, event_data)
        ]

        recorded_events: list[GamificationEvent] = []

        for rule in matching_rules:
            event = GamificationEvent(
                user_id=user_id,
                rule_id=rule.id,
                points_earned=rule.points,
                event_data=event_data,
            )
            event.rule = rule
            db.add(event)
            await db.flush()

            # Credit loyalty account and record movement
            await LoyaltyService.earn_points(
                db,
                user_id=user_id,
                points=rule.points,
                reference_type="gamification_event",
                reference_id=event.id,
                description=f"Gamification rule: {rule.name}",
            )

            recorded_events.append(event)
            await logger.ainfo(
                "gamification_points_awarded",
                user_id=str(user_id),
                rule_id=str(rule.id),
                points=rule.points,
                event_type=event_type,
            )

        return recorded_events

    # -----------------------------------------------------------------------
    # User Points & Summary
    # -----------------------------------------------------------------------

    @staticmethod
    async def get_user_points(
        db: AsyncSession,
        user_id: uuid.UUID,
    ) -> dict[str, Any]:
        """Calculate total earned points, spent points, available points, and rank."""
        account = await LoyaltyService.get_or_create_account(db, user_id)

        # Gamification events points earned
        event_stmt = select(
            func.coalesce(func.sum(GamificationEvent.points_earned), 0)
        ).where(GamificationEvent.user_id == user_id)
        gamification_earned: int = (await db.execute(event_stmt)).scalar_one()

        # Loyalty transaction metrics
        earned_stmt = select(
            func.coalesce(func.sum(LoyaltyTransaction.points), 0)
        ).where(
            LoyaltyTransaction.account_id == account.id,
            LoyaltyTransaction.type == LoyaltyTransactionType.EARN,
        )
        loyalty_earned: int = (await db.execute(earned_stmt)).scalar_one()

        spent_stmt = select(
            func.coalesce(func.sum(func.abs(LoyaltyTransaction.points)), 0)
        ).where(
            LoyaltyTransaction.account_id == account.id,
            LoyaltyTransaction.type == LoyaltyTransactionType.REDEEM,
        )
        points_spent: int = (await db.execute(spent_stmt)).scalar_one()

        total_earned = max(gamification_earned, loyalty_earned)
        points_available = account.points
        rank = account.tier.value

        return {
            "total_points_earned": total_earned,
            "total_earned": total_earned,
            "points_spent": points_spent,
            "points_available": points_available,
            "available_points": points_available,
            "rank": rank,
        }

    # -----------------------------------------------------------------------
    # Reward Claiming
    # -----------------------------------------------------------------------

    @staticmethod
    async def claim_reward(
        db: AsyncSession,
        user_id: uuid.UUID,
        reward_id: uuid.UUID,
    ) -> ClaimRewardResponse:
        """Validate points requirement, decrement quantity, and record redemption."""
        stmt = select(Reward).where(Reward.id == reward_id).with_for_update()
        result = await db.execute(stmt)
        reward = result.scalar_one_or_none()

        if not reward:
            raise ValueError(f"Reward not found: {reward_id}")

        if not reward.is_active:
            raise ValueError("Reward is not currently active")

        if reward.quantity_available is not None and reward.quantity_available <= 0:
            raise ValueError("Reward is out of stock")

        # Redeem points from user loyalty account (raises ValueError if insufficient)
        transaction, account = await LoyaltyService.redeem_points(
            db,
            user_id=user_id,
            points=reward.points_required,
            reference_type="reward_claim",
            reference_id=reward.id,
            description=f"Claimed reward: {reward.name}",
        )

        # Decrement quantity if tracked
        if reward.quantity_available is not None:
            reward.quantity_available -= 1

        await db.flush()

        await logger.ainfo(
            "reward_claimed",
            user_id=str(user_id),
            reward_id=str(reward.id),
            points_spent=reward.points_required,
            remaining_points=account.points,
        )

        return ClaimRewardResponse(
            reward_id=reward.id,
            reward_name=reward.name,
            points_spent=reward.points_required,
            remaining_points=account.points,
            claimed_at=transaction.created_at,
            message=f"Successfully claimed reward '{reward.name}'",
        )

    # -----------------------------------------------------------------------
    # Rewards Querying
    # -----------------------------------------------------------------------

    @staticmethod
    async def list_rewards(
        db: AsyncSession,
        active_only: bool = True,
        skip: int = 0,
        limit: int | None = None,
    ) -> list[Reward]:
        """List rewards, optionally filtering for active only."""
        stmt = select(Reward)
        if active_only:
            stmt = stmt.where(Reward.is_active.is_(True))
        stmt = stmt.order_by(Reward.points_required.asc(), Reward.created_at.desc())

        if skip:
            stmt = stmt.offset(skip)
        if limit is not None:
            stmt = stmt.limit(limit)

        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_reward(
        db: AsyncSession,
        reward_id: uuid.UUID,
    ) -> Reward | None:
        """Fetch a single reward by its ID."""
        return await db.get(Reward, reward_id)

    # -----------------------------------------------------------------------
    # History
    # -----------------------------------------------------------------------

    @staticmethod
    async def get_user_history(
        db: AsyncSession,
        user_id: uuid.UUID,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[GamificationEvent], int]:
        """Return paginated gamification event history for a user."""
        count_stmt = (
            select(func.count())
            .select_from(GamificationEvent)
            .where(GamificationEvent.user_id == user_id)
        )
        total = (await db.execute(count_stmt)).scalar_one()

        stmt = (
            select(GamificationEvent)
            .options(selectinload(GamificationEvent.rule))
            .where(GamificationEvent.user_id == user_id)
            .order_by(GamificationEvent.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await db.execute(stmt)
        events = list(result.scalars().all())
        for event in events:
            if event.rule:
                event.rule_name = event.rule.name
        return events, total

    # -----------------------------------------------------------------------
    # Admin Rewards Management
    # -----------------------------------------------------------------------

    @staticmethod
    async def admin_create_reward(
        db: AsyncSession,
        data: RewardCreate | dict[str, Any],
    ) -> Reward:
        """Create a new redeemable reward (admin)."""
        payload = (
            data.model_dump(exclude_unset=True)
            if isinstance(data, RewardCreate)
            else dict(data)
        )
        reward = Reward(**payload)
        db.add(reward)
        await db.flush()
        await logger.ainfo("reward_created", reward_id=str(reward.id), name=reward.name)
        return reward

    @staticmethod
    async def admin_update_reward(
        db: AsyncSession,
        reward_id: uuid.UUID,
        data: RewardUpdate | dict[str, Any],
    ) -> Reward:
        """Update an existing reward (admin)."""
        reward = await db.get(Reward, reward_id)
        if not reward:
            raise ValueError(f"Reward not found: {reward_id}")

        updates = (
            data.model_dump(exclude_unset=True)
            if isinstance(data, RewardUpdate)
            else dict(data)
        )
        for key, value in updates.items():
            if hasattr(reward, key) and value is not None:
                setattr(reward, key, value)

        await db.flush()
        await logger.ainfo("reward_updated", reward_id=str(reward_id))
        return reward

    # -----------------------------------------------------------------------
    # Admin Rules Management
    # -----------------------------------------------------------------------

    @staticmethod
    async def admin_create_rule(
        db: AsyncSession,
        data: GamificationRuleCreate | dict[str, Any],
    ) -> GamificationRule:
        """Create a new gamification rule (admin)."""
        payload = (
            data.model_dump(exclude_unset=True)
            if isinstance(data, GamificationRuleCreate)
            else dict(data)
        )
        rule = GamificationRule(**payload)
        db.add(rule)
        await db.flush()
        await logger.ainfo(
            "gamification_rule_created",
            rule_id=str(rule.id),
            name=rule.name,
            event_type=rule.event_type,
        )
        return rule

    @staticmethod
    async def admin_update_rule(
        db: AsyncSession,
        rule_id: uuid.UUID,
        data: GamificationRuleUpdate | dict[str, Any],
    ) -> GamificationRule:
        """Update an existing gamification rule (admin)."""
        rule = await db.get(GamificationRule, rule_id)
        if not rule:
            raise ValueError(f"Gamification rule not found: {rule_id}")

        updates = (
            data.model_dump(exclude_unset=True)
            if isinstance(data, GamificationRuleUpdate)
            else dict(data)
        )
        for key, value in updates.items():
            if hasattr(rule, key) and value is not None:
                setattr(rule, key, value)

        await db.flush()
        await logger.ainfo("gamification_rule_updated", rule_id=str(rule_id))
        return rule

    @staticmethod
    async def admin_list_rules(
        db: AsyncSession,
        is_active: bool | None = None,
        skip: int = 0,
        limit: int | None = None,
    ) -> list[GamificationRule]:
        """List gamification rules with optional active filtering (admin)."""
        stmt = select(GamificationRule)
        if is_active is not None:
            stmt = stmt.where(GamificationRule.is_active.is_(is_active))
        stmt = stmt.order_by(GamificationRule.created_at.desc())

        if skip:
            stmt = stmt.offset(skip)
        if limit is not None:
            stmt = stmt.limit(limit)

        result = await db.execute(stmt)
        return list(result.scalars().all())


# Top-level functional aliases matching requested signatures
award_points_for_event = GamificationService.award_points_for_event
get_user_points = GamificationService.get_user_points
claim_reward = GamificationService.claim_reward
list_rewards = GamificationService.list_rewards
admin_create_reward = GamificationService.admin_create_reward
admin_update_reward = GamificationService.admin_update_reward
admin_create_rule = GamificationService.admin_create_rule
admin_list_rules = GamificationService.admin_list_rules
