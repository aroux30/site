"""Editorial calendar API: scheduled content overview (WordPress parity).

Returns a calendar view of blog posts grouped by date — published, scheduled,
and draft — so editors can plan content visually.

Usage:
    data = await EditorialCalendarService.get_month(db, year=2026, month=9)
"""

from __future__ import annotations

import calendar
from datetime import UTC, datetime, date
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import select, extract, or_

from app.modules.blog.domain.models import BlogPost, BlogPostStatus

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class EditorialCalendarService:
    """Provides a calendar view of blog content."""

    @staticmethod
    async def get_month(
        db: "AsyncSession",
        year: int,
        month: int,
    ) -> dict[str, Any]:
        """Get all posts for a given month, grouped by day."""
        first_day = date(year, month, 1)
        _, last_day_num = calendar.monthrange(year, month)
        last_day = date(year, month, last_day_num)

        # Posts published or scheduled in this month
        stmt = (
            select(BlogPost)
            .where(BlogPost.deleted_at.is_(None))
            .where(
                or_(
                    # Published in this month
                    BlogPost.published_at.between(
                        datetime(year, month, 1, tzinfo=UTC),
                        datetime(year, month, last_day_num, 23, 59, 59, tzinfo=UTC),
                    ),
                    # Scheduled for this month
                    BlogPost.scheduled_for.between(
                        datetime(year, month, 1, tzinfo=UTC),
                        datetime(year, month, last_day_num, 23, 59, 59, tzinfo=UTC),
                    ),
                    # Drafts and posts awaiting review, touched in this month.
                    # A post in review has no published_at and no scheduled_for
                    # worth showing, so without this it vanishes from the
                    # calendar for exactly the period it is being reviewed.
                    BlogPost.status.in_(
                        (BlogPostStatus.DRAFT, BlogPostStatus.PENDING_REVIEW)
                    )
                    & BlogPost.updated_at.between(
                        datetime(year, month, 1, tzinfo=UTC),
                        datetime(year, month, last_day_num, 23, 59, 59, tzinfo=UTC),
                    ),
                )
            )
            .order_by(BlogPost.published_at.asc().nullslast(), BlogPost.updated_at.asc())
        )
        posts = (await db.execute(stmt)).scalars().all()

        # Group by day
        days: dict[str, list[dict[str, Any]]] = {}
        for post in posts:
            post_date = post.published_at or post.scheduled_for or post.updated_at
            if post_date:
                day_key = post_date.strftime("%Y-%m-%d")
            else:
                day_key = "unscheduled"

            if day_key not in days:
                days[day_key] = []
            days[day_key].append({
                "id": str(post.id),
                "title": post.title,
                "slug": post.slug,
                "status": post.status.value if isinstance(post.status, BlogPostStatus) else str(post.status),
                "published_at": post.published_at.isoformat() if post.published_at else None,
                "scheduled_for": post.scheduled_for.isoformat() if post.scheduled_for else None,
            })

        return {
            "year": year,
            "month": month,
            "days": days,
            "total_posts": len(posts),
            "by_status": {
                "published": sum(1 for p in posts if p.status == BlogPostStatus.PUBLISHED),
                "draft": sum(1 for p in posts if p.status == BlogPostStatus.DRAFT),
                "scheduled": sum(1 for p in posts if p.scheduled_for),
            },
        }
