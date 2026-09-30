"""Pydantic v2 schemas for the price snapshot API."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class PriceSnapshotLineItem(BaseModel):
    """Single line item in the frozen price breakdown."""

    variant_id: str
    product_name: str
    quantity: int
    unit_price_rial: int = Field(description="Unit price (Rial)")
    line_total_rial: int = Field(description="quantity × unit_price (Rial)")
    discount_amount_rial: int = Field(0, description="Discount applied (Rial)")
    discount_code: str | None = None
    tax_amount_rial: int = Field(0, description="Tax on this line (Rial)")
    tax_rate_percent: int = Field(0, description="Tax rate as integer percent")


class PriceSnapshotResponse(BaseModel):
    """Complete frozen pricing breakdown for an order."""

    id: uuid.UUID
    order_id: uuid.UUID
    currency: str
    lines: list[PriceSnapshotLineItem]
    subtotal_rial: int = Field(description="Sum of line totals before discount (Rial)")
    total_discount_rial: int = Field(description="Sum of all discounts (Rial)")
    total_tax_rial: int = Field(description="Sum of all taxes (Rial)")
    shipping_rial: int = Field(description="Shipping cost (Rial)")
    grand_total_rial: int = Field(description="Final amount customer pays (Rial)")
    snapshot_hash: str = Field(description="SHA-256 tamper-detection hash")
    hash_valid: bool = Field(description="True if recomputed hash matches stored hash")
    created_at: datetime

    class Config:
        from_attributes = True
