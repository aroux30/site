"""Blog service handling business logic for blog posts and categories."""

from __future__ import annotations

import hmac
import math
import re
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, ClassVar

import structlog
from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import selectinload

from app.core.cache.redis import get_redis
from app.core.exceptions.handlers import ConflictError, NotFoundError, ValidationError
from app.modules.blog.domain.models import (
    BlogCategory,
    BlogComment,
    BlogPost,
    BlogPostRevision,
    BlogPostStatus,
    BlogPostTag,
    BlogTag,
    CommentStatus,
    PostFormat,
    PostVisibility,
)
from app.modules.blog.application.slug_history_service import (
    SLUG_RESOURCE_BLOG_POST,
    record_slug_change,
)
from app.modules.blog.schemas.blog import (
    BlogCategoryCreate,
    BlogCategoryDeleteResult,
    BlogCategoryResponse,
    BlogCategoryUpdate,
    BlogListResponse,
    BlogPostCreate,
    BlogPostDetailResponse,
    BlogPostResponse,
    BlogPostRevisionDetailResponse,
    BlogPostRevisionResponse,
    BlogPostUpdate,
    BlogTagCreate,
    BlogTagResponse,
    BlogTagUpdate,
)
from app.modules.seo.domain.models import SEOMetadata
from app.modules.users.domain.models import User, UserProfile
from app.shared.content.html_sanitizer import sanitize_html
from app.shared.domain.slug import generate_slug as _generate_slug

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
logger: structlog.stdlib.BoundLogger = structlog.get_logger()


def generate_slug(text: str) -> str:
    """Backward-compatible wrapper around the shared Persian slug helper."""
    return _generate_slug(text, fallback="post")


def calculate_reading_time(content: str) -> int:
    """Calculate approximate reading time in minutes (assuming 200 wpm)."""
    words = len(re.findall(r"\w+", content))
    return max(1, math.ceil(words / 200))


def _hash_post_password(plain: str) -> str:
    """Hash a post-access password for storage (Argon2id).

    Stored hashed for the same reason user passwords are: a database leak
    must not hand out the plaintext that unlocks protected articles. The
    hash is never serialized into any API response.
    """
    from app.core.security.password import hash_password

    return hash_password(plain)


#: Statuses only a publisher may set. Everything else is editorial work a
#: contributor can do. WordPress splits these the same way: ``edit_posts`` is
#: what a contributor holds, ``publish_posts`` is what an author holds and they
#: are different capabilities.
_PUBLISH_ONLY_STATUSES: frozenset[BlogPostStatus] = frozenset(
    {BlogPostStatus.PUBLISHED, BlogPostStatus.PENDING_REVIEW}
)


def assert_may_publish(
    status: BlogPostStatus | None, *, permissions: set[str] | None
) -> None:
    """Refuse a publish-level status from a caller without ``blog:publish``.

    ``BlogPostCreate.status`` and ``BlogPostUpdate.status`` are both
    client-supplied, and ``publish_posts`` used to map onto the same
    ``blog:write`` codename as ``edit_posts`` with no enforcement site — so a
    contributor, whose seeded description says "writes drafts an editor
    reviews", could publish by posting ``{"status": "published"}``.

    ``permissions=None`` means the caller could not be resolved (an internal
    job, a test, a path that never fetched the actor). Those keep working: an
    unknown actor is not evidence of an unprivileged one, and failing closed
    here would break the beat task that promotes scheduled posts.
    """
    if status is None or status not in _PUBLISH_ONLY_STATUSES:
        return
    if permissions is None:
        return
    if "blog:publish" in permissions or "settings:write" in permissions:
        return
    if "super_admin" in permissions or "*" in permissions:
        return
    raise ValidationError(
        f"انتشار نوشته (وضعیت «{status.value}») نیازمند دسترسی blog:publish است"
    )


