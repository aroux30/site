"""Referral program domain models."""

import enum
import uuid
from typing import Optional

from sqlalchemy import (
    BigInteger,
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
        return f"<Referral(id={self.id}, referrer_id={self.referrer_id}, referred_id={self.referred_id})>"


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
    referral: Mapped["Referral"] = relationship(
        "Referral", back_populates="commissions"
    )

    def __repr__(self) -> str:
        return f"<ReferralCommission(id={self.id}, amount={self.amount}, status={self.status})>"
