"""Fiscal invoice domain models.

An :class:`Invoice` is a *fiscal document* — formally numbered, sequentially
allocated per Jalali fiscal period, immutable once posted, and chained to the
previous posted invoice with a SHA-256 integrity hash (Odoo-style tamper
evidence). It sits beside the existing rendered tax-invoice HTML in
``orders/application/invoice_service.py``, which stays the presentation layer:
this module owns the *record*, that module owns the *rendering*.

Money convention: every amount is an integer **Rial** value (the platform's
internal unit — see ``app/shared/money/money.py``); never float.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.base import BaseModel


class InvoiceType(str, enum.Enum):
    INVOICE = "invoice"
    CREDIT_NOTE = "credit_note"


class InvoiceStatus(str, enum.Enum):
    DRAFT = "draft"
    POSTED = "posted"
    PAID = "paid"
    CANCELLED = "cancelled"


# Allowed status transitions. Cancellation rules (documented):
# - draft     -> cancelled (never issued; safe to void)
# - posted    -> cancelled (voided before any payment is recorded against it)
# - paid      -> terminal for cancellation (a paid invoice must be corrected
#                with a credit note, never deleted/cancelled)
# - cancelled -> terminal
INVOICE_TRANSITIONS: dict[InvoiceStatus, frozenset[InvoiceStatus]] = {
    InvoiceStatus.DRAFT: frozenset({InvoiceStatus.POSTED, InvoiceStatus.CANCELLED}),
    InvoiceStatus.POSTED: frozenset({InvoiceStatus.PAID, InvoiceStatus.CANCELLED}),
    InvoiceStatus.PAID: frozenset(),
    InvoiceStatus.CANCELLED: frozenset(),
}


class Invoice(BaseModel):
    """Fiscal document header with totals/customer snapshots and hash chain."""

    __tablename__ = "invoices"
    __table_args__ = (
        UniqueConstraint("number", name="uq_invoices_number"),
        Index("ix_invoices_order_id", "order_id"),
        Index("ix_invoices_status", "status"),
        Index("ix_invoices_fiscal_period", "fiscal_period"),
        Index("ix_invoices_type", "type"),
        Index("ix_invoices_issued_at", "issued_at"),
        Index("ix_invoices_idempotency_key", "idempotency_key"),
    )

    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="RESTRICT"),
        nullable=False,
    )
    type: Mapped[InvoiceType] = mapped_column(
        Enum(InvoiceType, name="invoice_type_enum", native_enum=False),
        default=InvoiceType.INVOICE,
        nullable=False,
    )
    status: Mapped[InvoiceStatus] = mapped_column(
        Enum(InvoiceStatus, name="invoice_status_enum", native_enum=False),
        default=InvoiceStatus.DRAFT,
        nullable=False,
    )
    # Fiscal document number (INV-1404-000123 / CN-1404-000045). Allocated at
    # post time; NULL while draft.
    number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # Jalali fiscal year, e.g. "1404". Set at post time from issued_at.
    fiscal_period: Mapped[str | None] = mapped_column(String(8), nullable=True)
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Immutable financial snapshot (integer Rial) captured at issue time.
    totals: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    # Buyer snapshot (name/phone/national code/address) captured at issue time.
    customer: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    # SHA-256 tamper-evident chain: hash = sha256(number | issued_at | totals |
    # previous posted invoice's hash). Genesis hash for the first document.
    hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    previous_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # For credit notes: the original invoice this note corrects.
    credit_for_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("invoices.id", ondelete="RESTRICT"),
        nullable=True,
    )
    credit_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Archived rendering (HTML snapshot today; PDF bytes once a renderer is
    # configured) stored via the media/storage infra at post time.
    archive_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    archive_content_type: Mapped[str | None] = mapped_column(String(100), nullable=True)

    idempotency_key: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    lines: Mapped[list["InvoiceLine"]] = relationship(
        "InvoiceLine", back_populates="invoice", lazy="selectin", cascade="all, delete-orphan"
    )
    # Self-referential: a credit note points at the invoice it corrects.
    credit_notes: Mapped[list["Invoice"]] = relationship(
        "Invoice",
        back_populates="credit_for",
        remote_side="Invoice.id",
        lazy="select",
    )
    credit_for: Mapped["Invoice | None"] = relationship(
        "Invoice",
        back_populates="credit_notes",
        remote_side="Invoice.credit_for_id",
        lazy="select",
    )

    @property
    def is_mutable(self) -> bool:
        """Posted/paid/cancelled invoices are immutable fiscal records."""
        return self.status == InvoiceStatus.DRAFT

    def __repr__(self) -> str:
        return f"<Invoice(id={self.id}, number={self.number}, type={self.type}, status={self.status})>"


class InvoiceLine(BaseModel):
    """Immutable invoice line snapshot (integer Rial amounts)."""

    __tablename__ = "invoice_lines"
    __table_args__ = (
        Index("ix_invoice_lines_invoice_id", "invoice_id"),
        CheckConstraint("quantity >= 0", name="ck_invoice_lines_quantity_nonneg"),
    )

    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("invoices.id", ondelete="CASCADE"),
        nullable=False,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    product_name: Mapped[str] = mapped_column(String(500), nullable=False)
    sku: Mapped[str | None] = mapped_column(String(100), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[int] = mapped_column(BigInteger, nullable=False)
    total_price: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # Relationships
    invoice: Mapped["Invoice"] = relationship("Invoice", back_populates="lines")

    def __repr__(self) -> str:
        return f"<InvoiceLine(id={self.id}, sku={self.sku}, qty={self.quantity})>"


class InvoiceSequence(BaseModel):
    """Per-fiscal-period sequence row for gapless number allocation.

    Allocation protocol (see ``application/numbering.py``): the row for the
    (fiscal_period, doc_type) pair is locked with ``SELECT ... FOR UPDATE``,
    ``last_value`` is incremented inside the caller's transaction, and the new
    value is used to build the document number. Because the lock is held to
    commit time, two concurrent posters can never receive the same value and
    a rolled-back allocation cannot hand its value to anyone else — the next
    allocator simply re-uses the still-committed ``last_value`` + 1, so the
    committed sequence has no gaps.
    """

    __tablename__ = "invoice_sequences"
    __table_args__ = (
        UniqueConstraint("fiscal_period", "doc_type", name="uq_invoice_sequences_period_type"),
    )

    fiscal_period: Mapped[str] = mapped_column(String(8), nullable=False)
    doc_type: Mapped[InvoiceType] = mapped_column(
        Enum(InvoiceType, name="invoice_type_enum", native_enum=False),
        nullable=False,
    )
    last_value: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)

    def __repr__(self) -> str:
        return f"<InvoiceSequence({self.doc_type}:{self.fiscal_period} last={self.last_value})>"
