"""Pydantic v2 schemas for Fintech: Card2Card, Direct Pay, Gateways, and Error resolution (Karta Phase 3/5)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.modules.payments.domain.fintech_models import DirectInvoiceStatus, ReceiptReviewStatus

# ── Card-to-Card Receipt Schemas ──────────────────────────────────────────


class CardTransferReceiptCreate(BaseModel):
    """Customer payload to submit a manual card-to-card payment receipt."""

    order_id: uuid.UUID
    amount: int = Field(..., ge=10_000, description="Amount transferred in IRR")
    tracking_code: str = Field(..., min_length=1, max_length=100, description="Bank transfer reference number")
    source_card_last4: str = Field(..., min_length=4, max_length=4, description="Last 4 digits of source debit card")
    destination_card_number: str | None = Field(None, max_length=20)
    receipt_image_url: str | None = Field(None, max_length=500, description="Uploaded bank receipt image URL")


class CardTransferReceiptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    order_id: uuid.UUID
    user_id: uuid.UUID
    amount: int
    tracking_code: str
    source_card_last4: str
    destination_card_number: str | None = None
    receipt_image_url: str | None = None
    status: ReceiptReviewStatus
    admin_notes: str | None = None
    reviewed_at: datetime | None = None
    created_at: datetime


class CardTransferReceiptReviewRequest(BaseModel):
    """Admin review decision for a submitted card transfer receipt."""

    is_approved: bool
    admin_notes: str | None = Field(None, max_length=1000)


# ── Direct Pay Invoice Schemas ────────────────────────────────────────────


class DirectInvoiceCreateRequest(BaseModel):
    """Payload to create a quick invoice without shopping cart."""

    amount: int = Field(..., ge=10_000, description="Invoice amount in IRR")
    title: str = Field(..., min_length=1, max_length=250, description="Purpose or title of payment")
    description: str | None = Field(None, max_length=2000)
    payer_name: str | None = Field(None, max_length=150)
    payer_mobile: str | None = Field(None, max_length=20)
    ttl_hours: int = Field(72, ge=1, le=720)


class DirectInvoiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    invoice_number: str
    user_id: uuid.UUID | None = None
    amount: int
    title: str
    description: str | None = None
    payer_name: str | None = None
    payer_mobile: str | None = None
    status: DirectInvoiceStatus
    payment_id: uuid.UUID | None = None
    expire_at: datetime | None = None
    paid_at: datetime | None = None
    created_at: datetime


# ── Gateway Setting Schemas ───────────────────────────────────────────────


class GatewaySettingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    provider_key: str
    title_fa: str
    is_active: bool
    is_default: bool
    priority: int
    min_amount: int
    max_amount: int
    created_at: datetime


class GatewaySettingUpdateRequest(BaseModel):
    """Admin configuration update for a payment gateway."""

    title_fa: str = Field(..., min_length=1, max_length=100)
    is_active: bool = True
    is_default: bool = False
    priority: int = Field(0, ge=0)
    min_amount: int = Field(10_000, ge=0)
    max_amount: int = Field(500_000_000, ge=0)
    credentials: dict[str, Any] | None = None


# ── Gateway Error Resolution Schemas ──────────────────────────────────────


class GatewayErrorResolveRequest(BaseModel):
    provider: str
    error_code: str | int


class GatewayErrorResolveResponse(BaseModel):
    provider: str
    error_code: str
    persian_message: str
