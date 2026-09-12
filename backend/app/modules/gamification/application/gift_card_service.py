"""Internal gift cards and charge packages service (Karta Phase 5/7).

Implements:
- Gift voucher issuance with graphic templates (gold, birthday, vip)
- Direct redemption into digital wallet ledger balance (Karta Gift Cards)
- Incentive charge packages with bonus credit (Karta charge_packages)
"""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import select

from app.core.exceptions.handlers import ConflictError, NotFoundError, ValidationError
from app.modules.gamification.domain.gift_models import ChargePackage, InternalGiftCard
from app.modules.wallet.application import wallet_service
from app.modules.wallet.domain.models import WalletTransactionType

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


async def issue_internal_gift_card(
    db: AsyncSession,
    amount: int,
    card_template: str = "gold",
    sender_name: str | None = None,
    recipient_email: str | None = None,
    recipient_phone: str | None = None,
    message: str | None = None,
    created_by_user_id: uuid.UUID | None = None,
    expires_at: datetime | None = None,
) -> InternalGiftCard:
    """Generate and issue a unique digital gift card."""
    if amount <= 0:
        raise ValidationError("مبلغ کارت هدیه باید بزرگتر از صفر باشد")

    code = f"GIFT-{datetime.now(UTC).year}-{secrets.token_hex(2).upper()}-{secrets.token_hex(2).upper()}"
    safe_creator = uuid.UUID(str(created_by_user_id)) if created_by_user_id else None

    card = InternalGiftCard(
        code=code,
        amount=amount,
        remaining_balance=amount,
        card_template=card_template.strip().lower(),
        sender_name=sender_name,
        recipient_email=recipient_email,
        recipient_phone=recipient_phone,
        message=message,
        is_active=True,
        created_by_user_id=safe_creator,
        expires_at=expires_at,
    )
    db.add(card)
    await db.flush()

    await logger.ainfo("gift_card_issued", code=code, amount=amount)
    return card


async def redeem_internal_gift_card(
    db: AsyncSession,
    user_id: uuid.UUID,
    code: str,
) -> dict[str, Any]:
    """Redeem gift card voucher and credit balance directly to user wallet."""
    safe_user_id = uuid.UUID(str(user_id))
    clean_code = code.strip().upper()

    stmt = select(InternalGiftCard).where(InternalGiftCard.is_active.is_(True))
    active_cards = list((await db.execute(stmt)).scalars().all())
    card = next((c for c in active_cards if c.code == clean_code), None)

    if card is None:
        raise NotFoundError(resource="InternalGiftCard", detail="کد کارت هدیه نامعتبر است یا قبلاً استفاده شده است")

    now = datetime.now(UTC)
    if card.expires_at and card.expires_at < now:
        raise ValidationError("اعتبار این کارت هدیه منقضی شده است")

    if card.remaining_balance <= 0 or card.claimed_by_user_id is not None:
        raise ConflictError(detail="این کارت هدیه قبلاً استفاده شده است")

    amount_to_credit = card.remaining_balance

    # Credit user's wallet via wallet_service ledger
    await wallet_service.credit(
        db,
        user_id=safe_user_id,
        amount=amount_to_credit,
        tx_type=WalletTransactionType.BONUS,
        reference_type="gift_card",
        reference_id=card.id,
        description=f"شارژ کیف‌پول از طریق کارت هدیه {card.code}",
    )

    # Mark card claimed
    card.remaining_balance = 0
    card.is_active = False
    card.claimed_by_user_id = safe_user_id
    card.claimed_at = now

    await db.flush()
    await logger.ainfo("gift_card_redeemed", code=card.code, user_id=str(safe_user_id), amount=amount_to_credit)

    return {
        "code": card.code,
        "amount_credited": amount_to_credit,
        "claimed_at": card.claimed_at,
    }


async def list_active_charge_packages(
    db: AsyncSession,
) -> list[ChargePackage]:
    """List pre-configured wallet top-up packages ordered by priority."""
    stmt = (
        select(ChargePackage)
        .where(ChargePackage.is_active.is_(True))
        .order_by(ChargePackage.ordering.asc())
    )
    return list((await db.execute(stmt)).scalars().all())


async def create_charge_package(
    db: AsyncSession,
    title: str,
    pay_amount: int,
    credit_amount: int,
    ordering: int = 0,
) -> ChargePackage:
    """Create a new incentive wallet top-up package."""
    pkg = ChargePackage(
        title=title.strip(),
        pay_amount=pay_amount,
        credit_amount=credit_amount,
        is_active=True,
        ordering=ordering,
    )
    db.add(pkg)
    await db.flush()
    return pkg
