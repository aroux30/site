"""Pydantic v2 schemas for the checkout module."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

# ── Quote ──────────────────────────────────────────────────────────────────


class CheckoutQuoteRequest(BaseModel):
    """Input for calculating an order quote before committing."""

    cart_id: uuid.UUID
    address_id: uuid.UUID
    shipping_method_id: uuid.UUID
    coupon_code: str | None = Field(None, max_length=50, description="Optional coupon code")


class CheckoutLineItem(BaseModel):
    """Line-item breakdown in the quote."""

    variant_id: uuid.UUID
    product_name: str
    sku: str
    quantity: int
    unit_price: int = Field(description="Unit price (Rial)")
    subtotal: int = Field(description="quantity * unit_price (Rial)")


class CheckoutQuoteResponse(BaseModel):
    """Complete cost breakdown before placing the order."""

    items: list[CheckoutLineItem] = []
    subtotal: int = Field(description="Sum of line item subtotals (Rial)")
    shipping_cost: int = Field(description="Shipping fee (Rial)")
    discount_amount: int = Field(0, description="Discount deducted (Rial)")
    tax: int = Field(0, description="Tax (Rial) — currently 0 for Iran domestic")
    total: int = Field(description="Grand total (Rial)")
    coupon_applied: str | None = None

    @property
    def total_toman(self) -> int:
        return self.total // 10

    @property
    def subtotal_toman(self) -> int:
        return self.subtotal // 10


# ── Validation ─────────────────────────────────────────────────────────────


class CheckoutValidationIssue(BaseModel):
    field: str
    message: str


class CheckoutValidationResponse(BaseModel):
    is_valid: bool
    issues: list[CheckoutValidationIssue] = []


# ── Create Order ───────────────────────────────────────────────────────────


class CreateOrderRequest(BaseModel):
    """Full order creation payload. The *idempotency_key* ensures the same
    request is not processed twice (e.g. double-click protection)."""

    cart_id: uuid.UUID
    address_id: uuid.UUID
    shipping_method_id: uuid.UUID
    coupon_code: str | None = Field(None, max_length=50)
    payment_method: str = Field(
        ..., description="Payment method slug (e.g. 'zarinpal', 'idpay', 'wallet')"
    )
    idempotency_key: str = Field(
        ...,
        min_length=8,
        max_length=255,
        description="Client-generated unique key to prevent duplicate orders",
    )
    notes: str | None = Field(None, max_length=2000, description="Customer note")


class CreateOrderResponse(BaseModel):
    """Confirmation of order creation."""

    order_id: uuid.UUID
    order_number: str
    status: str
    subtotal: int
    shipping_cost: int
    discount_amount: int
    tax: int
    total: int
    payment_url: str | None = Field(
        None, description="Gateway redirect URL (null if wallet or COD)"
    )
    created_at: datetime

    @property
    def total_toman(self) -> int:
        return self.total // 10
