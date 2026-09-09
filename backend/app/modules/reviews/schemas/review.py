"""Pydantic schemas for the reviews module."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ── Enums ─────────────────────────────────────────────────────────────────


class ReviewSortOption(str, enum.Enum):
    NEWEST = "newest"
    OLDEST = "oldest"
    HIGHEST_RATING = "highest_rating"
    LOWEST_RATING = "lowest_rating"
    MOST_HELPFUL = "most_helpful"


class ReviewStatusFilter(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    ALL = "all"


# ── Request schemas ───────────────────────────────────────────────────────


class ReviewCreate(BaseModel):
    """Payload for creating a new review."""

    rating: int = Field(..., ge=1, le=5, description="Rating from 1 to 5")
    title: Optional[str] = Field(None, max_length=300, description="Review title")
    body: Optional[str] = Field(None, max_length=5000, description="Review body text")
    pros: Optional[list[str]] = Field(None, max_length=10, description="List of positive points")
    cons: Optional[list[str]] = Field(None, max_length=10, description="List of negative points")


class ReviewUpdate(BaseModel):
    """Payload for updating an existing review."""

    rating: Optional[int] = Field(None, ge=1, le=5, description="Updated rating")
    title: Optional[str] = Field(None, max_length=300, description="Updated title")
    body: Optional[str] = Field(None, max_length=5000, description="Updated body")
    pros: Optional[list[str]] = Field(None, max_length=10, description="Updated pros")
    cons: Optional[list[str]] = Field(None, max_length=10, description="Updated cons")


class ReviewVoteRequest(BaseModel):
    """Payload for voting on a review's helpfulness."""

    is_helpful: bool = Field(..., description="Whether the user found the review helpful")


class ReviewModerateRequest(BaseModel):
    """Admin request to approve or reject a review."""

    status: str = Field(..., pattern="^(approved|rejected)$", description="New status")
    reason: Optional[str] = Field(None, max_length=500, description="Moderation reason")


# ── Response schemas ──────────────────────────────────────────────────────


class ReviewUserInfo(BaseModel):
    """Minimal user info attached to a review response."""

    id: str
    display_name: Optional[str] = None


class ReviewResponse(BaseModel):
    """Single review in API responses."""

    id: str
    user: ReviewUserInfo
    product_id: str
    rating: int
    title: Optional[str] = None
    body: Optional[str] = None
    pros: Optional[list[str]] = None
    cons: Optional[list[str]] = None
    is_verified_purchase: bool = False
    status: str = "pending"
    helpful_count: int = 0
    unhelpful_count: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RatingDistribution(BaseModel):
    """Star-rating distribution for a product."""

    star_1: int = 0
    star_2: int = 0
    star_3: int = 0
    star_4: int = 0
    star_5: int = 0


class ReviewStats(BaseModel):
    """Aggregated review statistics for a product."""

    average_rating: float = 0.0
    total_reviews: int = 0
    distribution: RatingDistribution = Field(default_factory=RatingDistribution)
    verified_count: int = 0


class ReviewListResponse(BaseModel):
    """Paginated list of reviews with aggregate stats."""

    reviews: list[ReviewResponse] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    size: int = 20
    total_pages: int = 0
    stats: ReviewStats = Field(default_factory=ReviewStats)
