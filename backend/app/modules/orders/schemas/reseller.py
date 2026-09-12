"""Pydantic v2 schemas for B2B Reseller API Hub (Karta Phase 4)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.inventory.schemas.digital import DeliveredCardResponse

# ── Reseller API Key Schemas ──────────────────────────────────────────────


class ResellerApiKeyCreateRequest(BaseModel):
    """Admin payload to create a new partner API key."""

    user_id: uuid.UUID
    name: str = Field(..., min_length=1, max_length=100, description="Partner or company name")
    ip_whitelist: list[str] | None = Field(None, description="Allowed IP addresses")
    initial_credit: int = Field(0, ge=0, description="Initial pre-paid credit in IRR")
    expires_at: datetime | None = None
    rate_limit_per_minute: int = Field(60, ge=1, le=1000)


class ResellerApiKeyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    key_prefix: str
    ip_whitelist: list[str] | None = None
    credit_balance: int
    is_active: bool
    rate_limit_per_minute: int
    expires_at: datetime | None = None
    created_at: datetime


class ResellerApiKeyCreateResponse(ResellerApiKeyResponse):
    """Includes the plaintext API key (revealed only upon creation)."""

    plaintext_api_key: str = Field(..., description="Copy this secret now; it will not be shown again.")


# ── Wholesale Catalog Stock Schemas ───────────────────────────────────────


class ResellerCatalogItem(BaseModel):
    product_id: uuid.UUID
    name: str
    slug: str
    available_stock: int
    is_in_stock: bool


# ── Wholesale Purchase Schemas ────────────────────────────────────────────


class ResellerPurchaseRequest(BaseModel):
    """Payload for automated wholesale card order by partner."""

    product_id: uuid.UUID
    quantity: int = Field(..., ge=1, le=1000, description="Number of digital codes to purchase")
    unit_price: int = Field(..., ge=0, description="Agreed wholesale unit price in IRR")


class ResellerPurchaseResponse(BaseModel):
    order_id: uuid.UUID
    order_number: str
    product_id: uuid.UUID
    quantity: int
    total_cost: int
    remaining_credit: int
    cards: list[DeliveredCardResponse]


class ResellerBalanceResponse(BaseModel):
    credit_balance: int
    currency: str = "IRR"
