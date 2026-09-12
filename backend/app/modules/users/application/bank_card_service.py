"""Bank card registration and gateway anti-phishing verification service (Karta Phase 1).

Implements:
- Registration and Luhn checksum validation of Iranian bank cards
- Hash-based storage (SHA-256) and AES-256-GCM encryption
- Gateway card matching to prevent payments using third-party / stolen cards
"""

from __future__ import annotations

import hashlib
import re
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.exceptions.handlers import ConflictError, ValidationError
from app.core.security.data_protection import mask_card_pan
from app.modules.inventory.application.crypto_service import encrypt_pin
from app.modules.users.application.validation_utils import (
    get_bank_name_by_bin,
    validate_bank_card_luhn,
)
from app.modules.users.domain.kyc_models import UserBankCard

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


async def list_user_bank_cards(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> list[UserBankCard]:
    """Retrieve all registered bank cards for a user."""
    safe_user_id = uuid.UUID(str(user_id))
    stmt = (
        select(UserBankCard)
        .where(UserBankCard.user_id == safe_user_id)
        .order_by(UserBankCard.created_at.desc())
    )
    return list((await db.execute(stmt)).scalars().all())


async def register_user_bank_card(
    db: AsyncSession,
    user_id: uuid.UUID,
    card_number: str,
    iban: str | None = None,
    is_default: bool = False,
) -> UserBankCard:
    """Register and store verified customer bank card (Karta Mana/Nehab)."""
    safe_user_id = uuid.UUID(str(user_id))
    clean_pan = re.sub(r"\D", "", card_number or "")
    if not validate_bank_card_luhn(clean_pan):
        raise ValidationError("شماره کارت بانکی نامعتبر است (خطای الگوریتم لان)")

    pan_hash = hashlib.sha256(clean_pan.encode("utf-8")).hexdigest()
    masked = mask_card_pan(clean_pan)
    encrypted = encrypt_pin(clean_pan)
    bank = get_bank_name_by_bin(clean_pan)

    card = UserBankCard(
        user_id=safe_user_id,
        card_pan_masked=masked,
        card_pan_hash=pan_hash,
        card_pan_encrypted=encrypted,
        iban=iban,
        bank_name=bank,
        is_verified=True,
        is_default=is_default,
        verified_at=datetime.now(UTC),
    )

    try:
        async with db.begin_nested():
            db.add(card)
            await db.flush()
    except IntegrityError as exc:
        raise ConflictError(detail="این کارت بانکی قبلاً در سیستم ثبت شده است") from exc

    await logger.ainfo("bank_card_registered", user_id=str(safe_user_id), bank=bank, masked=masked)
    return card


async def verify_payment_card_match(
    db: AsyncSession,
    user_id: uuid.UUID,
    payment_card_pan: str,
) -> bool:
    """Enforce that payment was made with one of the user's verified cards.

    Matches gateway returned PAN against the user's registered cards in memory.
    """
    clean = re.sub(r"\D", "", payment_card_pan or "")
    if not clean:
        return False

    pan_hash = hashlib.sha256(clean.encode("utf-8")).hexdigest()
    user_cards = await list_user_bank_cards(db, user_id=user_id)
    return any(c.card_pan_hash == pan_hash and c.is_verified for c in user_cards)
