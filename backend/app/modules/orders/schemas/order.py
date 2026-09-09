"""Pydantic v2 schemas for the Orders module."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


# ── Order Item ─────────────────────────────────────────────────────────────


class OrderItemResponse(BaseModel):
    """Single line-item inside an order."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    variant_id: uuid.UUID
    product_name: str
    variant_info: Optional[str] = None
    sku: str
    quantity: int
    unit_price: int = Field(description="Unit price in Rials (BigInteger)")
    total_price: int = Field(description="Line total in Rials (BigInteger)")


# ── Status History / Timeline ──────────────────────────────────────────────


class OrderStatusHistoryResponse(BaseModel):
    """Single status-transition record."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    from_status: Optional[str] = None
    to_status: str
    changed_by: Optional[uuid.UUID] = None
    reason: Optional[str] = None
    extra_data: Optional[dict[str, Any]] = None
    created_at: datetime


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

    shipping_address_snapshot: Optional[dict[str, Any]] = None
    notes: Optional[str] = None
    ip_address: Optional[str] = None

    items: list[OrderItemResponse] = Field(default_factory=list)
    timeline: list[OrderStatusHistoryResponse] = Field(default_factory=list)

    created_at: datetime
    updated_at: datetime


class OrderListItem(BaseModel):
    """Lightweight order summary used in list endpoints (no items/timeline)."""

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
    notes: Optional[str] = Field(
        None,
        max_length=2000,
        description="Internal note / reason for the status change",
    )


# ── Filters ────────────────────────────────────────────────────────────────


class OrderFilterParams(BaseModel):
    """Query parameters for filtering orders."""

    status: Optional[str] = None
    from_date: Optional[datetime] = None
    to_date: Optional[datetime] = None
    min_total: Optional[int] = None
    max_total: Optional[int] = None
    search: Optional[str] = Field(None, description="Search in order_number")


class PaginationParams(BaseModel):
    """Query parameters for pagination."""

    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)
