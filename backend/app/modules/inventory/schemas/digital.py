"""Pydantic v2 schemas for digital cards and tiered pricing (Karta Phase 1/2)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.inventory.domain.digital_models import DigitalCardStatus, DigitalDeliveryType

# ── Digital Card Schemas ──────────────────────────────────────────────────


class DigitalCardCreateRequest(BaseModel):
    """Admin payload to add a single digital card."""

    product_id: uuid.UUID
    pin: str = Field(..., min_length=1, max_length=1000, description="Plaintext PIN or credential")
    serial_number: str | None = Field(None, max_length=128)
    delivery_type: DigitalDeliveryType = DigitalDeliveryType.UNIQUE
    max_uses: int = Field(1, ge=1, description="Max allocations for shared accounts")
    expire_at: datetime | None = None
    file_path: str | None = None


class DigitalCardResponse(BaseModel):
    """Admin representation of a digital card (PIN is NEVER exposed here)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    product_id: uuid.UUID
    delivery_type: DigitalDeliveryType
    serial_number: str | None = None
    card_hash: str
    status: DigitalCardStatus
    max_uses: int
    used_count: int
    assigned_order_id: uuid.UUID | None = None
    expire_at: datetime | None = None
    used_at: datetime | None = None
    reading_at: datetime | None = None
    created_at: datetime


class DeliveredCardResponse(BaseModel):
    """Customer representation of a delivered digital card with decrypted PIN."""

    id: uuid.UUID
    serial_number: str | None = None
    pin: str = Field(..., description="Decrypted PIN or access credential")
    delivery_type: DigitalDeliveryType
    file_download_url: str | None = None
    delivered_at: datetime | None = None
    reading_at: datetime | None = None


class MarkCardReadResponse(BaseModel):
    """Response after marking a card as viewed (Karta legal reading flag)."""

    id: uuid.UUID
    reading_at: datetime
    message: str = "Card marked as viewed"


# ── Bulk Import Schemas ───────────────────────────────────────────────────


class BulkImportRowResult(BaseModel):
    row_number: int
    serial_number: str | None = None
    status: str  # "success", "duplicate_skipped", "error"
    detail: str | None = None


class BulkImportSummaryResponse(BaseModel):
    """Summary result of CSV/Excel bulk card import."""

    total_rows: int
    imported_count: int
    duplicate_count: int
    error_count: int
    details: list[BulkImportRowResult] = Field(default_factory=list)


# ── Tiered Pricing Schemas ────────────────────────────────────────────────


class PriceTierCreateRequest(BaseModel):
    """Admin payload to set volume discount tier."""

    product_id: uuid.UUID
    from_qty: int = Field(..., ge=1)
    to_qty: int | None = Field(None, ge=1)
    unit_price: int = Field(..., ge=0, description="Unit price in IRR")


class PriceTierResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    product_id: uuid.UUID
    from_qty: int
    to_qty: int | None
    unit_price: int
    created_at: datetime


class DynamicPriceCalculationResponse(BaseModel):
    """Real-time calculation response for cart quantity (Karta ``findPrice``)."""

    product_id: uuid.UUID
    quantity: int
    unit_price: int
    total_price: int
    tier_applied: bool
    from_qty: int | None = None
    to_qty: int | None = None


# ── Category Custom Fields ────────────────────────────────────────────────


class CategoryCustomFieldCreateRequest(BaseModel):
    category_id: uuid.UUID
    field_key: str = Field(..., min_length=1, max_length=64)
    label: str = Field(..., min_length=1, max_length=200)
    field_type: str = Field("text", max_length=32)
    is_required: bool = False
    position: int = 0


class CategoryCustomFieldResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    category_id: uuid.UUID
    field_key: str
    label: str
    field_type: str
    is_required: bool
    position: int
