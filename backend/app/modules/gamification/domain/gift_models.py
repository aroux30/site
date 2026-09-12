"""Gamification, Internal Gift Cards, Lucky Wheel, and Charge Packages domain models (Karta Phase
5/7).

Implements:
- InternalGiftCard: Digital gift vouchers with templates and wallet redemption (Karta Gift Cards)
- LuckyWheelPrize & GiftTryLog: Post-order gamified lucky box / spin wheel with weighted odds
(Karta gifts & try_gifts)
- ChargePackage: Pre-set wallet top-up packages with incentive bonus credit (Karta charge_packages)
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import BaseModel


class PrizeType(str, enum.Enum):
    WALLET_CREDIT = "wallet_credit"
    DISCOUNT_PERCENT = "discount_percent"
    FIXED_DISCOUNT = "fixed_discount"
    FREE_PRODUCT = "free_product"
    NOTHING = "nothing"


class InternalGiftCard(BaseModel):
    """In-platform digital gift voucher redeemable directly to wallet balance."""

    __tablename__ = "internal_gift_cards"
    __table_args__ = (
        Index("ix_internal_gift_cards_code", "code"),
        Index("ix_internal_gift_cards_created_by", "created_by_user_id"),
        Index("ix_internal_gift_cards_claimed_by", "claimed_by_user_id"),
        Index("ix_internal_gift_cards_is_active", "is_active"),
    )

    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    remaining_balance: Mapped[int] = mapped_column(BigInteger, nullable=False)
    card_template: Mapped[str] = mapped_column(String(32), default="gold", nullable=False)
    sender_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    recipient_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    recipient_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    claimed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return (
            f"<InternalGiftCard(code={self.code}, amount={self.amount}, active={self.is_active})>"
        )


class LuckyWheelPrize(BaseModel):
    """Configurable prize on the post-order gamified spin wheel (Karta gifts)."""

    __tablename__ = "lucky_wheel_prizes"
    __table_args__ = (Index("ix_lucky_wheel_prizes_is_active", "is_active"),)

    title: Mapped[str] = mapped_column(String(150), nullable=False)
    prize_type: Mapped[PrizeType] = mapped_column(
        Enum(PrizeType, name="prize_type_enum", native_enum=False),
        nullable=False,
    )
    value: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    probability_weight: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    icon: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    max_claims_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    claimed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    def __repr__(self) -> str:
        return f"<LuckyWheelPrize(title={self.title}, weight={self.probability_weight})>"


class GiftTryLog(BaseModel):
    """Audit log of lucky wheel spins linked to completed orders (Karta try_gifts)."""

    __tablename__ = "gift_try_logs"
    __table_args__ = (
        Index("ix_gift_try_logs_user_id", "user_id"),
        Index("ix_gift_try_logs_order_id", "order_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    prize_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("lucky_wheel_prizes.id", ondelete="SET NULL"),
        nullable=True,
    )
    prize_title: Mapped[str] = mapped_column(String(150), nullable=False)
    prize_type: Mapped[str] = mapped_column(String(50), nullable=False)
    awarded_value: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    def __repr__(self) -> str:
        return f"<GiftTryLog(order_id={self.order_id}, prize={self.prize_title})>"


class ChargePackage(BaseModel):
    """Pre-configured wallet top-up package with incentive bonus (Karta charge_packages).

    Example: pay 1,000,000 IRR, receive 1,050,000 IRR in wallet credit.
    """

    __tablename__ = "charge_packages"
    __table_args__ = (
        Index("ix_charge_packages_is_active", "is_active"),
        Index("ix_charge_packages_ordering", "ordering"),
    )

    title: Mapped[str] = mapped_column(String(100), nullable=False)
    pay_amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    credit_amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    ordering: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    def __repr__(self) -> str:
        return (
            f"<ChargePackage(title={self.title}, pay={self.pay_amount}, "
            f"credit={self.credit_amount})>"
        )
