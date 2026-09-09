"""Reviews module API routes.

Provides endpoints for product reviews, helpfulness voting, and admin
moderation.  Review routes are nested under ``/products/{product_id}/reviews``
while direct review operations use ``/reviews/{review_id}``.
"""

from __future__ import annotations

import uuid
from typing import Any, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.security.dependencies import (
    RequirePermissions,
    get_current_user_id,
)
from app.modules.reviews.application.review_service import ReviewService
from app.modules.reviews.schemas.review import (
    ReviewCreate,
    ReviewListResponse,
    ReviewModerateRequest,
    ReviewResponse,
    ReviewSortOption,
    ReviewUpdate,
    ReviewVoteRequest,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger()

router = APIRouter()

_review_service = ReviewService()


# ── General review endpoints ─────────────────────────────────────────────


@router.get("", response_model=ReviewListResponse)
async def list_reviews(
    product_id: uuid.UUID = Query(..., description="Product ID to fetch reviews for"),
    sort: ReviewSortOption = Query(ReviewSortOption.NEWEST, description="Sort order"),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Results per page"),
    db: AsyncSession = Depends(get_db),
) -> ReviewListResponse:
    """List approved reviews for a product by query param."""
    return await _review_service.get_product_reviews(
        db=db,
        product_id=product_id,
        sort=sort,
        page=page,
        size=size,
    )


@router.post("", response_model=ReviewResponse, status_code=status.HTTP_201_CREATED)
async def submit_review(
    data: ReviewCreate,
    product_id: Optional[uuid.UUID] = Query(None, description="Product ID"),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> ReviewResponse:
    """Submit a review with product_id in body or query param."""
    target_product_id = data.product_id or product_id
    if not target_product_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="product_id is required either in payload or query parameter",
        )
    return await _review_service.create_review(
        db=db,
        user_id=user_id,
        product_id=target_product_id,
        data=data,
    )


# ── Product-scoped review endpoints ──────────────────────────────────────


@router.get("/products/{product_id}/reviews", response_model=ReviewListResponse)
async def get_product_reviews(
    product_id: uuid.UUID,
    sort: ReviewSortOption = Query(ReviewSortOption.NEWEST, description="Sort order"),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Results per page"),
    db: AsyncSession = Depends(get_db),
) -> ReviewListResponse:
    """List approved reviews for a product with pagination and stats."""
    return await _review_service.get_product_reviews(
        db=db,
        product_id=product_id,
        sort=sort,
        page=page,
        size=size,
    )


@router.post(
    "/products/{product_id}/reviews",
    response_model=ReviewResponse,
    status_code=201,
)
async def create_review(
    product_id: uuid.UUID,
    data: ReviewCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> ReviewResponse:
    """Submit a review for a product (one per user per product)."""
    return await _review_service.create_review(
        db=db,
        user_id=user_id,
        product_id=product_id,
        data=data,
    )


# ── Direct review endpoints ──────────────────────────────────────────────


@router.patch("/reviews/{review_id}", response_model=ReviewResponse)
async def update_review(
    review_id: uuid.UUID,
    data: ReviewUpdate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> ReviewResponse:
    """Update a review (only the author can update)."""
    return await _review_service.update_review(
        db=db,
        user_id=user_id,
        review_id=review_id,
        data=data,
    )


@router.delete("/reviews/{review_id}", status_code=204)
async def delete_review(
    review_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a review (only the author can delete)."""
    await _review_service.delete_review(
        db=db,
        user_id=user_id,
        review_id=review_id,
    )


@router.post("/reviews/{review_id}/vote")
async def vote_review(
    review_id: uuid.UUID,
    data: ReviewVoteRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Vote on whether a review is helpful.

    Voting the same way again toggles the vote off.
    """
    return await _review_service.vote_review(
        db=db,
        user_id=user_id,
        review_id=review_id,
        is_helpful=data.is_helpful,
    )


# ── Admin endpoints ──────────────────────────────────────────────────────


@router.get(
    "/admin/reviews/pending",
    response_model=ReviewListResponse,
    dependencies=[Depends(RequirePermissions("reviews:moderate"))],
)
async def list_pending_reviews(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> ReviewListResponse:
    """List all pending reviews for moderation."""
    # Reuse service with status_filter="pending" and no product filter
    from sqlalchemy import select, func
    from app.modules.reviews.domain.models import Review, ReviewStatus

    base = select(Review).where(Review.status == ReviewStatus.PENDING)
    count_q = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    stmt = base.order_by(Review.created_at.asc()).offset((page - 1) * size).limit(size)
    result = await db.execute(stmt)
    reviews = result.scalars().all()

    import math

    review_responses = [_review_service._to_response(r) for r in reviews]
    total_pages = math.ceil(total / size) if size > 0 else 0

    return ReviewListResponse(
        reviews=review_responses,
        total=total,
        page=page,
        size=size,
        total_pages=total_pages,
    )


@router.post(
    "/admin/reviews/{review_id}/moderate",
    response_model=ReviewResponse,
    dependencies=[Depends(RequirePermissions("reviews:moderate"))],
)
async def moderate_review(
    review_id: uuid.UUID,
    data: ReviewModerateRequest,
    db: AsyncSession = Depends(get_db),
) -> ReviewResponse:
    """Approve or reject a review (admin)."""
    return await _review_service.moderate_review(
        db=db,
        review_id=review_id,
        new_status=data.status,
        reason=data.reason,
    )
