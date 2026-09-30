"""Split-tender allocations: several payments settling one order.

ERP benchmark gap analysis (feature #6 Payments, P1 — split tender).

Why an allocation table rather than a second ``payments`` row
-------------------------------------------------------------
``payments`` already has an ``order_id`` FK and the single-payment flow
depends on "one live payment per order" (see ``payment_service.create_payment``).
Split tender relaxes that rule *only* for payments created through the split
path, so both flows must be distinguishable: a payment is part of a split
tender **iff** it has an allocation row. The legacy single-payment flow is
therefore untouched — it never writes an allocation.

Exactly-once completion
-----------------------
The order flips to ``CONFIRMED`` exactly once, on the allocation that brings
the sum of *successful* allocations to the order total:

1. The order row is locked ``FOR UPDATE`` (the same lock order as
   ``verify_payment``, which locks the payment first then the order — see
   :func:`app.modules.payments.application.split_tender_service.complete_allocation`
   for how the two lock orders are kept from deadlocking).
2. The sum of successful allocations is recomputed from the rows, never from
   a cached counter, so a lost update cannot double-confirm.
3. A partial unique index guarantees at most one allocation row per
   ``(order_id)`` can hold the ``completing`` marker, which makes a double
   completion a constraint violation rather than a second order transition.

Refunds
-------
Refunds stay per-payment (the existing ``refund_payment`` flow refunds one
``Payment``), and because a split tender is several payments, a per-allocation
refund is simply "refund the payment this allocation points at". v1 therefore
does not need a new refund path; see
:func:`app.modules.payments.application.split_tender_service.refund_allocation`
for the documented helper that resolves an allocation to its payment.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import BaseModel


class AllocationStatus(str, enum.Enum):
    """Settlement state of one slice of an order's payment."""

    PENDING = "pending"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"


class PaymentAllocation(BaseModel):
    """One payment's share of one order (split tender).

    A row exists from the moment the slice is created, so the order carries an
    auditable trail of *intended* slices even if a gateway slice never
    settles.
    """

    __tablename__ = "payment_allocations"
    __table_args__ = (
        # One allocation per payment: a payment is a slice of exactly one
        # order, and re-using a payment for a second slice would double-count.
        UniqueConstraint("payment_id", name="uq_payment_allocations_payment_id"),
        Index("ix_payment_allocations_order_id", "order_id"),
        Index("ix_payment_allocations_status", "status"),
        Index("ix_payment_allocations_provider", "provider"),
        # At most one completing allocation per order — the database-side
        # guard behind the exactly-once order confirmation.
        Index(
            "uq_payment_allocations_one_completing_per_order",
            "order_id",
            unique=True,
            postgresql_where=text("is_completing = true"),
        ),
        # Integer-Rial guards, mirroring the money-integrity constraints the
        # other financial tables carry (migration a7f2c91d4e08).
        CheckConstraint("amount_rial > 0", name="ck_payment_allocations_amount_positive"),
        CheckConstraint(
            "refunded_rial >= 0 AND refunded_rial <= amount_rial",
            name="ck_payment_allocations_refunded_within_amount",
        ),
    )

    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="RESTRICT"),
        nullable=False,
    )
    payment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("payments.id", ondelete="RESTRICT"),
        nullable=False,
    )
    amount_rial: Mapped[int] = mapped_column(BigInteger, nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[AllocationStatus] = mapped_column(
        Enum(
            AllocationStatus,
            name="allocation_status_enum",
            native_enum=False,
        ),
        default=AllocationStatus.PENDING,
        nullable=False,
        server_default=text("'PENDING'::character varying"),
    )
    # True on the single allocation that brought the order to fully paid.
    is_completing: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, server_default=text("false")
    )
    # Client-supplied key so a retried checkout cannot create a second slice
    # for the same intent.
    idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    refunded_rial: Mapped[int] = mapped_column(
        BigInteger, default=0, nullable=False, server_default=text("0")
    )
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Wallet slices record the ledger transaction that debited the wallet so
    # the debit is traceable back to this allocation.
    wallet_transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    extra_data: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONB, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<PaymentAllocation(id={self.id}, order_id={self.order_id}, "
            f"amount_rial={self.amount_rial}, status={self.status})>"
        )
