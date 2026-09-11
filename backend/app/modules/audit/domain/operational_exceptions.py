"""Domain models and definitions for Operational Exception Center.

Conforms to Evidence-Gated Production Hardening Master Task v3.0 Phase 32 / Rule 32 / ADMIN-003:
Actionable operational anomalies:
- PRICE_MISMATCH, PAYMENT_MISMATCH, PAYMENT_TIMEOUT
- INVENTORY_CONFLICT, INVENTORY_NEGATIVE
- DUPLICATE_ORDER, DUPLICATE_PAYMENT
- REFUND_TIMEOUT, SHIPPING_FAILURE, SHIPMENT_DUPLICATE
- SEARCH_INDEX_FAILURE, WEBHOOK_REPLAY, PROMOTION_CONFLICT
Each with severity, status, owner, entity tracking, timeline, and resolution.
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


class ExceptionType(str, enum.Enum):
    PRICE_MISMATCH = "PRICE_MISMATCH"
    PAYMENT_MISMATCH = "PAYMENT_MISMATCH"
    PAYMENT_TIMEOUT = "PAYMENT_TIMEOUT"
    INVENTORY_CONFLICT = "INVENTORY_CONFLICT"
    INVENTORY_NEGATIVE = "INVENTORY_NEGATIVE"
    DUPLICATE_ORDER = "DUPLICATE_ORDER"
    DUPLICATE_PAYMENT = "DUPLICATE_PAYMENT"
    REFUND_TIMEOUT = "REFUND_TIMEOUT"
    SHIPPING_FAILURE = "SHIPPING_FAILURE"
    SHIPMENT_DUPLICATE = "SHIPMENT_DUPLICATE"
    SEARCH_INDEX_FAILURE = "SEARCH_INDEX_FAILURE"
    WEBHOOK_REPLAY = "WEBHOOK_REPLAY"
    PROMOTION_CONFLICT = "PROMOTION_CONFLICT"


class ExceptionSeverity(str, enum.Enum):
    CRITICAL = "CRITICAL"  # Potential financial corruption, stock oversell, or gateway mismatch
    HIGH = "HIGH"          # Blocked user checkout, shipment duplicate
    MEDIUM = "MEDIUM"      # Webhook replay attempt, non-critical retry exhaustion
    LOW = "LOW"            # Informational discrepancy or telemetry warning


class ExceptionStatus(str, enum.Enum):
    OPEN = "OPEN"
    INVESTIGATING = "INVESTIGATING"
    RESOLVED = "RESOLVED"
    DISMISSED = "DISMISSED"


@dataclass(slots=True)
class OperationalExceptionDomain:
    id: uuid.UUID
    exception_type: ExceptionType
    severity: ExceptionSeverity
    status: ExceptionStatus
    entity_type: str
    entity_id: str
    details: dict[str, Any]
    created_at: datetime
    owner_id: Optional[uuid.UUID] = None
    resolved_at: Optional[datetime] = None
    resolution_notes: Optional[str] = None

    def assign(self, owner_id: uuid.UUID) -> None:
        self.owner_id = owner_id
        if self.status == ExceptionStatus.OPEN:
            self.status = ExceptionStatus.INVESTIGATING

    def resolve(self, notes: str) -> None:
        self.status = ExceptionStatus.RESOLVED
        self.resolution_notes = notes
        self.resolved_at = datetime.now(timezone.utc)

    def dismiss(self, reason: str) -> None:
        self.status = ExceptionStatus.DISMISSED
        self.resolution_notes = reason
        self.resolved_at = datetime.now(timezone.utc)
