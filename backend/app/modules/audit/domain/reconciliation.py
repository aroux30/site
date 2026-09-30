"""Durable reconciliation findings for the audit bounded context.

Additive storage for the read-only payment reconciliation scanner described in
``docs/architecture/clean-room-operational-capability-and-reconciliation.md``.

This is deliberately *not* the operational exception center: that registry is an
in-memory real-time alerting view, while a reconciliation finding is a durable,
deduplicated record of a provable financial mismatch that survives restarts and
must be resolvable by an operator with an auditable note.

Storage design notes
--------------------
* ``dedupe_key`` carries a UNIQUE constraint. Every detector derives a stable
  key from the identity of the mismatched entity, so re-running the scanner
  (at-least-once Celery execution, an admin-triggered run, or two overlapping
  runs) can only ever converge on one row per condition.
* Entity references are plain strings, not foreign keys. A finding is evidence
  *about* a payment/order/refund/webhook and must remain readable even if the
  referenced row is later deleted; an FK would either block the delete or
  cascade the evidence away.
* Amounts are integer Iranian rials, mirroring the authoritative money columns.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import BaseModel


class FindingType(str, enum.Enum):
    """The provable mismatch classes the scanner is allowed to report."""

    #: ``payments.amount`` differs from the authoritative ``orders.total``.
    PAYMENT_AMOUNT_MISMATCH = "PAYMENT_AMOUNT_MISMATCH"
    #: A COMPLETED payment whose order never left the PENDING state.
    PAYMENT_ORDER_STATUS_MISMATCH = "PAYMENT_ORDER_STATUS_MISMATCH"
    #: Non-rejected refunds for one payment exceed that payment's amount.
    REFUND_TOTAL_EXCEEDS_PAYMENT = "REFUND_TOTAL_EXCEEDS_PAYMENT"
    #: A webhook event stayed unprocessed past the documented grace period.
    WEBHOOK_UNPROCESSED = "WEBHOOK_UNPROCESSED"
    #: A terminally cancelled order still has a physical shipment leaving it.
    ORDER_CANCELED_WITH_SHIPMENT = "ORDER_CANCELED_WITH_SHIPMENT"
    #: An order claims delivery but none of its physical shipments is delivered.
    ORDER_DELIVERED_SHIPMENT_OPEN = "ORDER_DELIVERED_SHIPMENT_OPEN"
    #: A fully refunded order has less processed refund value than its total.
    ORDER_REFUNDED_UNDERREFUND = "ORDER_REFUNDED_UNDERREFUND"


class FindingSeverity(str, enum.Enum):
    CRITICAL = "CRITICAL"  # Money is provably mis-stated or over-returned
    HIGH = "HIGH"  # Money is captured but the order side disagrees
    MEDIUM = "MEDIUM"  # Stalled processing that has not yet moved money
    LOW = "LOW"  # Informational discrepancy


class FindingStatus(str, enum.Enum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"
    DISMISSED = "DISMISSED"


class ReconciliationFinding(BaseModel):
    """One deduplicated, durable reconciliation finding."""

    __tablename__ = "reconciliation_findings"
    __table_args__ = (
        Index("ix_reconciliation_findings_status", "status"),
        Index("ix_reconciliation_findings_finding_type", "finding_type"),
        Index("ix_reconciliation_findings_severity", "severity"),
        Index("ix_reconciliation_findings_last_detected_at", "last_detected_at"),
        Index(
            "ix_reconciliation_findings_entity",
            "entity_type",
            "entity_id",
        ),
    )

    #: Stable identity of the underlying condition; the deduplication key.
    dedupe_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    finding_type: Mapped[FindingType] = mapped_column(
        Enum(FindingType, name="reconciliation_finding_type_enum", native_enum=False),
        nullable=False,
    )
    severity: Mapped[FindingSeverity] = mapped_column(
        Enum(FindingSeverity, name="reconciliation_finding_severity_enum", native_enum=False),
        nullable=False,
    )
    status: Mapped[FindingStatus] = mapped_column(
        Enum(FindingStatus, name="reconciliation_finding_status_enum", native_enum=False),
        default=FindingStatus.OPEN,
        nullable=False,
    )

    #: Referenced entity kind (``payment``, ``refund``, ``webhook_event``, …).
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    #: Referenced entity identifier, stored as text so non-UUID references fit.
    entity_id: Mapped[str] = mapped_column(String(255), nullable=False)

    #: Integer-rial amounts; NULL when the detector has no money comparison.
    expected_amount: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    actual_amount: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    #: Secret-free evidence for the operator. Never carries provider payloads.
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    first_detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    #: How many scanner passes observed this condition (at-least-once safe).
    occurrence_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    resolution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<ReconciliationFinding(id={self.id}, type={self.finding_type}, "
            f"status={self.status}, dedupe_key={self.dedupe_key})>"
        )
