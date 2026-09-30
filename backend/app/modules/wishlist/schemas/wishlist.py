"""Pydantic schemas for the wishlist module."""

from __future__ import annotations

from datetime import datetime

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
    product_name: str | None = None
    product_slug: str | None = None
    product_image_url: str | None = None
    product_price: int | None = None
    product_is_active: bool | None = None
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
