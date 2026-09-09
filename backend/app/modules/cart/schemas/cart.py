"""Pydantic v2 schemas for the cart module."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


# ── Cart item detail ───────────────────────────────────────────────────────


class CartItemResponse(BaseModel):
    """Enriched cart line item with variant / product info."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    variant_id: uuid.UUID
    quantity: int
    price_snapshot: int = Field(description="Unit price in Rial at time of add")
    subtotal: int = Field(description="quantity * price_snapshot (Rial)")

    # Enrichment fields (populated by service, not from the ORM model directly)
    product_name: Optional[str] = None
    variant_info: Optional[str] = None
    sku: Optional[str] = None
    current_price: Optional[int] = Field(
        None, description="Live price in Rial — may differ from snapshot"
    )
    image_url: Optional[str] = None
    is_available: Optional[bool] = None

    @property
    def price_toman(self) -> int:
        return self.price_snapshot // 10

    @property
    def subtotal_toman(self) -> int:
        return self.subtotal // 10


# ── Cart ───────────────────────────────────────────────────────────────────


class CartResponse(BaseModel):
    """Full cart with all line items and aggregated totals."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: Optional[uuid.UUID] = None
    session_id: Optional[str] = None
    status: str
    items: list[CartItemResponse] = []
    subtotal: int = Field(0, description="Sum of all line item subtotals (Rial)")
    item_count: int = Field(0, description="Total number of individual items")
    expires_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    @property
    def subtotal_toman(self) -> int:
        return self.subtotal // 10


# ── Mutations ──────────────────────────────────────────────────────────────


class CartItemCreate(BaseModel):
    """Payload for adding an item to the cart."""

    variant_id: uuid.UUID
    quantity: int = Field(1, ge=1, le=100)


class CartItemUpdate(BaseModel):
    """Payload for updating an existing cart item's quantity."""

    quantity: int = Field(..., ge=0, le=100, description="Set to 0 to remove the item")


# ── Merge ──────────────────────────────────────────────────────────────────


class CartMergeRequest(BaseModel):
    """Request to merge a guest cart into the authenticated user's cart."""

    guest_session_id: str = Field(
        ..., min_length=1, max_length=255, description="Session ID of the guest cart"
    )


# ── Validation ─────────────────────────────────────────────────────────────


class CartValidationIssue(BaseModel):
    variant_id: uuid.UUID
    issue: str
    old_value: Optional[Any] = None
    new_value: Optional[Any] = None


class CartValidationResponse(BaseModel):
    """Result of validating every item in the cart against current catalog."""

    is_valid: bool
    issues: list[CartValidationIssue] = []
    cart: CartResponse
