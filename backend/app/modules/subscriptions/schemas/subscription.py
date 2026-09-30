"""Pydantic v2 schemas for the subscriptions module."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SubscriptionItemRequest(BaseModel):
    """One line of a new subscription."""

    variant_id: uuid.UUID
    quantity: int = Field(1, ge=1, le=10_000)
    product_name: str | None = Field(None, max_length=500)


class CreateSubscriptionRequest(BaseModel):
    """Payload for creating a subscription."""

    name: str = Field(..., min_length=1, max_length=200)
    interval: str = Field(..., description="weekly|monthly|quarterly|yearly|custom_days")
    interval_count: int = Field(1, ge=1, le=24)
    custom_interval_days: int | None = Field(None, ge=1, le=365)
    items: list[SubscriptionItemRequest] = Field(..., min_length=1)
    saved_method_id: uuid.UUID | None = None
    shipping_address_snapshot: dict[str, Any] | None = None
    notes: str | None = Field(None, max_length=2000)


class SubscriptionItemResponse(BaseModel):
    """One line of an existing subscription.

    ``unit_price_rial`` is the raw DB column: ``ProductVariant.price`` copied
    verbatim, which is Rial. Verified against live data -- ``order_items.unit_price``
    equals that column exactly -- so the name is correct and consumers divide by
    10 to display it, the same as the catalog API does on the way out.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    variant_id: uuid.UUID
    product_name: str
    sku: str
    quantity: int
    unit_price_rial: int


class SubscriptionBillingResponse(BaseModel):
    """One billing cycle's outcome."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    period_index: int
    status: str
    amount_rial: int
    order_id: uuid.UUID | None = None
    payment_id: uuid.UUID | None = None
    attempt_count: int
    last_error: str | None = None
    billed_at: datetime | None = None
    renewal_notified: bool
    created_at: datetime


class SubscriptionResponse(BaseModel):
    """A subscription as returned to its owner."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    status: str
    interval: str
    interval_count: int
    custom_interval_days: int | None = None
    saved_method_id: uuid.UUID | None = None
    total_per_cycle: int
    started_at: datetime
    next_billing_at: datetime | None = None
    last_billed_at: datetime | None = None
    cancelled_at: datetime | None = None
    cancelled_reason: str | None = None
    failure_count: int
    notes: str | None = None
    items: list[SubscriptionItemResponse] = Field(default_factory=list)
    created_at: datetime

    @classmethod
    def from_model(cls, sub: Any) -> SubscriptionResponse:
        """Build the response, mapping enums to their string values."""
        return cls(
            id=sub.id,
            name=sub.name,
            status=sub.status.value,
            interval=sub.interval.value,
            interval_count=sub.interval_count,
            custom_interval_days=sub.custom_interval_days,
            saved_method_id=sub.saved_method_id,
            total_per_cycle=sub.total_per_cycle,
            started_at=sub.started_at,
            next_billing_at=sub.next_billing_at,
            last_billed_at=sub.last_billed_at,
            cancelled_at=sub.cancelled_at,
            cancelled_reason=sub.cancelled_reason,
            failure_count=sub.failure_count,
            notes=sub.notes,
            items=[SubscriptionItemResponse.model_validate(i) for i in sub.items],
            created_at=sub.created_at,
        )


class SubscriptionDetailResponse(SubscriptionResponse):
    """A subscription plus its billing history (account detail view)."""

    billings: list[SubscriptionBillingResponse] = Field(default_factory=list)


class CancelSubscriptionRequest(BaseModel):
    """Optional cancellation reason."""

    reason: str | None = Field(None, max_length=500)


class SubscriptionRunResponse(BaseModel):
    """Summary of one manual billing run (admin)."""

    due: int
    paid: int
    failed: int
    skipped: int
    errors: int

