"""Pydantic v2 schemas for the Recommendation & AI module."""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.catalog.schemas.catalog import ProductResponse


class RecommendedProductItem(BaseModel):
    """Product item with recommendation relevance score and explanation."""

    model_config = ConfigDict(from_attributes=True)

    product_id: uuid.UUID
    product: ProductResponse
    score: float = Field(default=0.0, description="Relevance score (typically 0.0 to 1.0)")
    reason: str | None = Field(
        default=None,
        description="Reason or rationale for this recommendation",
    )

    @model_validator(mode="before")
    @classmethod
    def populate_product_id(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "product_id" not in data and "product" in data:
                prod = data["product"]
                if isinstance(prod, dict):
                    data["product_id"] = prod.get("id")
                elif hasattr(prod, "id"):
                    data["product_id"] = prod.id
        return data


class RecommendationResponse(BaseModel):
    """General recommendation response containing a list of products with scores and reasons."""

    model_config = ConfigDict(from_attributes=True)

    items: list[RecommendedProductItem] = Field(
        default_factory=list,
        description="List of recommended products with relevance scores and reasons",
    )
    total: int = Field(default=0, ge=0, description="Total number of items recommended")

    @model_validator(mode="before")
    @classmethod
    def compute_total(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "total" not in data and "items" in data and isinstance(data["items"], list):
                data["total"] = len(data["items"])
        return data

    def __iter__(self):  # type: ignore[no-untyped-def]
        return iter(self.items)

    def __len__(self) -> int:
        return len(self.items)

    def __getitem__(self, index: int) -> RecommendedProductItem:
        return self.items[index]


class SimilarProductsRequest(BaseModel):
    """Query/request schema for finding products similar to a given product."""

    model_config = ConfigDict(str_strip_whitespace=True)

    product_id: uuid.UUID = Field(..., description="Source product ID to find similarities for")
    limit: int = Field(default=6, ge=1, le=50, description="Maximum number of similar products to return")


class SimilarProductsResponse(RecommendationResponse):
    """Response containing products similar to the requested product."""

    product_id: uuid.UUID | None = Field(
        default=None,
        description="Source product ID for which similarities were computed",
    )


class PersonalizedFeedResponse(RecommendationResponse):
    """Response containing personalized product recommendations for a specific user."""

    user_id: uuid.UUID | None = Field(
        default=None,
        description="User ID for whom the personalized feed was generated",
    )


class FrequentlyBoughtTogetherResponse(RecommendationResponse):
    """Response containing products frequently purchased with a given product."""

    product_id: uuid.UUID | None = Field(
        default=None,
        description="Source product ID for co-occurrence analysis",
    )


class TrendingProductsResponse(RecommendationResponse):
    """Response containing currently trending products across the platform."""

    timeframe_days: int = Field(
        default=14,
        ge=1,
        description="Number of days looked back to determine trending products",
    )