class BlogService:
    """Service encapsulating CRUD and business logic for blog posts and categories."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Slug Uniqueness Helpers ───────────────────────────────────────────

    async def _post_slug_exists(self, slug: str, exclude_id: uuid.UUID | None = None) -> bool:
        stmt = select(func.count(BlogPost.id)).where(BlogPost.slug == slug)
        if exclude_id is not None:
            stmt = stmt.where(BlogPost.id != exclude_id)
        count = (await self.db.execute(stmt)).scalar_one()
        return count > 0

    async def _category_slug_exists(self, slug: str, exclude_id: uuid.UUID | None = None) -> bool:
        stmt = select(func.count(BlogCategory.id)).where(BlogCategory.slug == slug)
        if exclude_id is not None:
            stmt = stmt.where(BlogCategory.id != exclude_id)
        count = (await self.db.execute(stmt)).scalar_one()
        return count > 0

    async def _ensure_unique_post_slug(
        self, slug: str, exclude_id: uuid.UUID | None = None
    ) -> str:
        candidate = slug
        counter = 1
        while await self._post_slug_exists(candidate, exclude_id=exclude_id):
            candidate = f"{slug}-{counter}"
            counter += 1
        return candidate

    async def _ensure_unique_category_slug(
        self, slug: str, exclude_id: uuid.UUID | None = None
    ) -> str:
        candidate = slug
        counter = 1
        while await self._category_slug_exists(candidate, exclude_id=exclude_id):
            candidate = f"{slug}-{counter}"
            counter += 1
        return candidate

    # ── View Count Tracking ───────────────────────────────────────────────

    async def increment_view_count(self, post_id: uuid.UUID) -> int:
        """Increment Redis view count for the post and return current value."""
        try:
            client = await get_redis()
            return await client.incr(f"blog:post:views:{post_id}")
        except Exception as exc:
            logger.debug("redis_view_increment_failed", post_id=str(post_id), error=str(exc))
            return 0

    async def get_view_count(self, post_id: uuid.UUID) -> int:
        """Fetch current view count from Redis."""
        try:
            client = await get_redis()
            val = await client.get(f"blog:post:views:{post_id}")
            return int(val) if val else 0
        except Exception:
            return 0

    async def get_author_slug(self, author_id: uuid.UUID) -> str | None:
        """The author's public slug, or None when they have none.

        Read from the users row rather than derived from the display name: a
        name edit must not move an already-published /author/ URL.
        """
        try:
            stmt = select(User.author_slug).where(User.id == author_id)
            return (await self.db.execute(stmt)).scalar_one_or_none()
        except Exception:  # noqa: BLE001
            return None

    async def get_author_name(self, author_id: uuid.UUID) -> str:
        """Retrieve author name or fallback to default."""
        try:
            stmt = (
                select(UserProfile.first_name, UserProfile.last_name, User.phone)
                .outerjoin(UserProfile, UserProfile.user_id == User.id)
                .where(User.id == author_id)
            )
            result = (await self.db.execute(stmt)).first()
            if result:
                first, last, phone = result
                if first or last:
                    return f"{first or ''} {last or ''}".strip()
                if phone:
                    return f"کاربر {phone[-4:]}"
            return "تحریریه فروشگاه"
        except Exception:
            return "تحریریه فروشگاه"

    # ── Response Mapper ───────────────────────────────────────────────────

    def _post_to_response(
        self,
        post: BlogPost,
        views: int,
        author_name: str,
        *,
        author_slug: str | None = None,
        excerpt_word_limit: int | None = None,
        excerpt_more: str | None = None,
    ) -> BlogPostResponse:
        """Map a post model (with post_tags eager-loaded) to a list/summary response.

        ``excerpt_word_limit`` only applies when the post has no authored
        excerpt: the storefront renders ``excerpt`` unconditionally, so a post
        without one used to render an empty paragraph. Passing None keeps the
        previous behaviour for callers that do not want a derived summary.

        ``excerpt_more`` is the separator appended to a truncated derived
        excerpt (the ``excerpt_more`` site option). None keeps auto_excerpt's
        own default, so an unset option behaves exactly as before.
        """
        tags = [
            BlogTagResponse.model_validate(pt.tag)
            for pt in post.post_tags
            if pt.tag is not None
        ]
        excerpt = post.excerpt
        if not excerpt and excerpt_word_limit:
            from app.shared.content.excerpt import auto_excerpt

            kwargs = {"max_words": excerpt_word_limit}
            if excerpt_more is not None:
                kwargs["suffix"] = excerpt_more
            excerpt = auto_excerpt(post.content, **kwargs) or None
        return BlogPostResponse(
            id=post.id,
            author_id=post.author_id,
            author_slug=author_slug,
            title=post.title,
            slug=post.slug,
            excerpt=excerpt,
            cover_image_url=post.cover_image_url,
            status=post.status,
            published_at=post.published_at,
            scheduled_for=post.scheduled_for,
            category_id=post.category_id,
            category=(
                BlogCategoryResponse.model_validate(post.category) if post.category else None
            ),
            tags=tags,
            reading_time=calculate_reading_time(post.content),
            view_count=views,
            author_name=author_name,
            is_featured=post.is_featured,
            visibility=post.visibility,
            allow_comments=post.allow_comments,
            post_format=post.post_format,
            gallery_image_ids=post.gallery_image_ids,
            comment_count=0,  # filled by caller if needed
            created_at=post.created_at,
            updated_at=post.updated_at,
            deleted_at=post.deleted_at,
            locale=post.locale,
            translation_group=post.translation_group,
        )

    async def _get_seo_dict(self, post_id: uuid.UUID) -> dict[str, Any] | None:
        """Fetch SEO metadata for a post as a plain dict, or None."""
        seo_stmt = select(SEOMetadata).where(
            SEOMetadata.resource_type == "blog_post",
            SEOMetadata.resource_id == post_id,
        )
        seo = (await self.db.execute(seo_stmt)).scalar_one_or_none()
        if not seo:
            return None
        return {
            "title": seo.title,
            "description": seo.description,
            "canonical_url": seo.canonical_url,
            "og_title": seo.og_title,
            "og_description": seo.og_description,
            "og_image": seo.og_image,
            "schema_markup": seo.schema_markup,
        }

    # ── Tag Operations ────────────────────────────────────────────────────

    async def create_tag(self, data: BlogTagCreate) -> BlogTagResponse:
        """Create a new blog tag."""
        base_slug = data.slug.strip() if data.slug else generate_slug(data.name)
        slug = await self._ensure_unique_tag_slug(base_slug)

        tag = BlogTag(name=data.name.strip(), slug=slug)
        self.db.add(tag)
        await self.db.commit()
        await self.db.refresh(tag)

        return BlogTagResponse(
            id=tag.id,
            name=tag.name,
            slug=tag.slug,
            created_at=tag.created_at,
            updated_at=tag.updated_at,
            post_count=0,
        )

    async def list_tags(self) -> list[BlogTagResponse]:
        """List all blog tags with their published post counts."""
        count_subq = (
            select(
                BlogPostTag.tag_id,
                func.count(BlogPostTag.post_id).label("post_count"),
            )
            .join(BlogPost, BlogPost.id == BlogPostTag.post_id)
            .where(BlogPost.status == BlogPostStatus.PUBLISHED)
            .group_by(BlogPostTag.tag_id)
            .subquery()
        )
        stmt = (
            select(BlogTag, func.coalesce(count_subq.c.post_count, 0).label("post_count"))
            .outerjoin(count_subq, count_subq.c.tag_id == BlogTag.id)
            .order_by(BlogTag.name.asc())
        )
        rows = (await self.db.execute(stmt)).all()
        return [
            BlogTagResponse(
                id=tag.id,
                name=tag.name,
                slug=tag.slug,
                created_at=tag.created_at,
                updated_at=tag.updated_at,
                post_count=count,
            )
            for tag, count in rows
        ]

    async def _ensure_unique_tag_slug(
        self, slug: str, exclude_id: uuid.UUID | None = None
    ) -> str:
        candidate = slug
        counter = 1
        while await self._tag_slug_exists(candidate, exclude_id=exclude_id):
            candidate = f"{slug}-{counter}"
            counter += 1
        return candidate

    async def _tag_slug_exists(self, slug: str, exclude_id: uuid.UUID | None = None) -> bool:
        stmt = select(func.count(BlogTag.id)).where(BlogTag.slug == slug)
        if exclude_id is not None:
            stmt = stmt.where(BlogTag.id != exclude_id)
        count = (await self.db.execute(stmt)).scalar_one()
        return count > 0

    async def _resolve_allow_comments(self, requested: bool | None) -> bool:
        """Decide whether a new post accepts comments.

        An explicit true/false from the caller always wins. When the caller is
        silent, the site's ``default_comment_status`` decides — "open" means
        new posts accept comments, which is what the setting means in
        WordPress. It is *not* an auto-approval flag: moderation still applies
        to whatever arrives.
        """
        if requested is not None:
            return requested

        from app.modules.settings.application.site_options_service import (
            SiteOptionsService,
        )

        status = await SiteOptionsService.get(self.db, "default_comment_status", "open")
        return str(status or "open").strip().lower() != "closed"

    async def _replace_post_tags(
        self, post: BlogPost, tag_ids: list[uuid.UUID] | None
    ) -> None:
        """Replace a post's tag set with the given tag IDs (no-op when None)."""
        if tag_ids is None:
            return
        if tag_ids:
            stmt = select(BlogTag.id).where(BlogTag.id.in_(tag_ids))
            found = set((await self.db.execute(stmt)).scalars().all())
            missing = [str(t) for t in tag_ids if t not in found]
            if missing:
                raise NotFoundError("BlogTag", f"Tags not found: {', '.join(missing)}")
        await self.db.execute(delete(BlogPostTag).where(BlogPostTag.post_id == post.id))
        for tag_id in dict.fromkeys(tag_ids):  # dedupe preserving order
            self.db.add(BlogPostTag(post_id=post.id, tag_id=tag_id))
        await self.db.flush()

    # ── Revision Operations ───────────────────────────────────────────────

    async def _snapshot_revision(
        self, post: BlogPost, created_by: uuid.UUID | None = None
    ) -> None:
        """Append an immutable snapshot of the post's current content state."""
        stmt = select(func.max(BlogPostRevision.revision_number)).where(
            BlogPostRevision.post_id == post.id
        )
        last = (await self.db.execute(stmt)).scalar()
        revision_number = (last or 0) + 1
        seo_title, seo_description = await self._current_post_seo(post.id)
        self.db.add(
            BlogPostRevision(
                post_id=post.id,
                revision_number=revision_number,
                title=post.title,
                slug=post.slug,
                content=post.content,
                excerpt=post.excerpt,
                cover_image_url=post.cover_image_url,
                status=post.status.value,
                seo_title=seo_title,
                seo_description=seo_description,
                created_by=created_by,
            )
        )
        await self.db.flush()

    async def _current_post_seo(
        self, post_id: uuid.UUID
    ) -> tuple[str | None, str | None]:
        """Snapshot the post's current SEO title/description into revisions.

        Revisions are immutable, so the SEO row (lives in the seo module's
        seo_metadata table, keyed resource_type/resource_id) is copied at
        snapshot time; revisions created before these columns existed stay
        NULL and the diff treats NULL vs NULL as unchanged.
        """
        row = (
            await self.db.execute(
                select(SEOMetadata.title, SEOMetadata.description).where(
                    SEOMetadata.resource_type == "blog_post",
                    SEOMetadata.resource_id == post_id,
                )
            )
        ).first()
        if row is None:
            return None, None
        return row.title, row.description

    async def list_revisions(self, post_id: uuid.UUID) -> list[BlogPostRevisionResponse]:
        """List revision snapshots for a post, newest first."""
        await self._get_post_or_404(post_id)
        stmt = (
            select(BlogPostRevision)
            .where(BlogPostRevision.post_id == post_id)
            .order_by(BlogPostRevision.revision_number.desc())
        )
        revisions = (await self.db.execute(stmt)).scalars().all()
        return [BlogPostRevisionResponse.model_validate(r) for r in revisions]

    async def get_revision(
        self, post_id: uuid.UUID, revision_number: int
    ) -> BlogPostRevisionDetailResponse:
        """Fetch the full content snapshot of one revision."""
        stmt = select(BlogPostRevision).where(
            BlogPostRevision.post_id == post_id,
            BlogPostRevision.revision_number == revision_number,
        )
        revision = (await self.db.execute(stmt)).scalar_one_or_none()
        if not revision:
            raise NotFoundError(
                "BlogPostRevision",
                f"Revision {revision_number} for post {post_id} not found",
            )
        return BlogPostRevisionDetailResponse.model_validate(revision)

    async def restore_revision(
        self,
        post_id: uuid.UUID,
        revision_number: int,
        actor_id: uuid.UUID | None = None,
    ) -> BlogPostDetailResponse:
        """Restore a post's content fields from a stored revision snapshot."""
        revision = await self.get_revision(post_id, revision_number)
        post = await self._get_post_or_404(post_id)
        post.title = revision.title
        post.content = revision.content
        post.excerpt = revision.excerpt
        post.cover_image_url = revision.cover_image_url
        await self._snapshot_revision(post, created_by=actor_id)
        await self.db.commit()
        await self.db.refresh(post)
        return await self.get_post_by_id(post.id)

    async def _get_post_or_404(self, post_id: uuid.UUID) -> BlogPost:
        post = await self.db.get(BlogPost, post_id)
        if not post:
            raise NotFoundError("BlogPost", f"Blog post {post_id} not found")
        return post

    # ── Scheduled Publishing ──────────────────────────────────────────────

    async def publish_due_scheduled(self) -> int:
        """Publish posts whose scheduled_for time has passed; return count published."""
        now = datetime.now(UTC)
        stmt = select(BlogPost).where(
            BlogPost.status == BlogPostStatus.DRAFT,
            BlogPost.scheduled_for.is_not(None),
            BlogPost.scheduled_for <= now,
        )
        due = (await self.db.execute(stmt)).scalars().all()
        for post in due:
            post.status = BlogPostStatus.PUBLISHED
            post.published_at = post.scheduled_for
            post.scheduled_for = None
            await self._snapshot_revision(post)
        if due:
            await self.db.commit()
            await self._notify_published(due)
            await logger.ainfo("scheduled_posts_published", count=len(due))
        return len(due)

    async def _notify_published(self, posts: list[BlogPost]) -> None:
        """Announce freshly published posts. Never fails the publish itself."""
        from app.modules.blog.application.notification_service import (
            BlogNotificationService,
        )

        notifier = BlogNotificationService(self.db)
        for post in posts:
            try:
                await notifier.notify_new_post(
                    post_id=post.id,
                    title=post.title,
                    slug=post.slug,
                    author_name="",
                    author_id=post.author_id,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("post_publish_notify_failed", post_id=str(post.id), error=str(exc))

    # ── Category Operations ───────────────────────────────────────────────

    async def create_category(self, data: BlogCategoryCreate) -> BlogCategoryResponse:
        """Create a new blog category."""
        base_slug = data.slug.strip() if data.slug else generate_slug(data.name)
        slug = await self._ensure_unique_category_slug(base_slug)

        parent_id = data.parent_id
        if parent_id is not None:
            parent = await self.db.get(BlogCategory, parent_id)
            if parent is None:
                raise ValidationError(
                    detail="دسته‌بندی والد یافت نشد"
                )

        category = BlogCategory(
            name=data.name.strip(),
            slug=slug,
            description=data.description,
            parent_id=parent_id,
            position=data.position,
        )
        self.db.add(category)
        await self.db.commit()
        await self.db.refresh(category)

        return await self._category_response(category)

    async def update_category(
        self, category_id: uuid.UUID, data: "BlogCategoryUpdate"
    ) -> BlogCategoryResponse:
        """Rename a category or move it to a new slug.

        A slug change is a public URL change. The unique check is done before
        the write so a collision raises rather than surfacing later as an
        IntegrityError from the driver.
        """
        category = await self.db.get(BlogCategory, category_id)
        if category is None:
            raise NotFoundError("BlogCategory", f"Category '{category_id}' not found")

        if data.name is not None:
            category.name = data.name.strip()
        if data.description is not None:
            category.description = data.description
        if data.position is not None:
            category.position = data.position
        if "parent_id" in data.model_fields_set and data.parent_id != category.parent_id:
            if await self._would_create_cycle(category_id, data.parent_id):
                raise ValidationError(
                    detail="یک دسته‌بندی نمی‌تواند والدِ خودش یا والدِ یکی از فرزندانش باشد"
                )
            if data.parent_id is not None:
                parent = await self.db.get(BlogCategory, data.parent_id)
                if parent is None:
                    raise ValidationError(detail="دسته‌بندی والد یافت نشد")
            category.parent_id = data.parent_id
        if data.slug is not None:
            wanted = data.slug.strip()
            if wanted and wanted != category.slug:
                clash = (
                    await self.db.execute(
                        select(BlogCategory).where(
                            BlogCategory.slug == wanted, BlogCategory.id != category_id
                        )
                    )
                ).scalar_one_or_none()
                if clash is not None:
                    raise ConflictError(
                        detail=f"دسته‌بندی دیگری با اسلاگ '{wanted}' وجود دارد"
                    )
                category.slug = wanted

        await self.db.commit()
        await self.db.refresh(category)
        await logger.ainfo("category_updated", category_id=str(category_id))
        return await self._category_response(category)

    async def delete_category(self, category_id: uuid.UUID) -> "BlogCategoryDeleteResult":
        """Delete a category, leaving its posts in place.

        The posts are orphaned rather than deleted: removing a category is how
        an operator retires a taxonomy they no longer use, and silently
        destroying published articles with it would be the worst possible
        reading of "delete this category".
        """
        category = await self.db.get(BlogCategory, category_id)
        if category is None:
            raise NotFoundError("BlogCategory", f"Category '{category_id}' not found")

        stmt = select(BlogPost).where(BlogPost.category_id == category_id)
        orphans = list((await self.db.execute(stmt)).scalars().all())
        for post in orphans:
            post.category_id = None

        await self.db.delete(category)
        await self.db.commit()
        await logger.ainfo(
            "category_deleted", category_id=str(category_id), orphaned=len(orphans)
        )
        return BlogCategoryDeleteResult(deleted=True, orphaned_posts=len(orphans))

    async def update_tag(
        self, tag_id: uuid.UUID, data: "BlogTagUpdate"
    ) -> BlogTagResponse:
        """Rename a tag or move it to a new slug."""
        tag = await self.db.get(BlogTag, tag_id)
        if tag is None:
            raise NotFoundError("BlogTag", f"Tag '{tag_id}' not found")

        if data.name is not None:
            tag.name = data.name.strip()
        if data.slug is not None:
            wanted = data.slug.strip()
            if wanted and wanted != tag.slug:
                clash = (
                    await self.db.execute(
                        select(BlogTag).where(
                            BlogTag.slug == wanted, BlogTag.id != tag_id
                        )
                    )
                ).scalar_one_or_none()
                if clash is not None:
                    raise ConflictError(detail=f"برچسب دیگری با اسلاگ '{wanted}' وجود دارد")
                tag.slug = wanted

        await self.db.commit()
        await self.db.refresh(tag)
        await logger.ainfo("tag_updated", tag_id=str(tag_id))
        return await self._tag_response(tag)

    async def delete_tag(self, tag_id: uuid.UUID) -> "BlogCategoryDeleteResult":
        """Delete a tag and unlink it from its posts.

        Tags are a many-to-many relation, so the join rows are removed and the
        posts themselves are untouched — a post with no tags is still a post.
        """
        tag = await self.db.get(BlogTag, tag_id)
        if tag is None:
            raise NotFoundError("BlogTag", f"Tag '{tag_id}' not found")

        stmt = select(BlogPostTag).where(BlogPostTag.tag_id == tag_id)
        links = list((await self.db.execute(stmt)).scalars().all())
        for link in links:
            await self.db.delete(link)

        await self.db.delete(tag)
        await self.db.commit()
        await logger.ainfo("tag_deleted", tag_id=str(tag_id), unlinked=len(links))
        return BlogCategoryDeleteResult(deleted=True, orphaned_posts=len(links))

    async def _category_response(self, category: BlogCategory) -> BlogCategoryResponse:
        count_stmt = select(func.count()).select_from(BlogPost).where(
            BlogPost.category_id == category.id,
            BlogPost.status == BlogPostStatus.PUBLISHED,
            BlogPost.deleted_at.is_(None),
        )
        post_count = (await self.db.execute(count_stmt)).scalar_one() or 0
        return BlogCategoryResponse(
            id=category.id,
            name=category.name,
            slug=category.slug,
            description=category.description,
            parent_id=category.parent_id,
            position=category.position,
            created_at=category.created_at,
            updated_at=category.updated_at,
            post_count=post_count,
            ancestors=await self._ancestors_of(category),
        )

    async def _tag_response(self, tag: BlogTag) -> BlogTagResponse:
        count_stmt = (
            select(func.count())
            .select_from(BlogPostTag)
            .join(BlogPost, BlogPost.id == BlogPostTag.post_id)
            .where(
                BlogPostTag.tag_id == tag.id,
                BlogPost.status == BlogPostStatus.PUBLISHED,
                BlogPost.deleted_at.is_(None),
            )
        )
        post_count = (await self.db.execute(count_stmt)).scalar_one() or 0
        return BlogTagResponse(
            id=tag.id,
            name=tag.name,
            slug=tag.slug,
            created_at=tag.created_at,
            updated_at=tag.updated_at,
            post_count=post_count,
        )

    async def list_categories(self) -> list[BlogCategoryResponse]:
        """List all categories with their published post counts."""
        # Subquery for published post count
        count_subq = (
            select(
                BlogPost.category_id,
                func.count(BlogPost.id).label("post_count"),
            )
            .where(BlogPost.status == BlogPostStatus.PUBLISHED)
            .group_by(BlogPost.category_id)
            .subquery()
        )

        stmt = (
            select(BlogCategory, func.coalesce(count_subq.c.post_count, 0).label("post_count"))
            .outerjoin(count_subq, count_subq.c.category_id == BlogCategory.id)
            .order_by(BlogCategory.name.asc())
        )

        rows = (await self.db.execute(stmt)).all()
        return [
            BlogCategoryResponse(
                id=cat.id,
                name=cat.name,
                slug=cat.slug,
                created_at=cat.created_at,
                updated_at=cat.updated_at,
                post_count=count,
            )
            for cat, count in rows
        ]

    async def get_category_by_id(self, category_id: uuid.UUID) -> BlogCategoryResponse:
        """Get category by UUID."""
        cat = await self.db.get(BlogCategory, category_id)
        if not cat:
            raise NotFoundError("Category", f"Category {category_id} not found")
        count_stmt = select(func.count(BlogPost.id)).where(
            BlogPost.category_id == category_id,
            BlogPost.status == BlogPostStatus.PUBLISHED,
        )
        count = (await self.db.execute(count_stmt)).scalar_one()
        return BlogCategoryResponse(
            id=cat.id,
            name=cat.name,
            slug=cat.slug,
            created_at=cat.created_at,
            updated_at=cat.updated_at,
            post_count=count,
        )

    async def get_category_by_slug(self, slug: str) -> BlogCategoryResponse:
        """Get category by slug."""
        stmt = select(BlogCategory).where(BlogCategory.slug == slug)
        cat = (await self.db.execute(stmt)).scalar_one_or_none()
        if not cat:
            raise NotFoundError("Category", f"Category '{slug}' not found")
        count_stmt = select(func.count(BlogPost.id)).where(
            BlogPost.category_id == cat.id,
            BlogPost.status == BlogPostStatus.PUBLISHED,
        )
        count = (await self.db.execute(count_stmt)).scalar_one()
        return BlogCategoryResponse(
            id=cat.id,
            name=cat.name,
            slug=cat.slug,
            created_at=cat.created_at,
            updated_at=cat.updated_at,
            post_count=count,
        )

    # ── Post Operations ───────────────────────────────────────────────────

    async def create_post(
        self,
        data: BlogPostCreate,
        author_id: uuid.UUID,
        permissions: set[str] | None = None,
    ) -> BlogPostDetailResponse:
        """Create a new blog article."""
        assert_may_publish(data.status, permissions=permissions)
        base_slug = data.slug.strip() if data.slug else generate_slug(data.title)
        slug = await self._ensure_unique_post_slug(base_slug)

        published_at = data.published_at
        status = data.status
        # Scheduling a future publish keeps the post as a draft until the beat
        # task promotes it at scheduled_for.
        if data.scheduled_for is not None and status == BlogPostStatus.DRAFT:
            published_at = None
        if status == BlogPostStatus.PUBLISHED and published_at is None:
            published_at = datetime.now(UTC)

        # Validate category if provided
        if data.category_id:
            cat = await self.db.get(BlogCategory, data.category_id)
            if not cat:
                raise NotFoundError("Category", f"Category {data.category_id} does not exist")

        post = BlogPost(
            author_id=author_id,
            title=data.title.strip(),
            slug=slug,
            content=sanitize_html(data.content),
            excerpt=data.excerpt.strip() if data.excerpt else None,
            cover_image_url=data.cover_image_url.strip() if data.cover_image_url else None,
            status=status,
            locale=data.locale,
            published_at=published_at,
            scheduled_for=data.scheduled_for,
            category_id=data.category_id,
            is_featured=data.is_featured,
            visibility=data.visibility,
            visibility_password=(
                _hash_post_password(data.visibility_password)
                if data.visibility_password
                else None
            ),
            allow_comments=await self._resolve_allow_comments(data.allow_comments),
            post_format=data.post_format,
            gallery_image_ids=data.gallery_image_ids,
        )
        self.db.add(post)
        await self.db.flush()

        await self._replace_post_tags(post, data.tag_ids)
        await self._snapshot_revision(post, created_by=author_id)

        await self.db.commit()
        await self.db.refresh(post)

        return await self.get_post_by_id(post.id)

    async def update_post(
        self,
        post_id: uuid.UUID,
        data: BlogPostUpdate,
        actor_id: uuid.UUID | None = None,
        permissions: set[str] | None = None,
    ) -> BlogPostDetailResponse:
        """Update an existing blog post, recording a content revision snapshot."""
        post = await self.db.get(BlogPost, post_id)
        if not post:
            raise NotFoundError("BlogPost", f"Blog post {post_id} not found")

        # Guard the *requested* status, and also the one the post already
        # holds: a contributor who can only edit their own draft must not be
        # able to touch fields on a post that is already live.
        assert_may_publish(data.status, permissions=permissions)
        if data.status is None and data.model_dump(exclude_unset=True).get("status") is None:
            assert_may_publish(post.status, permissions=permissions)

        update_dict = data.model_dump(exclude_unset=True)
        tag_ids = update_dict.pop("tag_ids", None)

        # Sanitise before the write and before the revision snapshot, so neither
        # the live row nor the revision history can hold a payload. The editor's
        # DOMPurify pass is not this boundary — the API takes the same field.
        if update_dict.get("content"):
            update_dict["content"] = sanitize_html(update_dict["content"])

        # Captured before the reassignment below: a post slug is a public URL, so
        # a rename 404s every link to the old one until the history row resolves
        # it back.
        previous_slug = post.slug

        if "title" in update_dict and "slug" not in update_dict and not post.slug:
            update_dict["slug"] = await self._ensure_unique_post_slug(
                generate_slug(update_dict["title"]), exclude_id=post_id
            )
        elif update_dict.get("slug"):
            update_dict["slug"] = await self._ensure_unique_post_slug(
                generate_slug(update_dict["slug"]), exclude_id=post_id
            )

        if "status" in update_dict:
            new_status = update_dict["status"]
            if new_status == BlogPostStatus.PUBLISHED:
                if post.published_at is None:
                    update_dict.setdefault("published_at", datetime.now(UTC))
                # Explicitly publishing clears any pending schedule.
                update_dict.setdefault("scheduled_for", None)

        if update_dict.get("category_id"):
            cat = await self.db.get(BlogCategory, update_dict["category_id"])
            if not cat:
                raise NotFoundError(
                    "Category", f"Category {update_dict['category_id']} does not exist"
                )

        # A submitted access password is stored hashed. An empty string means
        # "unchanged", not "clear": the API never returns the stored hash, so
        # the admin form cannot pre-fill the field and an untouched save must
        # not silently remove protection. Removing protection = switching
        # visibility away from "password".
        if "visibility_password" in update_dict:
            raw_password = update_dict["visibility_password"]
            if raw_password:
                update_dict["visibility_password"] = _hash_post_password(raw_password)
            else:
                update_dict.pop("visibility_password")

        # Snapshot when any content-bearing field changes.
        content_keys = {"title", "content", "excerpt", "cover_image_url", "status"}
        content_changed = any(
            key in update_dict and update_dict[key] != getattr(post, key)
            for key in content_keys
        )

        for key, value in update_dict.items():
            setattr(post, key, value)

        if content_changed:
            await self._snapshot_revision(post, created_by=actor_id)

        if post.slug != previous_slug:
            await record_slug_change(
                self.db,
                resource_type=SLUG_RESOURCE_BLOG_POST,
                resource_id=post.id,
                old_slug=previous_slug,
                new_slug=post.slug,
            )

        await self._replace_post_tags(post, tag_ids)

        await self.db.commit()
        await self.db.refresh(post)

        return await self.get_post_by_id(post.id)

    async def delete_post(self, post_id: uuid.UUID) -> None:
        """Soft delete: move to trash (restorable). Use hard_delete_post to purge."""
        post = await self.db.get(BlogPost, post_id)
        if not post:
            raise NotFoundError("BlogPost", f"Blog post {post_id} not found")

        if post.deleted_at is None:
            post.deleted_at = datetime.now(UTC)
            await self.db.commit()
        logger.info("blog_post_trashed", post_id=str(post_id))

    async def restore_post(self, post_id: uuid.UUID) -> BlogPostDetailResponse:
        """Restore a trashed post."""
        post = await self.db.get(BlogPost, post_id)
        if not post or post.deleted_at is None:
            raise NotFoundError("BlogPost", f"Trashed post {post_id} not found")
        post.deleted_at = None
        await self.db.commit()
        await self.db.refresh(post)
        logger.info("blog_post_restored", post_id=str(post_id))
        return await self.get_post_by_id(post.id)

    async def hard_delete_post(self, post_id: uuid.UUID) -> None:
        """Permanently delete a post (only allowed from trash)."""
        post = await self.db.get(BlogPost, post_id)
        if not post:
            raise NotFoundError("BlogPost", f"Blog post {post_id} not found")
        if post.deleted_at is None:
            raise NotFoundError("BlogPost", "پست ابتدا باید به سطل زباله منتقل شود")
        await self.db.delete(post)
        await self.db.commit()
        logger.info("blog_post_hard_deleted", post_id=str(post_id))

    async def duplicate_post(
        self, post_id: uuid.UUID, *, author_id: uuid.UUID | None = None
    ) -> BlogPostDetailResponse:
        """Copy a blog post as a new draft with a unique slug (WordPress 'Duplicate')."""
        post = await self.db.get(BlogPost, post_id)
        if not post:
            raise NotFoundError("BlogPost", f"Blog post {post_id} not found")
        copy_slug = await self._ensure_unique_post_slug(f"{post.slug}-copy")
        copy = BlogPost(
            author_id=author_id or post.author_id,
            title=f"{post.title} (copy)",
            slug=copy_slug,
            content=post.content,
            excerpt=post.excerpt,
            cover_image_url=post.cover_image_url,
            status=BlogPostStatus.DRAFT,
            locale=post.locale or "fa",
            category_id=post.category_id,
            is_featured=False,
            visibility=post.visibility,
            # The stored Argon2 hash is copied as-is so the copy enforces the
            # same password (copying only ``visibility`` would leave the copy
            # with a "password" label and no password to ask for).
            visibility_password=post.visibility_password,
            allow_comments=post.allow_comments,
        )
        self.db.add(copy)
        await self.db.flush()
        # Copy tags
        for pt in post.post_tags:
            self.db.add(BlogPostTag(post_id=copy.id, tag_id=pt.tag_id))
        await self._snapshot_revision(copy, created_by=author_id)
        await self.db.commit()
        await self.db.refresh(copy)
        logger.info("blog_post_duplicated", source_id=str(post_id), copy_id=str(copy.id))
        return await self.get_post_by_id(copy.id)

    async def get_post_by_id(self, post_id: uuid.UUID) -> BlogPostDetailResponse:
        """Get post detail by ID."""
        stmt = (
            select(BlogPost)
            .options(
                selectinload(BlogPost.category),
                selectinload(BlogPost.post_tags).selectinload(BlogPostTag.tag),
            )
            .where(BlogPost.id == post_id)
        )
        post = (await self.db.execute(stmt)).scalar_one_or_none()
        if not post:
            raise NotFoundError("BlogPost", f"Blog post {post_id} not found")

        views = await self.get_view_count(post.id)
        author_name = await self.get_author_name(post.author_id)
        author_slug = await self.get_author_slug(post.author_id)

        base = self._post_to_response(post, views, author_name, author_slug=author_slug)
        related = await self._get_related_posts(post.category_id, exclude_id=post.id)
        seo_dict = await self._get_seo_dict(post.id)

        return BlogPostDetailResponse(
            **base.model_dump(),
            content=await self._render_content(post.content),
            related_posts=related,
            seo=seo_dict,
        )

    async def _render_content(self, content: str, *, include_unpublished: bool = False) -> str:
        """Resolve reusable blocks and shortcodes in a stored post body.

        Storage keeps the authored tokens (see ``_snapshot_revision``, which
        must snapshot what the author wrote); display resolves them.
        """
        from app.shared.content.render import render_body

        return await render_body(
            self.db, content, include_unpublished=include_unpublished
        )

    async def get_post_by_slug(
        self,
        slug: str,
        increment_views: bool = True,
        only_published: bool = True,
        access_password: str | None = None,
    ) -> BlogPostDetailResponse:
        """Retrieve a blog post by its slug.

        A password-protected post (``visibility == PASSWORD``) whose password
        was not supplied — or was wrong — returns its metadata with the body
        withheld (``content_locked=True``, empty ``content``). WordPress
        behaves the same way: the post page renders a password form rather
        than a 404, so readers can still find the article.

        ``access_password`` is verified against the stored Argon2 hash; the
        hash itself is never serialized into any response.
        """
        stmt = (
            select(BlogPost)
            .options(
                selectinload(BlogPost.category),
                selectinload(BlogPost.post_tags).selectinload(BlogPostTag.tag),
            )
            .where(BlogPost.slug == slug)
        )
        if only_published:
            stmt = stmt.where(BlogPost.status == BlogPostStatus.PUBLISHED)

        post = (await self.db.execute(stmt)).scalar_one_or_none()
        if not post:
            raise NotFoundError("BlogPost", f"Article '{slug}' not found")

        locked = await self._is_password_locked(post, access_password)

        if increment_views and not locked:
            views = await self.increment_view_count(post.id)
        else:
            views = await self.get_view_count(post.id)

        author_name = await self.get_author_name(post.author_id)
        author_slug = await self.get_author_slug(post.author_id)

        base = self._post_to_response(post, views, author_name, author_slug=author_slug)
        related = await self._get_related_posts(post.category_id, exclude_id=post.id)
        seo_dict = await self._get_seo_dict(post.id)

        if locked:
            return BlogPostDetailResponse(
                **base.model_dump(),
                content="",
                content_locked=True,
                related_posts=related,
                seo=seo_dict,
            )

        return BlogPostDetailResponse(
            **base.model_dump(),
            content=await self._render_content(
                post.content, include_unpublished=not only_published
            ),
            related_posts=related,
            seo=seo_dict,
        )

    async def _is_password_locked(
        self, post: BlogPost, access_password: str | None
    ) -> bool:
        """Whether this post's body must be withheld from the caller.

        Only ``PASSWORD`` visibility locks anything, and only when a stored
        hash exists — a password-visibility post with no password set is
        treated as public rather than permanently unreadable (WordPress does
        the same when the password field is empty).
        """
        if post.visibility != PostVisibility.PASSWORD:
            return False
        if not post.visibility_password:
            return False
        if not access_password:
            return True
        from app.core.security.password import verify_password

        try:
            return not verify_password(access_password, post.visibility_password)
        except Exception:
            # A malformed stored hash must not 500 the article page — treat
            # it as "cannot verify", i.e. locked.
            logger.warning("blog_post_password_hash_invalid", post_id=str(post.id))
            return True

    async def _get_related_posts(
        self,
        category_id: uuid.UUID | None,
        exclude_id: uuid.UUID,
        limit: int = 3,
    ) -> list[BlogPostResponse]:
        """Fetch related published articles in the same category (or most recent)."""
        stmt = (
            select(BlogPost)
            .options(
                selectinload(BlogPost.category),
                selectinload(BlogPost.post_tags).selectinload(BlogPostTag.tag),
            )
            .where(
                BlogPost.id != exclude_id,
                BlogPost.status == BlogPostStatus.PUBLISHED,
                # Related-posts is a public surface: private posts are
                # excluded outright, protected ones only advertise their
                # title (the excerpt/body stay behind the post's own page).
                BlogPost.visibility != PostVisibility.PRIVATE,
                BlogPost.deleted_at.is_(None),
            )
        )
        if category_id:
            stmt = stmt.where(BlogPost.category_id == category_id)

        stmt = stmt.order_by(BlogPost.published_at.desc().nullslast()).limit(limit)
        posts = (await self.db.execute(stmt)).scalars().all()

        results: list[BlogPostResponse] = []
        for p in posts:
            views = await self.get_view_count(p.id)
            author_name = await self.get_author_name(p.author_id)
            author_slug = await self.get_author_slug(p.author_id)
            results.append(self._post_to_response(p, views, author_name, author_slug=author_slug))
        return results

    # Strapi-style sortable columns: allowlisted so ?sort= never reaches SQL raw.
    _POST_SORT_COLUMNS: ClassVar[dict[str, str]] = {
        "title": "title",
        "published_at": "published_at",
        "created_at": "created_at",
        "updated_at": "updated_at",
    }

    async def list_posts(
        self,
        category_slug: str | None = None,
        status: BlogPostStatus | None = BlogPostStatus.PUBLISHED,
        search: str | None = None,
        tag_slug: str | None = None,
        page: int = 1,
        page_size: int = 10,
        sort: str | None = None,
        include_trashed: bool = False,
        public_only: bool = False,
    ) -> BlogListResponse:
        """List articles with category, tag, status filters, and pagination.

        ``sort`` follows the Strapi convention: ``<field>[:asc|desc]`` —
        e.g. ``title:asc`` or ``published_at:desc``. Unknown fields fall back
        to the default newest-first order.

        Trashed (soft-deleted) posts are hidden unless ``include_trashed``.
        Featured posts are ordered first within public listings.

        ``public_only`` (set by the storefront route, never by admin) drops
        private posts entirely — the admin list must keep seeing them — and
        replaces a password-protected post's excerpt with WordPress's
        "no excerpt because this is a protected post" placeholder instead of
        falling back to a derived summary of the withheld body.
        """
        stmt = select(BlogPost).options(
            selectinload(BlogPost.category),
            # The nested ``tag`` must be named explicitly: eager-loading only
            # ``post_tags`` leaves each association's ``tag`` to lazy-load,
            # which raises MissingGreenlet under asyncio the moment the
            # response mapper reads ``pt.tag``.
            selectinload(BlogPost.post_tags).selectinload(BlogPostTag.tag),
        )

        # Soft delete: hide trashed posts by default
        if not include_trashed:
            stmt = stmt.where(BlogPost.deleted_at.is_(None))

        # Private posts never leave the admin panel (WordPress parity).
        if public_only:
            stmt = stmt.where(BlogPost.visibility != PostVisibility.PRIVATE)

        if status is not None:
            stmt = stmt.where(BlogPost.status == status)

        if category_slug:
            stmt = stmt.join(BlogPost.category).where(BlogCategory.slug == category_slug)

        if tag_slug:
            stmt = (
                stmt.join(BlogPostTag, BlogPostTag.post_id == BlogPost.id)
                .join(BlogTag, BlogTag.id == BlogPostTag.tag_id)
                .where(BlogTag.slug == tag_slug)
            )

        if search:
            like_q = f"%{search.strip()}%"
            stmt = stmt.where(
                or_(
                    BlogPost.title.ilike(like_q),
                    BlogPost.excerpt.ilike(like_q),
                    BlogPost.content.ilike(like_q),
                )
            )

        # Count total
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.db.execute(count_stmt)).scalar_one()

        # Ordering & Pagination — featured posts first, then by date
        order_clause: Any = [
            BlogPost.is_featured.desc(),
            BlogPost.published_at.desc().nullslast(),
            BlogPost.created_at.desc(),
        ]
        if sort:
            field, _, direction = sort.partition(":")
            column_name = self._POST_SORT_COLUMNS.get(field.strip())
            if column_name is not None:
                column = getattr(BlogPost, column_name)
                order_clause = [
                    column.asc() if direction.strip().lower() == "asc" else column.desc()
                ]

        stmt = (
            stmt.order_by(*order_clause)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )

        posts = (await self.db.execute(stmt)).scalars().all()

        # A post with no authored excerpt would render an empty paragraph in
        # the list, so fall back to a derived summary at the admin's length.
        from app.modules.settings.application.site_options_service import (
            SiteOptionsService,
        )

        excerpt_limit = await SiteOptionsService.get_int(
            self.db, "excerpt_length", 55, minimum=5, maximum=300
        )
        # Read once for the whole page rather than per post. None means "unset",
        # which keeps auto_excerpt's own "..." default.
        excerpt_more = await SiteOptionsService.get(self.db, "excerpt_more")

        items: list[BlogPostResponse] = []
        for p in posts:
            views = await self.get_view_count(p.id)
            author_name = await self.get_author_name(p.author_id)
            author_slug = await self.get_author_slug(p.author_id)
            # A locked post must not leak its body through a derived excerpt.
            locked = public_only and p.visibility == PostVisibility.PASSWORD
            limit = None if locked else excerpt_limit
            item = self._post_to_response(
                p,
                views,
                author_name,
                author_slug=author_slug,
                excerpt_word_limit=limit,
                excerpt_more=None if locked else excerpt_more,
            )
            if locked:
                item.excerpt = "خلاصه‌ای برای این نوشته‌ی محافظت‌شده نمایش داده نمی‌شود."
            items.append(item)

        total_pages = max(1, math.ceil(total / page_size)) if total > 0 else 0

        return BlogListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_prev=page > 1,
        )

    async def get_recent_posts(self, limit: int = 5) -> list[BlogPostResponse]:
        """Fetch recent published articles for home page or sidebar.

        Public surface: private posts are excluded; a password-protected post
        keeps its title (it is visible to readers on the list) but its
        derived excerpt is replaced by the protected-post placeholder.
        """
        stmt = (
            select(BlogPost)
            .options(
                selectinload(BlogPost.category),
                selectinload(BlogPost.post_tags).selectinload(BlogPostTag.tag),
            )
            .where(
                BlogPost.status == BlogPostStatus.PUBLISHED,
                BlogPost.deleted_at.is_(None),
                BlogPost.visibility != PostVisibility.PRIVATE,
            )
            .order_by(BlogPost.published_at.desc().nullslast())
            .limit(limit)
        )
        posts = (await self.db.execute(stmt)).scalars().all()

        items: list[BlogPostResponse] = []
        for p in posts:
            views = await self.get_view_count(p.id)
            author_name = await self.get_author_name(p.author_id)
            author_slug = await self.get_author_slug(p.author_id)
            items.append(self._post_to_response(p, views, author_name, author_slug=author_slug))
        return items

    # ── Hierarchical categories ───────────────────────────────────────────

    async def _descendant_ids(self, category_id: uuid.UUID) -> set[uuid.UUID]:
        """Every category beneath ``category_id``, at any depth.

        Walks the tree iteratively with a visited set: a cycle introduced by a
        bad write (or a hand-edited row) must not hang the request.
        """
        found: set[uuid.UUID] = set()
        frontier = [category_id]
        while frontier:
            # Selecting parent_id for the frontier's children, then selecting
            # those children by parent_id: one round trip per level, and no
            # reliance on ORM relationship state that a prior commit expired.
            stmt = (
                select(BlogCategory.id)
                .where(
                    BlogCategory.parent_id.in_(frontier),
                    BlogCategory.id != category_id,
                )
                .limit(1000)
            )
            children = set((await self.db.execute(stmt)).scalars().all())
            children -= found
            if not children:
                break
            found |= children
            frontier = list(children)
        return found

    async def _ancestors_of(self, category: BlogCategory) -> list[dict[str, Any]]:
        """The chain from the root down to (but not including) the category.

        WordPress's ``get_ancestors`` order, so a breadcrumb renders
        "خانه / لپ‌تاپ / گیمینگ" and the last entry is the current page.
        """
        chain: list[dict[str, Any]] = []
        seen: set[uuid.UUID] = {category.id}
        # Walk the parent ids rather than the relationship: a freshly assigned
        # or a just-committed row may not have its parent loaded, and touching
        # the lazy attribute inside async code raises MissingGreenlet.
        current_id = category.parent_id
        while current_id is not None and current_id not in seen:
            seen.add(current_id)
            row = (
                await self.db.execute(
                    select(BlogCategory).where(BlogCategory.id == current_id)
                )
            ).scalar_one_or_none()
            if row is None:
                break
            chain.append({"id": row.id, "name": row.name, "slug": row.slug})
            current_id = row.parent_id
        chain.reverse()
        return chain

    async def _would_create_cycle(
        self, category_id: uuid.UUID, new_parent_id: uuid.UUID | None
    ) -> bool:
        """Whether re-parenting ``category_id`` under ``new_parent_id`` loops.

        A category cannot be its own parent, nor be moved under one of its own
        descendants — either would make the tree infinitely deep and any
        "descendants of X" walk recurse forever.
        """
        if new_parent_id is None:
            return False
        if new_parent_id == category_id:
            return True
        return new_parent_id in await self._descendant_ids(category_id)

    async def get_category_tree(self) -> list[BlogCategoryResponse]:
        """The full category forest, roots first, each with nested children."""
        stmt = select(BlogCategory).order_by(BlogCategory.position, BlogCategory.name)
        rows = list((await self.db.execute(stmt)).scalars().unique().all())

        counts = await self._published_counts()
        known = {c.id for c in rows}
        # Build bottom-up: a node's children must exist before its parent is
        # assembled, so resolve deepest-first to keep it one pass.
        def _to_response(node: BlogCategory) -> BlogCategoryResponse:
            kids = [c for c in rows if c.parent_id == node.id]
            return BlogCategoryResponse(
                id=node.id,
                name=node.name,
                slug=node.slug,
                description=node.description,
                parent_id=node.parent_id,
                position=node.position,
                created_at=node.created_at,
                updated_at=node.updated_at,
                post_count=counts.get(node.id, 0),
                children=[_to_response(k) for k in kids],
            )

        roots = [c for c in rows if c.parent_id is None or c.parent_id not in known]
        return [_to_response(r) for r in sorted(roots, key=lambda c: (c.position, c.name))]

    async def _published_counts(self) -> dict[uuid.UUID, int]:
        """Published post count per category, in one query.

        One grouped query rather than a count per category: a 50-category blog
        would otherwise issue 50 round-trips to render a list.
        """
        stmt = (
            select(BlogPost.category_id, func.count(BlogPost.id))
            .where(
                BlogPost.status == BlogPostStatus.PUBLISHED,
                BlogPost.deleted_at.is_(None),
                BlogPost.category_id.is_not(None),
            )
            .group_by(BlogPost.category_id)
        )
        return {
            cid: count
            for cid, count in (await self.db.execute(stmt)).all()
            if cid is not None
        }

    async def list_categories_hierarchical(self) -> list[BlogCategoryResponse]:
        """Flat list with ancestry attached — what the admin table renders."""
        stmt = select(BlogCategory).order_by(BlogCategory.position, BlogCategory.name)
        rows = list((await self.db.execute(stmt)).scalars().unique().all())
        counts = await self._published_counts()
        out: list[BlogCategoryResponse] = []
        for node in rows:
            out.append(
                BlogCategoryResponse(
                    id=node.id,
                    name=node.name,
                    slug=node.slug,
                    description=node.description,
                    parent_id=node.parent_id,
                    position=node.position,
                    created_at=node.created_at,
                    updated_at=node.updated_at,
                    post_count=counts.get(node.id, 0),
                    ancestors=await self._ancestors_of(node),
                )
            )
        return out

    async def bulk_posts(
        self,
        post_ids: list[uuid.UUID],
        action: str,
        *,
        actor_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Apply one action to many posts, reporting per-post outcomes.

        Partial success is the contract: an editor selecting 20 posts may not
        own all 20, and silently skipping the 3 they cannot touch would make the
        UI say "20 done" while 3 silently did nothing. Every post gets an entry
        in ``results`` — ``ok`` or ``error`` — and the counts say what really
        happened.

        Ownership is re-checked per post through the same capability helper the
        single-post routes use, so a bulk call is exactly as strict as the
        equivalent N individual calls.
        """
        from app.core.security.object_capabilities import (
            OBJECT_RULES,
            require_object_capability,
        )

        if action not in {"publish", "draft", "archive", "trash", "restore"}:
            from app.core.exceptions.handlers import ValidationError

            raise ValidationError(f"عملیات ناشناخته: {action}")

        results: list[dict[str, Any]] = []
        ok = 0
        failed = 0

        for post_id in post_ids:
            try:
                post = await self.db.get(BlogPost, post_id)
                if post is None:
                    raise NotFoundError("BlogPost", f"Blog post {post_id} not found")

                if actor_payload is not None:
                    # Same helper, same rule table as the single-post routes.
                    await require_object_capability(
                        actor_payload, post, OBJECT_RULES["posts"]
                    )

                if action == "trash":
                    if post.deleted_at is None:
                        post.deleted_at = datetime.now(UTC)
                elif action == "restore":
                    if post.deleted_at is None:
                        raise ValidationError("این نوشته در سطل زباله نیست")
                    post.deleted_at = None
                elif action == "publish":
                    post.status = BlogPostStatus.PUBLISHED
                    post.published_at = post.published_at or datetime.now(UTC)
                elif action == "draft":
                    post.status = BlogPostStatus.DRAFT
                elif action == "archive":
                    post.status = BlogPostStatus.ARCHIVED

                results.append({"id": str(post_id), "ok": True})
                ok += 1
            except Exception as exc:  # noqa: BLE001 — one bad post must not abort the batch
                failed += 1
                results.append({"id": str(post_id), "ok": False, "error": str(exc)})

        await self.db.commit()
        logger.info(
            "blog_posts_bulk_action", action=action, ok=ok, failed=failed
        )
        return {
            "action": action,
            "ok": ok,
            "failed": failed,
            "total": len(post_ids),
            "results": results,
        }
