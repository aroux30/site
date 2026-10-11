"""Pydantic v2 schemas for the Orders module."""

from __future__ import annotations

import contextlib
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.modules.orders.domain.models import OrderStatus

# ── Order Item ─────────────────────────────────────────────────────────────


class OrderItemResponse(BaseModel):
    """Single line-item inside an order."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    variant_id: uuid.UUID
    product_name: str
    variant_info: str | None = None
    sku: str
    quantity: int
    unit_price: int = Field(description="Unit price in Rials (BigInteger)")
    total_price: int = Field(description="Line total in Rials (BigInteger)")
    custom_fields: dict[str, Any] | None = Field(
        None, description="Dynamic category-field answers captured at checkout"
    )


# ── Status History / Timeline ──────────────────────────────────────────────


class OrderStatusHistoryResponse(BaseModel):
    """Single status-transition record."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    from_status: str | None = None
    to_status: str
    changed_by: uuid.UUID | None = None
    actor_id: uuid.UUID | None = None
    correlation_id: str | None = None
    reason: str | None = None
    extra_data: dict[str, Any] | None = None
    created_at: datetime

    @model_validator(mode="before")
    @classmethod
    def populate_audit_fields(cls, data: Any) -> Any:
        if hasattr(data, "changed_by"):
            cb = getattr(data, "changed_by", None)
            if not getattr(data, "actor_id", None):
                with contextlib.suppress(Exception):
                    data.actor_id = cb
            extra = getattr(data, "extra_data", None)
            if isinstance(extra, dict) and "correlation_id" in extra:
                with contextlib.suppress(Exception):
                    data.correlation_id = extra["correlation_id"]
        elif isinstance(data, dict):
            if "changed_by" in data and "actor_id" not in data:
                data["actor_id"] = data["changed_by"]
            extra = data.get("extra_data")
            if (
                isinstance(extra, dict)
                and "correlation_id" in extra
                and "correlation_id" not in data
            ):
                data["correlation_id"] = extra["correlation_id"]
        return data


class OrderTimelineResponse(BaseModel):
    """Complete timeline for an order."""

    order_id: uuid.UUID
    order_number: str
    current_status: str
    events: list[OrderStatusHistoryResponse]


# ── Order ──────────────────────────────────────────────────────────────────


class OrderResponse(BaseModel):
    """Full order representation including items and timeline."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    order_number: str
    status: str
    user_id: uuid.UUID

    subtotal: int = Field(description="Subtotal in Rials")
    shipping_cost: int = Field(description="Shipping cost in Rials")
    tax: int = Field(description="Tax in Rials")
    discount_amount: int = Field(description="Total discount in Rials")
    total: int = Field(description="Grand total in Rials")

    shipping_address_snapshot: dict[str, Any] | None = None
    notes: str | None = None
    ip_address: str | None = None

    items: list[OrderItemResponse] = Field(default_factory=list)
    timeline: list[OrderStatusHistoryResponse] = Field(default_factory=list)

    created_at: datetime
    updated_at: datetime

    @field_validator("shipping_address_snapshot")
    @classmethod
    def mask_shipping_address(cls, v: dict[str, Any] | None) -> dict[str, Any] | None:
        if isinstance(v, dict):
            from app.core.security.data_protection import mask_address

            masked = dict(v)
            for addr_key in ("address", "full_address", "street_address", "postal_address"):
                if masked.get(addr_key):
                    masked[addr_key] = mask_address(str(masked[addr_key]))
            return masked
        return v


class OrderListItem(BaseModel):
    """Lightweight order summary used in list endpoints (no timeline)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    order_number: str
    status: str
    user_id: uuid.UUID
    subtotal: int
    shipping_cost: int
    tax: int
    discount_amount: int
    total: int
    created_at: datetime
    updated_at: datetime
    # Admin-list extras; None in customer-facing list responses
    items_count: int | None = None
    # Real line-item briefs (admin lists only) so kanban/detail surfaces can
    # show actual lines instead of fabricating placeholders (QA B20).
    items: list[OrderItemResponse] | None = None
    customer_name: str | None = None
    customer_phone: str | None = None


class PaginationMeta(BaseModel):
    """Pagination metadata."""

    page: int
    page_size: int
    total_items: int
    total_pages: int
    has_next: bool
    has_prev: bool


class OrderListResponse(BaseModel):
    """Paginated list of orders."""

    items: list[OrderListItem]
    meta: PaginationMeta


# ── Requests ───────────────────────────────────────────────────────────────


class OrderCancelRequest(BaseModel):
    """User request to cancel an order."""

    reason: str = Field(
        ...,
        min_length=3,
        max_length=1000,
        description="Reason for cancellation",
    )


