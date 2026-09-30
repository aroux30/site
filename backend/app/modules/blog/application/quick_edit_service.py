"""Quick edit service: inline field updates without full page load (WordPress parity).

Allows patching a subset of post/page fields (title, slug, status, category,
date, author) in a single lightweight API call, matching the WordPress
quick-edit table row behavior.

Usage:
    result = await QuickEditService.quick_edit_post(db, post_id, {"title": "New", "status": "published"})
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import select

from app.modules.blog.domain.models import BlogPost, BlogPostStatus

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# Fields allowed for quick edit (no content/body changes)
QUICK_EDIT_FIELDS = {
    "title", "slug", "status", "category_id", "is_featured",
    "allow_comments", "visibility", "published_at",
}


class QuickEditService:
    """Lightweight inline field updates."""

    @staticmethod
    async def quick_edit_post(
        db: "AsyncSession",
        post_id: uuid.UUID,
        updates: dict[str, Any],
    ) -> dict[str, Any]:
        """Apply quick-edit field updates to a post."""
        post = await db.get(BlogPost, post_id)
        if not post:
            return {"error": "Post not found"}

        applied: dict[str, Any] = {}
        for key, value in updates.items():
            if key not in QUICK_EDIT_FIELDS:
                continue
            if key == "status":
                try:
                    value = BlogPostStatus(value)
                    if value == BlogPostStatus.PUBLISHED and post.published_at is None:
                        post.published_at = datetime.now(UTC)
                except ValueError:
                    continue
            setattr(post, key, value)
            applied[key] = str(value)

        if applied:
            await db.commit()
            await db.refresh(post)
            logger.info("quick_edit_applied", post_id=str(post_id), fields=list(applied.keys()))

        return {
            "post_id": str(post_id),
            "updated_fields": applied,
            "title": post.title,
            "slug": post.slug,
            "status": post.status.value,
        }
