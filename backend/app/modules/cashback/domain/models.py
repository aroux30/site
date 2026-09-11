"""Cashback program domain models."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    String,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.base import BaseModel

# ---- Enums ----


class CashbackRuleType(str, enum.Enum):
    PAYMENT_METHOD = "payment_method"
    CUSTOMER_SEGMENT = "customer_segment"
    PRODUCT = "product"
    CATEGORY = "category"
    CAMPAIGN = "campaign"


class CashbackTransactionStatus(str, enum.Enum):
    PENDING = "pending"
    CREDITED = "credited"
    EXPIRED = "expired"


# ---- Models ----


class CashbackRule(BaseModel):
    """Rules governing when and how cashback is awarded."""

    __tablename__ = "cashback_rules"
    __table_args__ = (
        Index("ix_cashback_rules_type", "type"),
        Index("ix_cashback_rules_is_active", "is_active"),
        Index("ix_cashback_rules_starts_at_ends_at", "starts_at", "ends_at"),
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    type: Mapped[CashbackRuleType] = mapped_column(
        Enum(CashbackRuleType, name="cashback_rule_type_enum", native_enum=False),
        nullable=False,
    )
    scope_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    percentage: Mapped[float] = mapped_column(Float, nullable=False)
    max_amount: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Relationships
    transactions: Mapped[list["CashbackTransaction"]] = relationship(
        "CashbackTransaction", back_populates="rule", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<CashbackRule(id={self.id}, name={self.name}, type={self.type})>"


class CashbackTransaction(BaseModel):
    """Individual cashback awards tied to orders and rules."""

    __tablename__ = "cashback_transactions"
    __table_args__ = (
        Index("ix_cashback_transactions_user_id", "user_id"),
        Index("ix_cashback_transactions_order_id", "order_id"),
        Index("ix_cashback_transactions_rule_id", "rule_id"),
        Index("ix_cashback_transactions_status", "status"),
        Index("ix_cashback_transactions_created_at", "created_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
    )
    rule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cashback_rules.id", ondelete="CASCADE"),
        nullable=False,
    )
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[CashbackTransactionStatus] = mapped_column(
        Enum(
            CashbackTransactionStatus,
            name="cashback_transaction_status_enum",
            native_enum=False,
        ),
        default=CashbackTransactionStatus.PENDING,
        nullable=False,
    )

    # Relationships
    rule: Mapped["CashbackRule"] = relationship("CashbackRule", back_populates="transactions")

    def __repr__(self) -> str:
        return f"<CashbackTransaction(id={self.id}, amount={self.amount}, status={self.status})>"