class AdminOrderUpdateRequest(BaseModel):
    """Admin request to update order status."""

    status: str = Field(..., description="New order status")
    notes: str | None = Field(
        None,
        max_length=2000,
        description="Internal note / reason for the status change",
    )


class OrderBulkStatusRequest(BaseModel):
    """Admin request to move several orders to one status.

    One target for the whole batch: a bulk action that allowed a per-order
    target would let the operator smuggle a refund onto one order inside an
    otherwise routine "mark as shipped" run.
    """

    ids: list[uuid.UUID] = Field(..., min_length=1, max_length=100)
    status: str = Field(..., description="Target order status applied to every id")
    notes: str | None = Field(
        None,
        max_length=2000,
        description="Internal note / reason recorded on every status change",
    )


class OrderBulkStatusResultItem(BaseModel):
    """Outcome for one order in a bulk status run."""

    order_id: uuid.UUID
    order_number: str | None = None
    status: OrderStatus
    from_status: OrderStatus | None = None
    success: bool
    error_code: str | None = None
    detail: str | None = None


class OrderBulkStatusResult(BaseModel):
    """Per-order outcome of a bulk status run.

    ``succeeded``/``failed`` are the whole truth of the batch: a partial run is
    reported as partial, never as a blanket success. ``failed`` carries the
    human-readable reason per order (an illegal transition, a delivered
    digital good that blocks cancellation, a missing row).
    """

    requested: int
    succeeded: int
    failed: int
    items: list[OrderBulkStatusResultItem]


# ── Admin board (kanban) ───────────────────────────────────────────────────


class AdminOrderStatusCount(BaseModel):
    """One column's header numbers for the admin orders board."""

    status: str
    count: int
    total: int = Field(description="Sum of order totals for this status, in Rials")


class AdminOrderStatsResponse(BaseModel):
    """Per-status counts and sums across ALL orders, for the board headers.

    The board fetches each column separately (a status with 24k rows cannot
    ship to the browser), so the column headers cannot be counted from the
    loaded rows — this endpoint is the one place that counts the whole table
    server-side. ``by_status`` carries every status of the OrderStatus enum,
    zero-filled, so the UI never has to guess whether a missing key means
    "zero orders" or "the endpoint forgot it".
    """

    by_status: list[AdminOrderStatusCount]
    total_orders: int
    total_revenue_rials: int = Field(
        description="Sum of totals for revenue-bearing statuses only (excludes canceled/refunded)"
    )


class AdminOrderPaymentSummary(BaseModel):
    """A payment row as the admin order drawer shows it."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    amount: int = Field(description="Amount in Rials")
    status: str
    provider: str
    provider_transaction_id: str | None = None
    created_at: datetime


class AdminOrderDetailResponse(BaseModel):
    """Full admin view of one order.

    Two deliberate differences from the customer-facing ``OrderResponse``:

    1. The shipping address snapshot is NOT masked. The customer schema
       masks street-level detail for non-admin DTOs; an operator packing a
       parcel needs the full address, and this route is gated behind
       ``orders:read``. This class is standalone (it does not inherit
       ``OrderResponse``) precisely so the masking validator cannot apply —
       the test suite asserts the returned address is unmasked.
    2. Payments are attached (status, provider, amount) so the operator can
       see whether money actually arrived before advancing the order — the
       list endpoint carries no payment info and the old board invented it.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    order_number: str
    status: str
    user_id: uuid.UUID

    subtotal: int
    shipping_cost: int
    tax: int
    discount_amount: int
    total: int

    shipping_address_snapshot: dict[str, Any] | None = None
    notes: str | None = None
    ip_address: str | None = None

    items: list[OrderItemResponse] = Field(default_factory=list)
    timeline: list[OrderStatusHistoryResponse] = Field(default_factory=list)
    payments: list[AdminOrderPaymentSummary] = Field(default_factory=list)

    customer_name: str | None = None
    customer_phone: str | None = None

    created_at: datetime
    updated_at: datetime


# ── Filters ────────────────────────────────────────────────────────────────


class OrderFilterParams(BaseModel):
    """Query parameters for filtering orders."""

    status: str | None = None
    statuses: list[str] | None = Field(
        None,
        description=(
            "Several statuses at once, as a comma-separated list. The admin "
            "board groups pending/confirmed/processing/shipped/delivered into «در حال "
            "پردازش» lane, which needs a single query — fanning out to one "
            "request per status on the client would page each status "
            "separately and the concatenated lane would skip and repeat rows."
        ),
    )
    from_date: datetime | None = None
    to_date: datetime | None = None
    min_total: int | None = None
    max_total: int | None = None
    search: str | None = Field(None, description="Search in order_number")


class PaginationParams(BaseModel):
    """Query parameters for pagination."""

    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)
