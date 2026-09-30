"""Pydantic schemas for the pricing module (price lists and rules)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.pricing.domain.models import CustomerSegment


class PriceListRuleCreate(BaseModel):
    """Create a rule inside a price list."""

    product_id: uuid.UUID | None = None
    variant_id: uuid.UUID | None = None
    min_quantity: int = Field(0, ge=0)
    fixed_price_rial: int | None = Field(None, ge=0)
    discount_bp: int | None = Field(None, ge=0, le=10_000)

    @model_validator(mode="after")
    def exactly_one_pricing_strategy(self) -> "PriceListRuleCreate":
        if self.fixed_price_rial is not None and self.discount_bp is not None:
            raise ValueError("fixed_price_rial and discount_bp are mutually exclusive")
        if self.product_id is not None and self.variant_id is not None:
            raise ValueError("a rule scopes to a product OR a variant, not both")
        return self


class PriceListRuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    price_list_id: uuid.UUID
    product_id: uuid.UUID | None
    variant_id: uuid.UUID | None
    min_quantity: int
    fixed_price_rial: int | None
    discount_bp: int | None


class PriceListCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    segment: CustomerSegment
    priority: int = Field(100, ge=0)
    is_active: bool = True
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    rules: list[PriceListRuleCreate] = []


class PriceListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    segment: CustomerSegment
    priority: int
    is_active: bool
    valid_from: datetime | None
    valid_to: datetime | None
    created_at: datetime
    updated_at: datetime


class PriceListDetailResponse(PriceListResponse):
    rules: list[PriceListRuleResponse] = []


class PriceListListResponse(BaseModel):
    items: list[PriceListResponse]
    total: int
