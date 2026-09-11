"""Payment processing domain models."""

import enum
import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.base import BaseModel

# ---- Enums ----


class PaymentProvider(str, enum.Enum):
    ZARINPAL = "zarinpal"
    IDPAY = "idpay"
    NEXTPAY = "nextpay"
    WALLET = "wallet"
    CARD_TRANSFER = "card_transfer"
    CRYPTO = "crypto"
    MOCK = "mock"


class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"


class PaymentTransactionType(str, enum.Enum):
    CHARGE = "charge"
    REFUND = "refund"
    VERIFY = "verify"


class RefundStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    PROCESSED = "processed"
    REJECTED = "rejected"


# ---- Models ----


class Payment(BaseModel):
    """Payment records linked to orders."""

    __tablename__ = "payments"
    __table_args__ = (
        Index("ix_payments_order_id", "order_id"),
        Index("ix_payments_status", "status"),
        Index("ix_payments_provider", "provider"),
        Index("ix_payments_idempotency_key", "idempotency_key"),
        Index("ix_payments_created_at", "created_at"),
    )

    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="RESTRICT"),
        nullable=False,
    )
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="IRR", nullable=False)
    provider: Mapped[PaymentProvider] = mapped_column(
        Enum(PaymentProvider, name="payment_provider_enum", native_enum=False),
        nullable=False,
    )
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus, name="payment_status_enum", native_enum=False),
        default=PaymentStatus.PENDING,
        nullable=False,
    )
    provider_transaction_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    authority: Mapped[str | None] = mapped_column(String(255), nullable=True)
    gateway_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    extra_data: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONB, nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)

    # Relationships
    transactions: Mapped[list["PaymentTransaction"]] = relationship(
        "PaymentTransaction", back_populates="payment", lazy="select"
    )
    refunds: Mapped[list["Refund"]] = relationship(
        "Refund", back_populates="payment", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<Payment(id={self.id}, order_id={self.order_id}, status={self.status})>"


class PaymentTransaction(BaseModel):
    """Individual transaction attempts within a payment."""

    __tablename__ = "payment_transactions"
    __table_args__ = (
        Index("ix_payment_transactions_payment_id", "payment_id"),
        Index("ix_payment_transactions_type", "type"),
        Index("ix_payment_transactions_created_at", "created_at"),
    )

    payment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("payments.id", ondelete="CASCADE"),
        nullable=False,
    )
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    type: Mapped[PaymentTransactionType] = mapped_column(
        Enum(
            PaymentTransactionType,
            name="payment_transaction_type_enum",
            native_enum=False,
        ),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    provider_response: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    # Relationships
    payment: Mapped["Payment"] = relationship("Payment", back_populates="transactions")

    def __repr__(self) -> str:
        return f"<PaymentTransaction(id={self.id}, type={self.type}, status={self.status})>"


class Refund(BaseModel):
    """Refund requests linked to payments and orders."""

    __tablename__ = "refunds"
    __table_args__ = (
        Index("ix_refunds_payment_id", "payment_id"),
        Index("ix_refunds_order_id", "order_id"),
        Index("ix_refunds_status", "status"),
    )

    payment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("payments.id", ondelete="RESTRICT"),
        nullable=False,
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="RESTRICT"),
        nullable=False,
    )
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[RefundStatus] = mapped_column(
        Enum(RefundStatus, name="refund_status_enum", native_enum=False),
        default=RefundStatus.PENDING,
        nullable=False,
    )
    processed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    payment: Mapped["Payment"] = relationship("Payment", back_populates="refunds")

    def __repr__(self) -> str:
        return f"<Refund(id={self.id}, amount={self.amount}, status={self.status})>"


class PaymentWebhookEvent(BaseModel):
    """Raw incoming webhook payloads recorded for replay protection and idempotency."""

    __tablename__ = "payment_webhook_events"
    __table_args__ = (
        UniqueConstraint("provider", "event_id", name="uq_webhook_provider_event_id"),
        Index("ix_webhook_events_provider", "provider"),
        Index("ix_webhook_events_event_id", "event_id"),
        Index("ix_webhook_events_created_at", "created_at"),
    )

    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    event_id: Mapped[str] = mapped_column(String(255), nullable=False)
    payment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("payments.id", ondelete="SET NULL"),
        nullable=True,
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    processed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    payment: Mapped[Optional["Payment"]] = relationship("Payment")

    def __repr__(self) -> str:
        return f"<PaymentWebhookEvent(provider={self.provider}, event_id={self.event_id}, processed={self.processed})>"  # noqa: E501
