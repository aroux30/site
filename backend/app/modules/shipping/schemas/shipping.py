"""Pydantic v2 schemas for the Shipping module."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ── Shipping Method ────────────────────────────────────────────────────────


class ShippingMethodResponse(BaseModel):
    """A single shipping method (e.g., Post Pishtaz, Tipax)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    provider: Optional[str] = None
    description: Optional[str] = None
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
    province: Optional[str] = None
    min_weight: Optional[float] = None
    max_weight: Optional[float] = None
    min_order_amount: Optional[int] = None
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
    provider: Optional[str] = None
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
    tracking_code: Optional[str] = None
    status: str
    shipped_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    items: list[ShipmentItemResponse] = Field(default_factory=list)
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
    tracking_code: Optional[str] = Field(None, max_length=100)


class ShipmentUpdateRequest(BaseModel):
    """Admin request to update a shipment's status or tracking code."""

    status: Optional[str] = Field(None, description="New shipment status")
    tracking_code: Optional[str] = Field(None, max_length=100, description="Carrier tracking code")
