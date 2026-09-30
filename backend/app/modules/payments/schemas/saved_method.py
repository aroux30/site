"""Pydantic schemas for saved payment methods (tokenized cards).

The response schema deliberately has **no** ``token`` field: the gateway token
is server-side only. A client that could read the token would be one leak away
from a chargeable handle.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.payments.domain.saved_method_models import TokenizationStatus


class SavedPaymentMethodResponse(BaseModel):
    """Customer-facing view of a saved card (never carries the gateway token)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    provider: str
    masked_pan: str | None = None
    last4: str | None = None
    expiry_jalali: str | None = None
    card_holder_name: str | None = None
    bank_name: str | None = None
    status: TokenizationStatus
    is_default: bool
    is_active: bool
    last_used_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class SavedPaymentMethodListResponse(BaseModel):
    """List wrapper for the account page."""

    items: list[SavedPaymentMethodResponse]
    total: int


class TokenizeCardRequest(BaseModel):
    """Start a card-registration flow with a gateway.

    No card data is accepted here: the customer enters the PAN on the
    gateway's own page. This application only learns the resulting token.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    provider: str = Field(..., max_length=50, description="Gateway to tokenize with")
    mobile: str | None = Field(
        None,
        max_length=20,
        description="Optional buyer mobile the gateway may pre-fill",
    )


class TokenizeCardResponse(BaseModel):
    """Result of a card-registration attempt.

    The gateway token is **never** in this response. When a provider completes
    registration synchronously the card is already saved and ``saved_method``
    carries the masked view; when a provider needs the customer to visit its
    own card-entry page, ``requires_redirect`` + ``redirect_url`` are set and
    the token comes back through that provider's server-side callback, never
    through the browser.
    """

    success: bool
    provider: str
    requires_redirect: bool = False
    redirect_url: str | None = None
    saved_method: SavedPaymentMethodResponse | None = None
    error_code: str | None = None
    error_message: str | None = None


class SavedMethodAdminQuery(BaseModel):
    """Admin filter for the saved-methods visibility endpoint."""

    user_id: uuid.UUID | None = None
    provider: str | None = None
    include_inactive: bool = True
    limit: int = Field(100, ge=1, le=500)


class ChargeSavedMethodRequest(BaseModel):
    """Charge a saved card for an order (v1: full order total)."""

    order_id: uuid.UUID
    amount: int = Field(..., gt=0, description="Amount in IRR (must equal the order total)")
    description: str = Field("", max_length=500)
