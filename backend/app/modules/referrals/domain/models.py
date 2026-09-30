"""Referral program domain models."""

import enum
import uuid

from sqlalchemy import (
    BigInteger,
    Boolean,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.base import BaseModel

# ---- Enums ----


class ReferralStatus(str, enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    REWARDED = "rewarded"


class CommissionStatus(str, enum.Enum):
    PENDING = "pending"
    PAID = "paid"


# ---- Models ----


class ReferralCode(BaseModel):
    """A user's own referral code.

    ``Referral`` records a referrer→referred *relationship*, which does not
    exist until someone actually signs up with the code. The code itself has
    to be stable before that, so it lives in its own row keyed by the owner.
    """

    __tablename__ = "referral_codes"
    __table_args__ = (
        Index("ix_referral_codes_user_id", "user_id", unique=True),
        Index("ix_referral_codes_code", "code", unique=True),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def __repr__(self) -> str:
        return f"<ReferralCode(user_id={self.user_id}, code={self.code})>"


class Referral(BaseModel):
    """Tracks user referral relationships (supports 2-level deep)."""

    __tablename__ = "referrals"
    __table_args__ = (
        Index("ix_referrals_referrer_id", "referrer_id"),
        Index("ix_referrals_referred_id", "referred_id"),
        Index("ix_referrals_code", "code"),
        Index("ix_referrals_status", "status"),
    )

    referrer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    referred_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    level: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[ReferralStatus] = mapped_column(
        Enum(ReferralStatus, name="referral_status_enum", native_enum=False),
        default=ReferralStatus.PENDING,
        nullable=False,
    )

    # Relationships
    commissions: Mapped[list["ReferralCommission"]] = relationship(
        "ReferralCommission", back_populates="referral", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<Referral(id={self.id}, referrer_id={self.referrer_id}, referred_id={self.referred_id})>"  # noqa: E501


class ReferralCommission(BaseModel):
    """Commission earned from referred user orders."""

    __tablename__ = "referral_commissions"
    __table_args__ = (
        Index("ix_referral_commissions_referral_id", "referral_id"),
        Index("ix_referral_commissions_order_id", "order_id"),
        Index("ix_referral_commissions_status", "status"),
    )

    referral_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("referrals.id", ondelete="CASCADE"),
        nullable=False,
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
    )
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    level: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[CommissionStatus] = mapped_column(
        Enum(CommissionStatus, name="commission_status_enum", native_enum=False),
        default=CommissionStatus.PENDING,
        nullable=False,
    )

    # Relationships
    referral: Mapped["Referral"] = relationship("Referral", back_populates="commissions")

    def __repr__(self) -> str:
        return f"<ReferralCommission(id={self.id}, amount={self.amount}, status={self.status})>"
