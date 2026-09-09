"""Loyalty program domain models."""

import enum
import uuid
from typing import Optional

from sqlalchemy import Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.base import BaseModel


# ---- Enums ----

class LoyaltyTier(str, enum.Enum):
    BRONZE = "bronze"
    SILVER = "silver"
    GOLD = "gold"
    PLATINUM = "platinum"


class LoyaltyTransactionType(str, enum.Enum):
    EARN = "earn"
    REDEEM = "redeem"
    ADJUST = "adjust"
    EXPIRE = "expire"


# ---- Models ----

class LoyaltyAccount(BaseModel):
    """User loyalty points account with tier tracking."""

    __tablename__ = "loyalty_accounts"
    __table_args__ = (
        Index("ix_loyalty_accounts_user_id", "user_id"),
        Index("ix_loyalty_accounts_tier", "tier"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    points: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tier: Mapped[LoyaltyTier] = mapped_column(
        Enum(LoyaltyTier, name="loyalty_tier_enum", native_enum=False),
        default=LoyaltyTier.BRONZE,
        nullable=False,
    )

    # Relationships
    transactions: Mapped[list["LoyaltyTransaction"]] = relationship(
        "LoyaltyTransaction", back_populates="account", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<LoyaltyAccount(id={self.id}, user_id={self.user_id}, tier={self.tier})>"


class LoyaltyTransaction(BaseModel):
    """Point movements on a loyalty account."""

    __tablename__ = "loyalty_transactions"
    __table_args__ = (
        Index("ix_loyalty_transactions_account_id", "account_id"),
        Index("ix_loyalty_transactions_type", "type"),
        Index("ix_loyalty_transactions_created_at", "created_at"),
        Index(
            "ix_loyalty_transactions_reference",
            "reference_type",
            "reference_id",
        ),
    )

    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("loyalty_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    points: Mapped[int] = mapped_column(Integer, nullable=False)
    type: Mapped[LoyaltyTransactionType] = mapped_column(
        Enum(
            LoyaltyTransactionType,
            name="loyalty_transaction_type_enum",
            native_enum=False,
        ),
        nullable=False,
    )
    reference_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    reference_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    account: Mapped["LoyaltyAccount"] = relationship(
        "LoyaltyAccount", back_populates="transactions"
    )

    def __repr__(self) -> str:
        return f"<LoyaltyTransaction(id={self.id}, type={self.type}, points={self.points})>"
