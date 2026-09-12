"""Lucky Wheel and Welcome Signup Gift service (Karta Phase 5/7).

Implements:
- Post-purchase gamified lucky box with weighted probability draw using CSPRNG (secrets)
- Welcome signup gift credit awarded upon initial phone verification (Karta signup_gift)
- Atomic 1-spin-per-order enforcement via database constraints (Karta try_gifts)
"""

from __future__ import annotations

import secrets
import uuid
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.exceptions.handlers import ConflictError, NotFoundError
from app.modules.gamification.domain.gift_models import (
    GiftTryLog,
    LuckyWheelPrize,
    PrizeType,
)
from app.modules.orders.domain.models import Order, OrderStatus
from app.modules.users.domain.models import User
from app.modules.wallet.application import wallet_service
from app.modules.wallet.domain.models import WalletTransactionType

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


def _secure_weighted_choice(prizes: list[LuckyWheelPrize]) -> LuckyWheelPrize:
    """Perform cryptographically secure weighted random choice using secrets module."""
    total_weight = sum(max(1, p.probability_weight) for p in prizes)
    rand_val = secrets.randbelow(total_weight)
    cumulative = 0
    for p in prizes:
        cumulative += max(1, p.probability_weight)
        if rand_val < cumulative:
            return p
    return prizes[-1]


async def spin_lucky_wheel_for_order(
    db: AsyncSession,
    user_id: uuid.UUID,
    order_id: uuid.UUID,
) -> dict[str, Any]:
    """Execute lucky wheel draw for a completed order with atomic 1-spin enforcement."""
    safe_user_id = uuid.UUID(str(user_id))
    safe_order_id = uuid.UUID(str(order_id))

    order = await db.get(Order, safe_order_id)
    if order is None:
        raise NotFoundError(resource="Order", detail="سفارش مورد نظر یافت نشد")

    if order.status != OrderStatus.COMPLETED:
        raise ConflictError(detail="گردونه شانس فقط پس از تکمیل و پرداخت موفق سفارش فعال می‌شود")

    prizes_stmt = select(LuckyWheelPrize).where(LuckyWheelPrize.is_active.is_(True))
    prizes = list((await db.execute(prizes_stmt)).scalars().all())

    if not prizes:
        prize_title = "متأسفانه این بار برنده نشدید"
        prize_type = PrizeType.NOTHING.value
        awarded_value = 0
        prize_id = None
    else:
        chosen = _secure_weighted_choice(prizes)
        prize_id = chosen.id
        prize_title = chosen.title
        prize_type = chosen.prize_type.value
        awarded_value = chosen.value

        chosen.claimed_count += 1
        if chosen.max_claims_total and chosen.claimed_count >= chosen.max_claims_total:
            chosen.is_active = False

    # Award prize if wallet credit
    if prize_type == PrizeType.WALLET_CREDIT.value and awarded_value > 0:
        await wallet_service.credit(
            db,
            user_id=safe_user_id,
            amount=awarded_value,
            tx_type=WalletTransactionType.BONUS,
            reference_type="lucky_wheel",
            reference_id=prize_id,
            description=f"جایزه گردونه شانس برای سفارش {order.order_number}",
        )

    log = GiftTryLog(
        user_id=safe_user_id,
        order_id=safe_order_id,
        prize_id=prize_id,
        prize_title=prize_title,
        prize_type=prize_type,
        awarded_value=awarded_value,
    )

    try:
        async with db.begin_nested():
            db.add(log)
            await db.flush()
    except IntegrityError as exc:
        raise ConflictError(detail="شما قبلاً شانس خود را برای این سفارش امتحان کرده‌اید") from exc

    await logger.ainfo("lucky_wheel_spun", order_id=str(safe_order_id), prize=prize_title, value=awarded_value)

    return {
        "order_id": safe_order_id,
        "prize_title": prize_title,
        "prize_type": prize_type,
        "awarded_value": awarded_value,
        "message": f"تبریک! شما برنده {prize_title} شدید" if prize_type != "nothing" else prize_title,
    }


async def apply_signup_gift(
    db: AsyncSession,
    user_id: uuid.UUID,
    gift_amount: int = 100_000,
) -> dict[str, Any]:
    """Award welcome bonus credit to user wallet upon initial phone verification."""
    safe_user_id = uuid.UUID(str(user_id))
    user = await db.get(User, safe_user_id)
    if user is None:
        raise NotFoundError(resource="User", detail=f"User {safe_user_id} not found")

    await wallet_service.get_or_create_wallet(db, safe_user_id)

    # Award welcome bonus credit via wallet ledger
    tx = await wallet_service.credit(
        db,
        user_id=safe_user_id,
        amount=gift_amount,
        tx_type=WalletTransactionType.BONUS,
        reference_type="signup_gift",
        reference_id=user.id,
        description="هدیه ثبت‌نام و فعال‌سازی حساب کاربری",
    )

    await logger.ainfo("signup_gift_awarded", user_id=str(safe_user_id), amount=gift_amount)
    return {
        "user_id": safe_user_id,
        "awarded_amount": gift_amount,
        "transaction_id": tx.id,
        "new_balance": tx.balance_after,
    }
