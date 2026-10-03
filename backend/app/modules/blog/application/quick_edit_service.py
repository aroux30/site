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
from sqlalchemy import delete, select

from app.modules.blog.domain.models import BlogPost, BlogPostStatus

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# Fields allowed for quick edit (no content/body changes)
QUICK_EDIT_FIELDS = {
    "title", "slug", "status", "category_id", "is_featured",
    "allow_comments", "visibility", "published_at",
    # Reassignment belongs here too: fixing a post filed under the wrong
    # author is exactly the "inline, without opening the editor" case.
    "author_id",
    # Custom fields. WordPress shows them inline in quick edit, and here they
    # were only reachable by opening the full editor — the one thing quick edit
    # exists to avoid. Applied after the column updates, because they live in a
    # different table (blog_post_meta) and are a replace, not a setattr.
    "meta",
    # Same reasoning for tags: the dialog has a tag picker, so the field has to
    # be in the allowed set or the picker silently does nothing on save.
    "tag_ids",
    # Post format, for the same reason. It is an enum column, so it needs the
    # same guarded write `status` gets: a raw setattr would put whatever the
    # client sent into the column and fail at flush, taking the whole batch
    # down with it.
    "post_format",
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
        meta_updates: dict[str, Any] | None = None
        tag_ids: list[Any] | None = None
        for key, value in updates.items():
            if key not in QUICK_EDIT_FIELDS:
                continue
            if key == "meta":
                # Handled below: it is a table replace, not a column write.
                meta_updates = value if isinstance(value, dict) else None
                continue
            if key == "tag_ids":
                # Same: the association rows are replaced, not a column.
                if isinstance(value, list):
                    tag_ids = value
                continue
            if key == "status":
                try:
                    value = BlogPostStatus(value)
                    if value == BlogPostStatus.PUBLISHED and post.published_at is None:
                        post.published_at = datetime.now(UTC)
                except ValueError:
                    continue
            if key == "post_format":
                # An unknown format is dropped rather than written: the column
                # is an enum, so a bad value would raise at flush and take the
                # rest of the save with it.
                from app.modules.blog.domain.models import PostFormat

                try:
                    value = PostFormat(value)
                except ValueError:
                    logger.warning(
                        "quick_edit_bad_post_format", value=str(value)[:32]
                    )
                    continue
            setattr(post, key, value)
            applied[key] = str(value)

        if tag_ids is not None:
            from app.core.exceptions.handlers import NotFoundError
            from app.modules.blog.domain.models import BlogPostTag, BlogTag

            parsed: list[uuid.UUID] = []
            for raw in tag_ids:
                if isinstance(raw, uuid.UUID):
                    parsed.append(raw)
                    continue
                try:
                    parsed.append(uuid.UUID(str(raw)))
                except (TypeError, ValueError):
                    # A malformed id is dropped rather than aborting the save:
                    # the dialog builds this list from ids it already holds, so
                    # a bad value means a stale client, not a wrong request.
                    logger.warning("quick_edit_bad_tag_id", value=str(raw)[:64])
            if parsed:
                found = set(
                    (await db.execute(select(BlogTag.id).where(BlogTag.id.in_(parsed))))
                    .scalars()
                    .all()
                )
                missing = [str(t) for t in parsed if t not in found]
                if missing:
                    raise NotFoundError("BlogTag", f"Tags not found: {', '.join(missing)}")
            await db.execute(delete(BlogPostTag).where(BlogPostTag.post_id == post_id))
            for tag_id in dict.fromkeys(parsed):
                db.add(BlogPostTag(post_id=post_id, tag_id=tag_id))
            await db.flush()
            applied["tag_ids"] = str(len(dict.fromkeys(parsed)))

        if meta_updates is not None:
            # A value of null deletes the key, matching the full editor: an empty
            # field in the quick-edit form means "this field is not set", not
            # "keep whatever was there".
            from sqlalchemy import delete as sa_delete, select as sa_select

            from app.modules.blog.domain.models import BlogPostMeta

            await db.execute(
                sa_delete(BlogPostMeta).where(BlogPostMeta.post_id == post_id)
            )
            for meta_key, meta_value in meta_updates.items():
                if not isinstance(meta_key, str) or not meta_key.strip():
                    continue
                db.add(
                    BlogPostMeta(
                        post_id=post_id,
                        meta_key=meta_key.strip()[:255],
                        meta_value=None if meta_value is None else str(meta_value),
                    )
                )
            await db.flush()
            applied["meta"] = str(sorted(meta_updates))

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
