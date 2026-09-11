"""Domain definitions and state machine for Return Merchandise Authorization (RMA).

Conforms to Evidence-Gated Production Hardening Master Task v3.0 Phase 13 / Phase 23:
- Full multi-step return lifecycle (Request -> Eligibility -> Approval -> Inspection -> Refund -> Close)
- Configurable statutory eligibility window (Iranian E-Commerce Law Art. 37: 7 days)
- Partial return support per order item
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


class ReturnStatus(str, enum.Enum):
    REQUESTED = "requested"
    APPROVED = "approved"
    REJECTED = "rejected"
    RECEIVED = "received"
    INSPECTED = "inspected"
    REFUNDED = "refunded"
    REPLACED = "replaced"
    CLOSED = "closed"


class ReturnReason(str, enum.Enum):
    DEFECTIVE = "defective"
    WRONG_ITEM = "wrong_item"
    NOT_AS_DESCRIBED = "not_as_described"
    CUSTOMER_REMORSE = "customer_remorse"  # 7-day statutory cooling-off period
    DAMAGED_IN_SHIPPING = "damaged_in_shipping"


class InspectionOutcome(str, enum.Enum):
    PASSED = "passed"  # Item undamaged and resalable
    DAMAGED_BY_CUSTOMER = "damaged_by_customer"  # Ineligible for refund
    DEFECTIVE_CONFIRMED = "defective_confirmed"  # Confirmed factory defect


# Valid transition state machine for RMA
RETURN_TRANSITIONS: dict[ReturnStatus, frozenset[ReturnStatus]] = {
    ReturnStatus.REQUESTED: frozenset({ReturnStatus.APPROVED, ReturnStatus.REJECTED}),
    ReturnStatus.APPROVED: frozenset({ReturnStatus.RECEIVED, ReturnStatus.CLOSED}),
    ReturnStatus.REJECTED: frozenset({ReturnStatus.CLOSED}),
    ReturnStatus.RECEIVED: frozenset({ReturnStatus.INSPECTED}),
    ReturnStatus.INSPECTED: frozenset({ReturnStatus.REFUNDED, ReturnStatus.REPLACED, ReturnStatus.REJECTED}),
    ReturnStatus.REFUNDED: frozenset({ReturnStatus.CLOSED}),
    ReturnStatus.REPLACED: frozenset({ReturnStatus.CLOSED}),
    ReturnStatus.CLOSED: frozenset(),  # Terminal state
}


@dataclass(slots=True)
class ReturnItemSpec:
    order_item_id: uuid.UUID
    variant_id: uuid.UUID
    quantity: int
    reason: ReturnReason
    customer_notes: Optional[str] = None
    inspection_outcome: Optional[InspectionOutcome] = None


@dataclass(slots=True)
class OrderReturnDomain:
    id: uuid.UUID
    order_id: uuid.UUID
    user_id: uuid.UUID
    status: ReturnStatus
    items: list[ReturnItemSpec]
    created_at: datetime
    eligibility_window_days: int = 7
    approved_at: Optional[datetime] = None
    inspected_at: Optional[datetime] = None
    refunded_at: Optional[datetime] = None
    admin_notes: Optional[str] = None
    refund_amount: int = 0  # In BigInteger Rials

    def can_transition_to(self, target: ReturnStatus) -> bool:
        return target in RETURN_TRANSITIONS.get(self.status, frozenset())

    def transition_to(self, target: ReturnStatus, notes: Optional[str] = None) -> None:
        if not self.can_transition_to(target):
            raise ValueError(
                f"Cannot transition return from '{self.status.value}' to '{target.value}'. "
                f"Allowed: {', '.join(s.value for s in RETURN_TRANSITIONS.get(self.status, frozenset()))}"
            )
        self.status = target
        if notes:
            self.admin_notes = notes
        now = datetime.now(timezone.utc)
        if target == ReturnStatus.APPROVED:
            self.approved_at = now
        elif target == ReturnStatus.INSPECTED:
            self.inspected_at = now
        elif target == ReturnStatus.REFUNDED:
            self.refunded_at = now
