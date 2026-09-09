"""Review application service.

Handles review CRUD, helpfulness voting, moderation, and statistics
aggregation.
"""

from __future__ import annotations

import math
import uuid
from typing import Any

import structlog
from sqlalchemy import and_, case, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions.handlers import ConflictError, ForbiddenError, NotFoundError
from app.modules.reviews.domain.models import Review, ReviewStatus, ReviewVote
from app.modules.reviews.schemas.review import (
    RatingDistribution,
    ReviewCreate,
    ReviewListResponse,
    ReviewResponse,
    ReviewSortOption,
    ReviewStats,
    ReviewUpdate,
    ReviewUserInfo,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger()


class ReviewService:
    """Application service for product reviews."""

    # ── Create ────────────────────────────────────────────────────────

    async def create_review(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        product_id: uuid.UUID,
        data: ReviewCreate,
    ) -> ReviewResponse:
        """Create a new review for a product.

        Each user may only submit one review per product.
        """
        # Check for existing review
        existing = await db.execute(
            select(Review).where(
                and_(
                    Review.product_id == product_id,
                    Review.user_id == user_id,
                )
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise ConflictError("You have already reviewed this product")

        review = Review(
            product_id=product_id,
            user_id=user_id,
            rating=data.rating,
            title=data.title,
            body=data.body,
            pros=data.pros,
            cons=data.cons,
            status=ReviewStatus.PENDING,
            is_verified_purchase=False,  # Could be enriched by order service
        )
        db.add(review)
        await db.flush()
        await db.refresh(review)

        await logger.ainfo(
            "review_created",
            review_id=str(review.id),
            product_id=str(product_id),
            user_id=str(user_id),
        )

        return self._to_response(review)

    # ── Update ────────────────────────────────────────────────────────

    async def update_review(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        review_id: uuid.UUID,
        data: ReviewUpdate,
    ) -> ReviewResponse:
        """Update an existing review owned by the user."""
        review = await self._get_review_or_404(db, review_id)

        if review.user_id != user_id:
            raise ForbiddenError("You can only edit your own reviews")

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(review, field, value)

        # Reset to pending on edit so moderators can re-review
        review.status = ReviewStatus.PENDING

        await db.flush()
        await db.refresh(review)

        await logger.ainfo(
            "review_updated",
            review_id=str(review_id),
            user_id=str(user_id),
        )

        return self._to_response(review)

    # ── Delete ────────────────────────────────────────────────────────

    async def delete_review(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        review_id: uuid.UUID,
    ) -> None:
        """Delete a review owned by the user."""
        review = await self._get_review_or_404(db, review_id)

        if review.user_id != user_id:
            raise ForbiddenError("You can only delete your own reviews")

        await db.delete(review)
        await db.flush()

        await logger.ainfo(
            "review_deleted",
            review_id=str(review_id),
            user_id=str(user_id),
        )

    # ── Read / list ───────────────────────────────────────────────────

    async def get_product_reviews(
        self,
        db: AsyncSession,
        product_id: uuid.UUID,
        sort: ReviewSortOption = ReviewSortOption.NEWEST,
        page: int = 1,
        size: int = 20,
        status_filter: str = "approved",
    ) -> ReviewListResponse:
        """Return paginated reviews for a product with aggregate stats."""
        # Base query
        base = select(Review).where(Review.product_id == product_id)

        if status_filter != "all":
            base = base.where(Review.status == ReviewStatus(status_filter))

        # Count
        count_q = select(func.count()).select_from(base.subquery())
        total = (await db.execute(count_q)).scalar() or 0

        # Sort
        order = self._sort_clause(sort)
        stmt = base.order_by(order).offset((page - 1) * size).limit(size)

        result = await db.execute(stmt)
        reviews = result.scalars().all()

        # Stats (always over approved reviews for consistency)
        stats = await self.get_review_stats(db, product_id)

        total_pages = math.ceil(total / size) if size > 0 else 0

        # Build response with vote counts
        review_responses: list[ReviewResponse] = []
        for review in reviews:
            resp = self._to_response(review)
            # Fetch vote counts
            counts = await self._get_vote_counts(db, review.id)
            resp.helpful_count = counts["helpful"]
            resp.unhelpful_count = counts["unhelpful"]
            review_responses.append(resp)

        return ReviewListResponse(
            reviews=review_responses,
            total=total,
            page=page,
            size=size,
            total_pages=total_pages,
            stats=stats,
        )

    # ── Voting ────────────────────────────────────────────────────────

    async def vote_review(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        review_id: uuid.UUID,
        is_helpful: bool,
    ) -> dict[str, Any]:
        """Cast or update a helpfulness vote on a review."""
        # Ensure review exists
        await self._get_review_or_404(db, review_id)

        # Check existing vote
        existing = await db.execute(
            select(ReviewVote).where(
                and_(
                    ReviewVote.review_id == review_id,
                    ReviewVote.user_id == user_id,
                )
            )
        )
        vote = existing.scalar_one_or_none()

        if vote is not None:
            if vote.is_helpful == is_helpful:
                # Same vote – remove it (toggle off)
                await db.delete(vote)
                await db.flush()
                action = "removed"
            else:
                # Different vote – update
                vote.is_helpful = is_helpful
                await db.flush()
                action = "updated"
        else:
            vote = ReviewVote(
                review_id=review_id,
                user_id=user_id,
                is_helpful=is_helpful,
            )
            db.add(vote)
            await db.flush()
            action = "created"

        counts = await self._get_vote_counts(db, review_id)

        await logger.ainfo(
            "review_vote",
            review_id=str(review_id),
            user_id=str(user_id),
            is_helpful=is_helpful,
            action=action,
        )

        return {
            "action": action,
            "helpful_count": counts["helpful"],
            "unhelpful_count": counts["unhelpful"],
        }

    # ── Stats ─────────────────────────────────────────────────────────

    async def get_review_stats(
        self, db: AsyncSession, product_id: uuid.UUID
    ) -> ReviewStats:
        """Compute aggregate review statistics for a product."""
        base = select(Review).where(
            and_(
                Review.product_id == product_id,
                Review.status == ReviewStatus.APPROVED,
            )
        )

        # Average and count
        agg_q = select(
            func.coalesce(func.avg(Review.rating), 0).label("avg"),
            func.count(Review.id).label("total"),
            func.count(
                case((Review.is_verified_purchase.is_(True), 1))
            ).label("verified"),
        ).where(
            and_(
                Review.product_id == product_id,
                Review.status == ReviewStatus.APPROVED,
            )
        )
        agg_result = (await db.execute(agg_q)).one()

        avg_rating = round(float(agg_result.avg), 2)
        total_reviews = int(agg_result.total)
        verified_count = int(agg_result.verified)

        # Distribution
        dist_q = select(
            Review.rating,
            func.count(Review.id).label("cnt"),
        ).where(
            and_(
                Review.product_id == product_id,
                Review.status == ReviewStatus.APPROVED,
            )
        ).group_by(Review.rating)

        dist_result = await db.execute(dist_q)
        dist_map = {row.rating: row.cnt for row in dist_result}

        distribution = RatingDistribution(
            star_1=dist_map.get(1, 0),
            star_2=dist_map.get(2, 0),
            star_3=dist_map.get(3, 0),
            star_4=dist_map.get(4, 0),
            star_5=dist_map.get(5, 0),
        )

        return ReviewStats(
            average_rating=avg_rating,
            total_reviews=total_reviews,
            distribution=distribution,
            verified_count=verified_count,
        )

    # ── Admin: moderation ─────────────────────────────────────────────

    async def moderate_review(
        self,
        db: AsyncSession,
        review_id: uuid.UUID,
        new_status: str,
        reason: str | None = None,
    ) -> ReviewResponse:
        """Approve or reject a pending review (admin operation)."""
        review = await self._get_review_or_404(db, review_id)

        try:
            status_enum = ReviewStatus(new_status)
        except ValueError:
            raise ValueError(f"Invalid review status: {new_status}")  # noqa: B904

        review.status = status_enum
        await db.flush()
        await db.refresh(review)

        await logger.ainfo(
            "review_moderated",
            review_id=str(review_id),
            new_status=new_status,
            reason=reason,
        )

        return self._to_response(review)

    # ── Private helpers ───────────────────────────────────────────────

    async def _get_review_or_404(
        self, db: AsyncSession, review_id: uuid.UUID
    ) -> Review:
        """Load a review by ID or raise NotFoundError."""
        result = await db.execute(
            select(Review).where(Review.id == review_id)
        )
        review = result.scalar_one_or_none()
        if review is None:
            raise NotFoundError("Review")
        return review

    async def _get_vote_counts(
        self, db: AsyncSession, review_id: uuid.UUID
    ) -> dict[str, int]:
        """Return helpful/unhelpful vote counts for a review."""
        q = select(
            func.count(case((ReviewVote.is_helpful.is_(True), 1))).label("helpful"),
            func.count(case((ReviewVote.is_helpful.is_(False), 1))).label("unhelpful"),
        ).where(ReviewVote.review_id == review_id)
        row = (await db.execute(q)).one()
        return {"helpful": int(row.helpful), "unhelpful": int(row.unhelpful)}

    @staticmethod
    def _sort_clause(sort: ReviewSortOption) -> Any:
        """Return an SQLAlchemy order_by clause."""
        if sort == ReviewSortOption.OLDEST:
            return Review.created_at.asc()
        if sort == ReviewSortOption.HIGHEST_RATING:
            return Review.rating.desc()
        if sort == ReviewSortOption.LOWEST_RATING:
            return Review.rating.asc()
        if sort == ReviewSortOption.MOST_HELPFUL:
            # Fall back to newest; real helpful sort would need a subquery
            return Review.created_at.desc()
        # NEWEST (default)
        return Review.created_at.desc()

    @staticmethod
    def _to_response(review: Review) -> ReviewResponse:
        """Map a Review ORM instance to a ReviewResponse schema."""
        return ReviewResponse(
            id=str(review.id),
            user=ReviewUserInfo(id=str(review.user_id)),
            product_id=str(review.product_id),
            rating=review.rating,
            title=review.title,
            body=review.body,
            pros=review.pros,
            cons=review.cons,
            is_verified_purchase=review.is_verified_purchase,
            status=review.status.value,
            helpful_count=0,
            unhelpful_count=0,
            created_at=review.created_at,
            updated_at=review.updated_at,
        )
