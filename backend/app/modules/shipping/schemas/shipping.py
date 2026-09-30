"""Pydantic v2 schemas for the Shipping module."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

# ── Shipping Method ────────────────────────────────────────────────────────


class ShippingMethodResponse(BaseModel):
    """A single shipping method (e.g., Post Pishtaz, Tipax)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    provider: str | None = None
    description: str | None = None
    is_active: bool
    estimated_days_min: int
    estimated_days_max: int
    created_at: datetime
    updated_at: datetime


# ── Shipping Rate ──────────────────────────────────────────────────────────


class ShippingRateResponse(BaseModel):
    """Rate rule record for a shipping method."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    method_id: uuid.UUID
    province: str | None = None
    min_weight: float | None = None
    max_weight: float | None = None
    min_order_amount: int | None = None
    price: int = Field(description="Price in Rials")


# ── Quote ──────────────────────────────────────────────────────────────────


class ShippingQuoteRequest(BaseModel):
    """Parameters for calculating shipping cost."""

    province: str = Field(..., min_length=1, max_length=100, description="Destination province")
    weight: float = Field(..., gt=0, description="Total weight in kilograms")
    order_amount: int = Field(..., ge=0, description="Cart/order subtotal in Rials")


class ShippingQuoteMethodItem(BaseModel):
    """One shipping option with its calculated price."""

    method_id: uuid.UUID
    name: str
    slug: str
    provider: str | None = None
    estimated_days_min: int
    estimated_days_max: int
    price: int = Field(description="Calculated shipping price in Rials")
    is_free: bool = Field(default=False, description="Whether free-shipping threshold was met")


class ShippingQuoteResponse(BaseModel):
    """All available shipping methods with calculated prices for the given parameters."""

    province: str
    weight: float
    order_amount: int
    methods: list[ShippingQuoteMethodItem]


# ── Shipment Items ─────────────────────────────────────────────────────────


class ShipmentItemResponse(BaseModel):
    """Individual item within a shipment."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    order_item_id: uuid.UUID
    quantity: int


class ShipmentItemCreate(BaseModel):
    """Item to include in a new shipment."""

    order_item_id: uuid.UUID
    quantity: int = Field(..., ge=1)


# ── Shipment ───────────────────────────────────────────────────────────────


class ShipmentResponse(BaseModel):
    """Physical shipment record with tracking info."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    order_id: uuid.UUID
    method_id: uuid.UUID
    tracking_code: str | None = None
    status: str
    shipped_at: datetime | None = None
    delivered_at: datetime | None = None
    items: list[ShipmentItemResponse] = Field(default_factory=list)
    # -- Delivery mode / COD / pickup (ERP feature #32) --
    delivery_type: str = "home"
    cod_amount_rial: int | None = None
    cod_collected_at: datetime | None = None
    pickup_point_id: uuid.UUID | None = None
    cancelled_at: datetime | None = None
    cancelled_reason: str | None = None
    label_url: str | None = None
    created_at: datetime
    updated_at: datetime


class ShipmentCreateRequest(BaseModel):
    """Admin request to create a new shipment for an order."""

    order_id: uuid.UUID
    method_id: uuid.UUID
    items: list[ShipmentItemCreate] = Field(
        ...,
        min_length=1,
        description="Items to ship (supports partial shipments)",
    )
    tracking_code: str | None = Field(None, max_length=100)
    # -- Shipping upgrade v1 (ERP #32) --
    delivery_type: str = Field(
        "home",
        description="home | pickup_point | cash_on_delivery",
    )
    pickup_point_id: uuid.UUID | None = None


class ShipmentUpdateRequest(BaseModel):
    """Admin request to update a shipment's status or tracking code."""

    status: str | None = Field(None, description="New shipment status")
    tracking_code: str | None = Field(None, max_length=100, description="Carrier tracking code")



# -- Cancellation, pickup points, COD (ERP feature #32) ---------------------


class ShipmentCancelRequest(BaseModel):
    """Cancellation payload. The reason is required by the service."""

    reason: str = Field(..., min_length=3, max_length=500)


class PickupPointResponse(BaseModel):
    """A carrier pickup location offered at checkout."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    provider: str
    external_id: str
    name: str
    city: str
    province: str | None = None
    address: str
    postal_code: str | None = None
    phone: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class PickupPointUpsertRequest(BaseModel):
    """Admin upsert payload for a pickup point (keyed by provider+external_id)."""

    provider: str = Field(..., min_length=1, max_length=100)
    external_id: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=300)
    city: str = Field(..., min_length=1, max_length=100)
    address: str = Field(..., min_length=5)
    province: str | None = Field(None, max_length=100)
    postal_code: str | None = Field(None, max_length=20)
    phone: str | None = Field(None, max_length=20)
    latitude: float | None = None
    longitude: float | None = None
