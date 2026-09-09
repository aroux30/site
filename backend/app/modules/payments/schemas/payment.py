"""Pydantic v2 schemas for the payment module."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.modules.payments.domain.models import (
    PaymentProvider,
    PaymentStatus,
    RefundStatus,
)


# ── Request Schemas ───────────────────────────────────────────────────────


class PaymentCreateRequest(BaseModel):
    """Create a new payment for an order."""

    model_config = ConfigDict(str_strip_whitespace=True)

    order_id: uuid.UUID = Field(..., description="Order UUID to pay for")
    provider: PaymentProvider = Field(
        ..., description="Payment gateway provider"
    )
    amount: int = Field(
        ..., gt=0, description="Amount in IRR (Rials) as integer"
    )
    idempotency_key: Optional[str] = Field(
        None,
        max_length=255,
        description="Client-generated idempotency key to prevent duplicate payments",
    )


class PaymentVerifyRequest(BaseModel):
    """Data submitted to verify a payment after gateway redirect."""

    authority: str = Field(
        ..., max_length=255, description="Authority token from the payment gateway"
    )
    status: str = Field(
        ..., max_length=50, description="Status string from the gateway callback"
    )


class PaymentCallbackData(BaseModel):
    """Raw callback / webhook payload from a payment gateway."""

    model_config = ConfigDict(extra="allow")

    authority: Optional[str] = None
    status: Optional[str] = None
    track_id: Optional[str] = None
    id: Optional[str] = None
    order_id: Optional[str] = None
    amount: Optional[int] = None
    card_no: Optional[str] = None
    hashed_card_no: Optional[str] = None
    date: Optional[str] = None
    extra: Optional[dict[str, Any]] = None
    payment_id: Optional[Any] = None
    payment_status: Optional[str] = None


class CardReceiptSubmitRequest(BaseModel):
    """Customer submission of bank transfer receipt / reference code."""

    model_config = ConfigDict(str_strip_whitespace=True)

    tracking_code: str = Field(
        ...,
        min_length=3,
        max_length=100,
        description="Bank reference number / tracking code (کد پیگیری / شماره ارجاع)",
    )
    card_pan: Optional[str] = Field(
        None,
        max_length=30,
        description="Sender card PAN or masked card number (شماره کارت واریز کننده)",
    )
    receipt_image_url: Optional[str] = Field(
        None,
        max_length=500,
        description="URL or path to uploaded receipt image (تصویر فیش)",
    )
    notes: Optional[str] = Field(
        None,
        max_length=500,
        description="Optional customer notes regarding the transfer",
    )


class PaymentRejectRequest(BaseModel):
    """Admin rejection details for a card-to-card payment."""

    model_config = ConfigDict(str_strip_whitespace=True)

    reason: Optional[str] = Field(
        None,
        max_length=500,
        description="Reason for rejecting the payment / receipt",
    )


class RefundRequest(BaseModel):
    """Request a refund for a completed payment."""

    payment_id: uuid.UUID = Field(..., description="Payment UUID to refund")
    amount: int = Field(
        ..., gt=0, description="Refund amount in IRR (must be <= payment amount)"
    )
    reason: Optional[str] = Field(
        None, max_length=1000, description="Reason for the refund"
    )


# ── Response Schemas ──────────────────────────────────────────────────────


class PaymentResponse(BaseModel):
    """Payment record returned to the client."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    order_id: uuid.UUID
    amount: int
    currency: str
    provider: PaymentProvider
    status: PaymentStatus
    gateway_url: Optional[str] = None
    authority: Optional[str] = None
    provider_transaction_id: Optional[str] = None
    idempotency_key: Optional[str] = None
    extra_data: Optional[dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime


class RefundResponse(BaseModel):
    """Refund record returned to the client."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    payment_id: uuid.UUID
    order_id: uuid.UUID
    amount: int
    reason: Optional[str] = None
    status: RefundStatus
    processed_by: Optional[uuid.UUID] = None
    processed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class PaymentMethodInfo(BaseModel):
    """Description of an available payment method."""

    provider: PaymentProvider
    name: str
    name_fa: str
    is_enabled: bool
    icon: Optional[str] = None
    description: Optional[str] = None
    instructions: Optional[str] = None
    instructions_fa: Optional[str] = None


class PaymentMethodsResponse(BaseModel):
    """List of available payment methods."""

    methods: list[PaymentMethodInfo]
