"""Fintech domain models: Card-to-Card receipts, Direct Pay invoices, and Gateway config (Karta
Phase 3/5).

Implements:
- CardTransferReceipt: Manual card-to-card slip upload and review workflow (Karta card2card)
- DirectInvoice: Direct quick invoices without shopping cart cycle (Karta Directpay)
- GatewaySetting: Dynamic runtime configuration and failover for payment gateways
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
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import BaseModel


class ReceiptReviewStatus(str, enum.Enum):
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"


class DirectInvoiceStatus(str, enum.Enum):
    UNPAID = "unpaid"
    PAID = "paid"
    CANCELED = "canceled"
    EXPIRED = "expired"


class CardTransferReceipt(BaseModel):
    """Offline card-to-card transfer receipt submitted by buyer (Karta card2card)."""

    __tablename__ = "card_transfer_receipts"
    __table_args__ = (
        Index("ix_card_transfer_receipts_order_id", "order_id"),
        Index("ix_card_transfer_receipts_user_id", "user_id"),
        Index("ix_card_transfer_receipts_status", "status"),
        Index("ix_card_transfer_receipts_tracking_code", "tracking_code"),
    )

    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="RESTRICT"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    tracking_code: Mapped[str] = mapped_column(String(100), nullable=False)
    source_card_last4: Mapped[str] = mapped_column(String(4), nullable=False)
    destination_card_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    receipt_image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[ReceiptReviewStatus] = mapped_column(
        Enum(ReceiptReviewStatus, name="receipt_review_status_enum", native_enum=False),
        default=ReceiptReviewStatus.PENDING_REVIEW,
        nullable=False,
    )
    admin_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return (
            f"<CardTransferReceipt(id={self.id}, tracking={self.tracking_code}, "
            f"status={self.status})>"
        )


class DirectInvoice(BaseModel):
    """Quick direct invoice and shareable payment link (Karta Directpay)."""

    __tablename__ = "direct_invoices"
    __table_args__ = (
        Index("ix_direct_invoices_invoice_number", "invoice_number"),
        Index("ix_direct_invoices_user_id", "user_id"),
        Index("ix_direct_invoices_status", "status"),
    )

    invoice_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    title: Mapped[str] = mapped_column(String(250), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    payer_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    payer_mobile: Mapped[str | None] = mapped_column(String(20), nullable=True)
    status: Mapped[DirectInvoiceStatus] = mapped_column(
        Enum(DirectInvoiceStatus, name="direct_invoice_status_enum", native_enum=False),
        default=DirectInvoiceStatus.UNPAID,
        nullable=False,
    )
    payment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("payments.id", ondelete="SET NULL"),
        nullable=True,
    )
    expire_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return (
            f"<DirectInvoice(number={self.invoice_number}, amount={self.amount}, "
            f"status={self.status})>"
        )


class GatewaySetting(BaseModel):
    """Dynamic gateway registry and switching configuration (Karta Gateways)."""

    __tablename__ = "gateway_settings"
    __table_args__ = (
        Index("ix_gateway_settings_provider_key", "provider_key"),
        Index("ix_gateway_settings_is_active", "is_active"),
    )

    provider_key: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    title_fa: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    min_amount: Mapped[int] = mapped_column(BigInteger, default=10_000, nullable=False)
    max_amount: Mapped[int] = mapped_column(BigInteger, default=500_000_000, nullable=False)
    credentials: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    def __repr__(self) -> str:
        return f"<GatewaySetting(key={self.provider_key}, active={self.is_active})>"
