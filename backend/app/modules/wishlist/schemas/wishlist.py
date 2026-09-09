"""Pydantic schemas for the wishlist module."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ── Request schemas ───────────────────────────────────────────────────────


class WishlistAddRequest(BaseModel):
    """Payload for adding a product to the wishlist."""

    product_id: str = Field(..., description="UUID of the product to add")


# ── Response schemas ──────────────────────────────────────────────────────


class WishlistItemResponse(BaseModel):
    """Single item in a wishlist."""

    id: str
    product_id: str
    product_name: Optional[str] = None
    product_slug: Optional[str] = None
    product_image_url: Optional[str] = None
    product_price: Optional[int] = None
    product_is_active: Optional[bool] = None
    added_at: datetime

    class Config:
        from_attributes = True


class WishlistResponse(BaseModel):
    """Complete wishlist for a user."""

    id: str
    name: str = "default"
    items: list[WishlistItemResponse] = Field(default_factory=list)
    total_items: int = 0

    class Config:
        from_attributes = True


class WishlistCheckResponse(BaseModel):
    """Response for is-in-wishlist check."""

    in_wishlist: bool
    product_id: str
