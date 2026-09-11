"""Pydantic v2 schemas for the Discounts / Coupons module."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# ── Coupon Apply / Remove ──────────────────────────────────────────────────


class CouponApplyRequest(BaseModel):
    """User request to apply a coupon code."""

    code: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Coupon code to validate and apply",
    )


class CouponApplyResponse(BaseModel):
    """Result of applying a coupon."""

    coupon_id: uuid.UUID
    code: str
    discount_amount: int = Field(description="Computed discount in Rials")
    discount_type: str = Field(description="'fixed' or 'percentage'")
    description: str = Field(description="Human-readable description of the discount")


class CouponRemoveRequest(BaseModel):
    """User request to remove a previously applied coupon."""

    code: str = Field(..., min_length=1, max_length=50)


class CouponRemoveResponse(BaseModel):
    """Acknowledgement of coupon removal."""

    code: str
    removed: bool = True


# ── Discount ───────────────────────────────────────────────────────────────


class DiscountResponse(BaseModel):
    """Full admin view of a discount rule."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    type: str
    value: int = Field(description="Discount value (Rials for fixed, basis points for percentage)")
    min_cart_amount: int | None = None
    max_discount: int | None = None
    scope: str
    scope_ids: list[Any] | None = None
    starts_at: datetime
    ends_at: datetime
    is_active: bool
    is_stackable: bool
    usage_limit: int | None = None
    usage_count: int
    priority: int
    created_at: datetime
    updated_at: datetime


class DiscountCreateRequest(BaseModel):
    """Admin request to create a new discount rule."""

    name: str = Field(..., min_length=1, max_length=200)
    type: str = Field(..., description="fixed | percentage | first_order")
    value: int = Field(..., ge=0, description="Discount value in Rials or basis points")
    min_cart_amount: int | None = Field(None, ge=0)
    max_discount: int | None = Field(None, ge=0)
    scope: str = Field(default="global", description="global | product | category | brand | user")
    scope_ids: list[str] | None = None
    starts_at: datetime
    ends_at: datetime
    is_active: bool = True
    is_stackable: bool = False
    usage_limit: int | None = Field(None, ge=0)
    priority: int = Field(default=0)


class DiscountUpdateRequest(BaseModel):
    """Admin request to partially update a discount rule."""

    name: str | None = Field(None, min_length=1, max_length=200)
    value: int | None = Field(None, ge=0)
    min_cart_amount: int | None = None
    max_discount: int | None = None
    scope: str | None = None
    scope_ids: list[str] | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    is_active: bool | None = None
    is_stackable: bool | None = None
    usage_limit: int | None = None
    priority: int | None = None


# ── Coupon (admin) ─────────────────────────────────────────────────────────


class CouponResponse(BaseModel):
    """Admin view of a coupon."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    discount_id: uuid.UUID
    code: str
    is_active: bool
    usage_limit: int | None = None
    usage_count: int
    starts_at: datetime
    ends_at: datetime
    created_at: datetime
    updated_at: datetime


# ── Pagination ─────────────────────────────────────────────────────────────


class PaginationMeta(BaseModel):
    page: int
    page_size: int
    total_items: int
    total_pages: int
    has_next: bool
    has_prev: bool


class DiscountListResponse(BaseModel):
    items: list[DiscountResponse]
    meta: PaginationMeta
