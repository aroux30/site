"""Digital wallet domain models."""

import enum
import uuid
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.base import BaseModel


# ---- Enums ----

class WalletTransactionType(str, enum.Enum):
    CREDIT = "credit"
    DEBIT = "debit"
    REFUND = "refund"
    CASHBACK = "cashback"
    BONUS = "bonus"
    WITHDRAWAL = "withdrawal"
    ADJUSTMENT = "adjustment"


# ---- Models ----

class Wallet(BaseModel):
    """User digital wallet for in-platform balance."""

    __tablename__ = "wallets"
    __table_args__ = (
        Index("ix_wallets_user_id", "user_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    balance: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    transactions: Mapped[list["WalletTransaction"]] = relationship(
        "WalletTransaction", back_populates="wallet", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<Wallet(id={self.id}, user_id={self.user_id}, balance={self.balance})>"


class WalletTransaction(BaseModel):
    """Individual wallet balance movements."""

    __tablename__ = "wallet_transactions"
    __table_args__ = (
        Index("ix_wallet_transactions_wallet_id", "wallet_id"),
        Index("ix_wallet_transactions_type", "type"),
        Index("ix_wallet_transactions_created_at", "created_at"),
        Index(
            "ix_wallet_transactions_reference",
            "reference_type",
            "reference_id",
        ),
    )

    wallet_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("wallets.id", ondelete="CASCADE"),
        nullable=False,
    )
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    type: Mapped[WalletTransactionType] = mapped_column(
        Enum(
            WalletTransactionType,
            name="wallet_transaction_type_enum",
            native_enum=False,
        ),
        nullable=False,
    )
    reference_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    reference_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    balance_after: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # Relationships
    wallet: Mapped["Wallet"] = relationship(
        "Wallet", back_populates="transactions"
    )

    def __repr__(self) -> str:
        return f"<WalletTransaction(id={self.id}, type={self.type}, amount={self.amount})>"
