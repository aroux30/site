"""Anti-fraud, Shahkar KYC, and bank card verification domain models (Karta Phase 1).

Implements:
- UserBankCard: Verified payment cards (Mana / Nehab verification)
- FailedAttempt: Rate-limiting and lockout for brute-force prevention
- UserTrustProfile: Trust score and Instant vs. Delayed delivery routing
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import BaseModel


class AttemptType(str, enum.Enum):
    OTP = "otp"
    LOGIN = "login"
    PAYMENT = "payment"
    KYC = "kyc"


class DeliveryRiskLevel(str, enum.Enum):
    INSTANT = "instant"  # Trusted users: immediate PIN revelation
    DELAYED = "delayed"  # Untrusted / first-time: held 2-12 hours for review


class UserBankCard(BaseModel):
    """User bank card verified via Mana/Nehab (Karta rynk_bank_cards).

    Ensures payments in gateway are made exclusively with user-owned verified cards.
    """

    __tablename__ = "user_bank_cards"
    __table_args__ = (
        Index("ix_user_bank_cards_user_id", "user_id"),
        Index("ix_user_bank_cards_card_pan_hash", "card_pan_hash"),
        Index("ix_user_bank_cards_is_verified", "is_verified"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    card_pan_masked: Mapped[str] = mapped_column(String(20), nullable=False)
    card_pan_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    card_pan_encrypted: Mapped[str] = mapped_column(String(255), nullable=False)
    iban: Mapped[str | None] = mapped_column(String(30), nullable=True)
    bank_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return (
            f"<UserBankCard(user_id={self.user_id}, masked={self.card_pan_masked}, "
            f"verified={self.is_verified})>"
        )


class FailedAttempt(BaseModel):
    """Tracks failed security operations to detect and block brute-force
    attacks (Karta failed_attempts)."""

    __tablename__ = "failed_attempts"
    __table_args__ = (
        Index("ix_failed_attempts_identifier", "identifier"),
        Index("ix_failed_attempts_attempt_type", "attempt_type"),
        Index("ix_failed_attempts_created_at", "created_at"),
    )

    # Phone number, email, or IP
    identifier: Mapped[str] = mapped_column(String(100), nullable=False)
    attempt_type: Mapped[AttemptType] = mapped_column(
        Enum(AttemptType, name="attempt_type_enum", native_enum=False),
        nullable=False,
    )
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(300), nullable=True)


class UserTrustProfile(BaseModel):
    """User risk and trust metrics determining order delivery policy (Karta is_trusted)."""

    __tablename__ = "user_trust_profiles"
    __table_args__ = (
        Index("ix_user_trust_profiles_user_id", "user_id"),
        Index("ix_user_trust_profiles_is_trusted", "is_trusted"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    is_trusted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    shahkar_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # 0 (safe) to 100 (high risk)
    risk_score: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    delayed_delivery_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # 50M Rials default
    daily_spend_limit: Mapped[int] = mapped_column(BigInteger, default=50_000_000, nullable=False)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return (
            f"<UserTrustProfile(user_id={self.user_id}, trusted={self.is_trusted}, "
            f"risk={self.risk_score})>"
        )
