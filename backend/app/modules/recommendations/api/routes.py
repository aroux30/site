"""Recommendations & AI module API routes."""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.security.dependencies import get_current_user_id
from app.modules.recommendations.application.recommendation_service import (
    recommendation_service,
)
from app.modules.recommendations.schemas.recommendations import (
    FrequentlyBoughtTogetherResponse,
    PersonalizedFeedResponse,
    SimilarProductsResponse,
    TrendingProductsResponse,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger()

router = APIRouter()


# ── Similar Products ─────────────────────────────────────────────────────────


@router.get(
    "/similar/{product_id}",
    response_model=SimilarProductsResponse,
    summary="Get similar products",
    description="Calculate and return products similar to the given product based on category, brand, tag overlap, and price proximity.",
)
@router.get(
    "/recommendations/similar/{product_id}",
    response_model=SimilarProductsResponse,
    include_in_schema=False,
)
async def get_similar_products(
    product_id: uuid.UUID,
    limit: int = Query(default=6, ge=1, le=50, description="Maximum number of similar products to return"),
    db: AsyncSession = Depends(get_db),
) -> SimilarProductsResponse:
    """Retrieve products similar to the requested product ID."""
    return await recommendation_service.get_similar_products(
        db=db,
        product_id=product_id,
        limit=limit,
    )


# ── Frequently Bought Together ───────────────────────────────────────────────


@router.get(
    "/frequently-bought-together/{product_id}",
    response_model=FrequentlyBoughtTogetherResponse,
    summary="Get frequently bought together products",
    description="Analyze order items to find products that frequently co-occur in the same orders as the given product.",
)
@router.get(
    "/recommendations/frequently-bought-together/{product_id}",
    response_model=FrequentlyBoughtTogetherResponse,
    include_in_schema=False,
)
async def get_frequently_bought_together(
    product_id: uuid.UUID,
    limit: int = Query(default=4, ge=1, le=20, description="Maximum number of co-occurring products to return"),
    db: AsyncSession = Depends(get_db),
) -> FrequentlyBoughtTogetherResponse:
    """Retrieve products frequently bought together with the requested product ID."""
    return await recommendation_service.get_frequently_bought_together(
        db=db,
        product_id=product_id,
        limit=limit,
    )


# ── Trending Products ────────────────────────────────────────────────────────


@router.get(
    "/trending",
    response_model=TrendingProductsResponse,
    summary="Get trending products",
    description="Find platform-wide trending products based on order volume and review activity over the last 14 days.",
)
@router.get(
    "/recommendations/trending",
    response_model=TrendingProductsResponse,
    include_in_schema=False,
)
async def get_trending_products(
    limit: int = Query(default=8, ge=1, le=50, description="Maximum number of trending products to return"),
    db: AsyncSession = Depends(get_db),
) -> TrendingProductsResponse:
    """Retrieve top trending products across the platform."""
    return await recommendation_service.get_trending_products(
        db=db,
        limit=limit,
    )


# ── Personalized Recommendations (Requires Auth) ────────────────────────────


@router.get(
    "/for-you",
    response_model=PersonalizedFeedResponse,
    summary="Get personalized recommendations",
    description="Construct a personalized product feed based on the authenticated user's wishlist, recent orders, and category preferences.",
)
@router.get(
    "/recommendations/for-you",
    response_model=PersonalizedFeedResponse,
    include_in_schema=False,
)
async def get_personalized_recommendations(
    user_id: uuid.UUID = Depends(get_current_user_id),
    limit: int = Query(default=8, ge=1, le=50, description="Maximum number of recommended products to return"),
    db: AsyncSession = Depends(get_db),
) -> PersonalizedFeedResponse:
    """Retrieve a personalized product feed for the authenticated user."""
    return await recommendation_service.get_personalized_recommendations(
        db=db,
        user_id=user_id,
        limit=limit,
    )
