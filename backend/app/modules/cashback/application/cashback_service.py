"""Cashback application service – rule management and cashback calculation."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import func, select

from app.modules.cashback.domain.models import (
    CashbackRule,
    CashbackRuleType,
    CashbackTransaction,
    CashbackTransactionStatus,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
logger: structlog.stdlib.BoundLogger = structlog.get_logger()


class CashbackService:
    """Manages cashback rules and calculates cashback on order completion."""

    # ── Admin CRUD ────────────────────────────────────────────────────

    @staticmethod
    async def create_rule(
        db: AsyncSession,
        *,
        name: str,
        type: CashbackRuleType,  # noqa: A002  # API parameter name is the public contract
        scope_id: str | None,
        percentage: float,
        max_amount: int | None,
        is_active: bool,
        starts_at: datetime,
        ends_at: datetime,
    ) -> CashbackRule:
        """Create a new cashback rule."""
        rule = CashbackRule(
            name=name,
            type=type,
            scope_id=scope_id,
            percentage=percentage,
            max_amount=max_amount,
            is_active=is_active,
            starts_at=starts_at,
            ends_at=ends_at,
        )
        db.add(rule)
        await db.flush()
        await logger.ainfo("cashback_rule_created", rule_id=str(rule.id), name=name)
        return rule

    @staticmethod
    async def update_rule(
        db: AsyncSession,
        rule_id: uuid.UUID,
        **updates: Any,
    ) -> CashbackRule:
        """Update an existing cashback rule."""
        stmt = select(CashbackRule).where(CashbackRule.id == rule_id)
        result = await db.execute(stmt)
        rule = result.scalar_one_or_none()
        if not rule:
            raise ValueError(f"Cashback rule {rule_id} not found.")

        clean = {k: v for k, v in updates.items() if v is not None}
        for key, value in clean.items():
            setattr(rule, key, value)

        await db.flush()
        await logger.ainfo("cashback_rule_updated", rule_id=str(rule_id))
        return rule

    @staticmethod
    async def delete_rule(db: AsyncSession, rule_id: uuid.UUID) -> None:
        """Soft-delete a cashback rule by deactivating it."""
        stmt = select(CashbackRule).where(CashbackRule.id == rule_id)
        result = await db.execute(stmt)
        rule = result.scalar_one_or_none()
        if not rule:
            raise ValueError(f"Cashback rule {rule_id} not found.")
        rule.is_active = False
        await db.flush()
        await logger.ainfo("cashback_rule_deactivated", rule_id=str(rule_id))

    @staticmethod
    async def get_rule(db: AsyncSession, rule_id: uuid.UUID) -> CashbackRule | None:
        """Get a single cashback rule by ID."""
        stmt = select(CashbackRule).where(CashbackRule.id == rule_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def list_rules(
        db: AsyncSession,
        *,
        is_active: bool | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[CashbackRule], int]:
        """Return paginated cashback rules."""
        base = select(CashbackRule)
        count_base = select(func.count()).select_from(CashbackRule)

        if is_active is not None:
            base = base.where(CashbackRule.is_active == is_active)
            count_base = count_base.where(CashbackRule.is_active == is_active)

        total = (await db.execute(count_base)).scalar_one()
        stmt = base.order_by(CashbackRule.created_at.desc()).offset(skip).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all()), total

    # ── Cashback Calculation ──────────────────────────────────────────

    @staticmethod
    async def calculate_cashback(
        db: AsyncSession,
        *,
        user_id: uuid.UUID,
        order_id: uuid.UUID,
        order_total: int,
        payment_method: str | None = None,
        category_ids: list[str] | None = None,
        product_ids: list[str] | None = None,
    ) -> tuple[int, int]:
        """Calculate and credit cashback for an order.

        Returns (total_cashback_amount, number_of_transactions_created).
        """
        now = datetime.now(UTC)

        stmt = select(CashbackRule).where(
            CashbackRule.is_active.is_(True),
            CashbackRule.starts_at <= now,
            CashbackRule.ends_at >= now,
        )
        result = await db.execute(stmt)
        rules = result.scalars().all()

        total_cashback = 0
        count = 0

        for rule in rules:
            matched = False

            if rule.type == CashbackRuleType.CAMPAIGN:
                matched = True
            elif rule.type == CashbackRuleType.PAYMENT_METHOD and payment_method:
                matched = rule.scope_id == payment_method
            elif rule.type == CashbackRuleType.CATEGORY and category_ids:
                matched = rule.scope_id in category_ids
            elif rule.type == CashbackRuleType.PRODUCT and product_ids:
                matched = rule.scope_id in product_ids

            if not matched:
                continue

            amount = int(order_total * rule.percentage / 100)
            if rule.max_amount and amount > rule.max_amount:
                amount = rule.max_amount

            if amount <= 0:
                continue

            transaction = CashbackTransaction(
                user_id=user_id,
                order_id=order_id,
                rule_id=rule.id,
                amount=amount,
                status=CashbackTransactionStatus.PENDING,
            )
            db.add(transaction)
            total_cashback += amount
            count += 1

            await logger.ainfo(
                "cashback_calculated",
                user_id=str(user_id),
                order_id=str(order_id),
                rule_id=str(rule.id),
                amount=amount,
            )

        await db.flush()
        return total_cashback, count

    # ── Credit to wallet ──────────────────────────────────────────────

    @staticmethod
    async def credit_pending_cashback(db: AsyncSession, user_id: uuid.UUID) -> int:
        """Credit all pending cashback transactions for a user to their wallet.

        Returns the total amount credited. Actual wallet crediting should
        be performed by the wallet service; this method marks transactions
        as credited and returns the amount.
        """
        stmt = select(CashbackTransaction).where(
            CashbackTransaction.user_id == user_id,
            CashbackTransaction.status == CashbackTransactionStatus.PENDING,
        )
        result = await db.execute(stmt)
        transactions = result.scalars().all()

        total = 0
        for txn in transactions:
            txn.status = CashbackTransactionStatus.CREDITED
            total += txn.amount

        await db.flush()
        await logger.ainfo(
            "cashback_credited",
            user_id=str(user_id),
            total=total,
            count=len(transactions),
        )
        return total

    # ── User Queries ──────────────────────────────────────────────────

    @staticmethod
    async def get_user_transactions(
        db: AsyncSession,
        user_id: uuid.UUID,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[CashbackTransaction], int]:
        """Return paginated cashback transactions for a user."""
        count_stmt = (
            select(func.count())
            .select_from(CashbackTransaction)
            .where(CashbackTransaction.user_id == user_id)
        )
        total = (await db.execute(count_stmt)).scalar_one()

        stmt = (
            select(CashbackTransaction)
            .where(CashbackTransaction.user_id == user_id)
            .order_by(CashbackTransaction.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all()), total
