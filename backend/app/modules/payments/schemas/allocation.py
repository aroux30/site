"""Pydantic schemas for split-tender allocations.

All amounts are integer Rials. The request schema carries no order total: the
order's own total is authoritative and the slices must cover it exactly.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.payments.domain.allocation_models import AllocationStatus
from app.modules.payments.schemas.payment import PaymentResponse


class AllocationSliceRequest(BaseModel):
    """One slice of a split tender (wallet part / gateway part)."""

    model_config = ConfigDict(str_strip_whitespace=True)

    provider: str = Field(..., max_length=50, description="Payments provider for this slice")
    amount_rial: int = Field(..., gt=0, description="Slice amount in IRR")
    description: str = Field("", max_length=500)
    idempotency_key: str | None = Field(
        None,
        max_length=255,
        description="Client key so a retried split cannot duplicate this slice",
    )


class SplitTenderRequest(BaseModel):
    """Create a split-tender checkout: several slices covering the order total."""

    order_id: uuid.UUID
    slices: list[AllocationSliceRequest] = Field(..., min_length=1, max_length=5)


class PaymentAllocationResponse(BaseModel):
    """One settled (or pending) slice of an order's payment."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    order_id: uuid.UUID
    payment_id: uuid.UUID
    amount_rial: int
    provider: str
    status: AllocationStatus
    is_completing: bool
    settled_at: datetime | None = None
    refunded_rial: int
    failure_reason: str | None = None
    created_at: datetime
    updated_at: datetime


class OrderAllocationSummary(BaseModel):
    """Paid / pending / remaining view of an order's split tender."""

    order_id: uuid.UUID
    order_total_rial: int
    paid_amount_rial: int
    pending_amount_rial: int
    remaining_amount_rial: int
    is_fully_paid: bool
    allocations: list[PaymentAllocationResponse]


class SplitPaymentResponse(BaseModel):
    """Result of creating a split tender.

    ``redirect_url`` is the gateway the customer must visit next (the first
    unsettled gateway slice); it is ``None`` when the split was fully covered
    by the wallet and the order is already complete.
    """

    order_id: uuid.UUID
    payments: list[PaymentResponse]
    allocations: list[PaymentAllocationResponse]
    redirect_url: str | None = None
    summary: OrderAllocationSummary


class AllocationRefundRequest(BaseModel):
    """Refund one split slice (v1: full allocation amount only)."""

    amount: int = Field(..., gt=0, description="Refund amount in IRR (must equal the slice)")
    reason: str | None = Field(None, max_length=1000)
