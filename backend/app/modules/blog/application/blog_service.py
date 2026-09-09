"""Blog service handling business logic for blog posts and categories."""

from __future__ import annotations

import math
import re
import unicodedata
import uuid
from datetime import datetime, timezone
from typing import Optional

import structlog
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.cache.redis import get_redis
from app.core.exceptions.handlers import ConflictError, NotFoundError
from app.modules.blog.domain.models import BlogCategory, BlogPost, BlogPostStatus
from app.modules.blog.schemas.blog import (
    BlogCategoryCreate,
    BlogCategoryResponse,
    BlogListResponse,
    BlogPostCreate,
    BlogPostDetailResponse,
    BlogPostResponse,
    BlogPostUpdate,
)
from app.modules.seo.domain.models import SEOMetadata
from app.modules.users.domain.models import User, UserProfile

logger: structlog.stdlib.BoundLogger = structlog.get_logger()

# ── Persian Transliteration for URL Slugs ──────────────────────────────────
_PERSIAN_TO_LATIN: dict[str, str] = {
    "آ": "a", "ا": "a", "ب": "b", "پ": "p", "ت": "t", "ث": "s",
    "ج": "j", "چ": "ch", "ح": "h", "خ": "kh", "د": "d", "ذ": "z",
    "ر": "r", "ز": "z", "ژ": "zh", "س": "s", "ش": "sh", "ص": "s",
    "ض": "z", "ط": "t", "ظ": "z", "ع": "a", "غ": "gh", "ف": "f",
    "ق": "gh", "ک": "k", "گ": "g", "ل": "l", "م": "m", "ن": "n",
    "و": "v", "ه": "h", "ی": "y", "ئ": "y", "ي": "y", "ك": "k",
    "ة": "h", "إ": "e", "أ": "a", "ؤ": "v",
    "۰": "0", "۱": "1", "۲": "2", "۳": "3", "۴": "4",
    "۵": "5", "۶": "6", "۷": "7", "۸": "8", "۹": "9",
    "٠": "0", "١": "1", "٢": "2", "٣": "3", "٤": "4",
    "٥": "5", "٦": "6", "٧": "7", "٨": "8", "٩": "9",
}

_DIACRITICS_RE = re.compile(
    r"[\u064B-\u065F\u0670\u06D6-\u06ED\u200B-\u200F\u202A-\u202E\uFEFF]"
)


def generate_slug(text: str) -> str:
    """Generate a clean URL-safe slug from Persian or English text."""
    if not text:
        return ""
    text = _DIACRITICS_RE.sub("", text)
    text = text.replace("\u200c", "-")  # Half-space (ZWNJ)
    transliterated = [_PERSIAN_TO_LATIN.get(ch, ch) for ch in text]
    text = "".join(transliterated)
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = text.lower()
    text = re.sub(r"[^a-z0-9-]", "-", text)
    text = re.sub(r"-{2,}", "-", text)
    return text.strip("-") or "post"


def calculate_reading_time(content: str) -> int:
    """Calculate approximate reading time in minutes (assuming 200 wpm)."""
    words = len(re.findall(r"\w+", content))
    return max(1, math.ceil(words / 200))


class BlogService:
    """Service encapsulating CRUD and business logic for blog posts and categories."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Slug Uniqueness Helpers ───────────────────────────────────────────

    async def _post_slug_exists(self, slug: str, exclude_id: Optional[uuid.UUID] = None) -> bool:
        stmt = select(func.count(BlogPost.id)).where(BlogPost.slug == slug)
        if exclude_id is not None:
            stmt = stmt.where(BlogPost.id != exclude_id)
        count = (await self.db.execute(stmt)).scalar_one()
        return count > 0

    async def _category_slug_exists(self, slug: str, exclude_id: Optional[uuid.UUID] = None) -> bool:
        stmt = select(func.count(BlogCategory.id)).where(BlogCategory.slug == slug)
        if exclude_id is not None:
            stmt = stmt.where(BlogCategory.id != exclude_id)
        count = (await self.db.execute(stmt)).scalar_one()
        return count > 0

    async def _ensure_unique_post_slug(self, slug: str, exclude_id: Optional[uuid.UUID] = None) -> str:
        candidate = slug
        counter = 1
        while await self._post_slug_exists(candidate, exclude_id=exclude_id):
            candidate = f"{slug}-{counter}"
            counter += 1
        return candidate

    async def _ensure_unique_category_slug(self, slug: str, exclude_id: Optional[uuid.UUID] = None) -> str:
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

    # ── Category Operations ───────────────────────────────────────────────

    async def create_category(self, data: BlogCategoryCreate) -> BlogCategoryResponse:
        """Create a new blog category."""
        base_slug = data.slug.strip() if data.slug else generate_slug(data.name)
        slug = await self._ensure_unique_category_slug(base_slug)

        category = BlogCategory(name=data.name.strip(), slug=slug)
        self.db.add(category)
        await self.db.commit()
        await self.db.refresh(category)

        return BlogCategoryResponse(
            id=category.id,
            name=category.name,
            slug=category.slug,
            created_at=category.created_at,
            updated_at=category.updated_at,
            post_count=0,
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
    ) -> BlogPostDetailResponse:
        """Create a new blog article."""
        base_slug = data.slug.strip() if data.slug else generate_slug(data.title)
        slug = await self._ensure_unique_post_slug(base_slug)

        published_at = data.published_at
        if data.status == BlogPostStatus.PUBLISHED and published_at is None:
            published_at = datetime.now(timezone.utc)

        # Validate category if provided
        if data.category_id:
            cat = await self.db.get(BlogCategory, data.category_id)
            if not cat:
                raise NotFoundError("Category", f"Category {data.category_id} does not exist")

        post = BlogPost(
            author_id=author_id,
            title=data.title.strip(),
            slug=slug,
            content=data.content,
            excerpt=data.excerpt.strip() if data.excerpt else None,
            cover_image_url=data.cover_image_url.strip() if data.cover_image_url else None,
            status=data.status,
            published_at=published_at,
            category_id=data.category_id,
        )
        self.db.add(post)
        await self.db.commit()
        await self.db.refresh(post)

        return await self.get_post_by_id(post.id)

    async def update_post(
        self,
        post_id: uuid.UUID,
        data: BlogPostUpdate,
    ) -> BlogPostDetailResponse:
        """Update an existing blog post."""
        post = await self.db.get(BlogPost, post_id)
        if not post:
            raise NotFoundError("BlogPost", f"Blog post {post_id} not found")

        update_dict = data.model_dump(exclude_unset=True)

        if "title" in update_dict and "slug" not in update_dict and not post.slug:
            update_dict["slug"] = await self._ensure_unique_post_slug(
                generate_slug(update_dict["title"]), exclude_id=post_id
            )
        elif "slug" in update_dict and update_dict["slug"]:
            update_dict["slug"] = await self._ensure_unique_post_slug(
                generate_slug(update_dict["slug"]), exclude_id=post_id
            )

        if "status" in update_dict:
            new_status = update_dict["status"]
            if new_status == BlogPostStatus.PUBLISHED and post.published_at is None:
                update_dict.setdefault("published_at", datetime.now(timezone.utc))

        if "category_id" in update_dict and update_dict["category_id"]:
            cat = await self.db.get(BlogCategory, update_dict["category_id"])
            if not cat:
                raise NotFoundError("Category", f"Category {update_dict['category_id']} does not exist")

        for key, value in update_dict.items():
            setattr(post, key, value)

        await self.db.commit()
        await self.db.refresh(post)

        return await self.get_post_by_id(post.id)

    async def delete_post(self, post_id: uuid.UUID) -> None:
        """Delete a blog article."""
        post = await self.db.get(BlogPost, post_id)
        if not post:
            raise NotFoundError("BlogPost", f"Blog post {post_id} not found")

        await self.db.delete(post)
        await self.db.commit()

    async def get_post_by_id(self, post_id: uuid.UUID) -> BlogPostDetailResponse:
        """Get post detail by ID."""
        stmt = (
            select(BlogPost)
            .options(selectinload(BlogPost.category))
            .where(BlogPost.id == post_id)
        )
        post = (await self.db.execute(stmt)).scalar_one_or_none()
        if not post:
            raise NotFoundError("BlogPost", f"Blog post {post_id} not found")

        views = await self.get_view_count(post.id)
        author_name = await self.get_author_name(post.author_id)
        reading_time = calculate_reading_time(post.content)

        category_resp = None
        if post.category:
            category_resp = BlogCategoryResponse.model_validate(post.category)

        # Related posts
        related = await self._get_related_posts(post.category_id, exclude_id=post.id)

        # SEO metadata
        seo_stmt = select(SEOMetadata).where(
            SEOMetadata.resource_type == "blog_post",
            SEOMetadata.resource_id == post.id,
        )
        seo = (await self.db.execute(seo_stmt)).scalar_one_or_none()
        seo_dict = None
        if seo:
            seo_dict = {
                "title": seo.title,
                "description": seo.description,
                "canonical_url": seo.canonical_url,
                "og_title": seo.og_title,
                "og_description": seo.og_description,
                "og_image": seo.og_image,
                "schema_markup": seo.schema_markup,
            }

        return BlogPostDetailResponse(
            id=post.id,
            author_id=post.author_id,
            title=post.title,
            slug=post.slug,
            content=post.content,
            excerpt=post.excerpt,
            cover_image_url=post.cover_image_url,
            status=post.status,
            published_at=post.published_at,
            category_id=post.category_id,
            category=category_resp,
            reading_time=reading_time,
            view_count=views,
            author_name=author_name,
            related_posts=related,
            seo=seo_dict,
            created_at=post.created_at,
            updated_at=post.updated_at,
        )

    async def get_post_by_slug(
        self,
        slug: str,
        increment_views: bool = True,
        only_published: bool = True,
    ) -> BlogPostDetailResponse:
        """Retrieve a blog post by its slug."""
        stmt = (
            select(BlogPost)
            .options(selectinload(BlogPost.category))
            .where(BlogPost.slug == slug)
        )
        if only_published:
            stmt = stmt.where(BlogPost.status == BlogPostStatus.PUBLISHED)

        post = (await self.db.execute(stmt)).scalar_one_or_none()
        if not post:
            raise NotFoundError("BlogPost", f"Article '{slug}' not found")

        views = 0
        if increment_views:
            views = await self.increment_view_count(post.id)
        else:
            views = await self.get_view_count(post.id)

        author_name = await self.get_author_name(post.author_id)
        reading_time = calculate_reading_time(post.content)

        category_resp = None
        if post.category:
            category_resp = BlogCategoryResponse.model_validate(post.category)

        # Related posts
        related = await self._get_related_posts(post.category_id, exclude_id=post.id)

        # SEO metadata
        seo_stmt = select(SEOMetadata).where(
            SEOMetadata.resource_type == "blog_post",
            SEOMetadata.resource_id == post.id,
        )
        seo = (await self.db.execute(seo_stmt)).scalar_one_or_none()
        seo_dict = None
        if seo:
            seo_dict = {
                "title": seo.title,
                "description": seo.description,
                "canonical_url": seo.canonical_url,
                "og_title": seo.og_title,
                "og_description": seo.og_description,
                "og_image": seo.og_image,
                "schema_markup": seo.schema_markup,
            }

        return BlogPostDetailResponse(
            id=post.id,
            author_id=post.author_id,
            title=post.title,
            slug=post.slug,
            content=post.content,
            excerpt=post.excerpt,
            cover_image_url=post.cover_image_url,
            status=post.status,
            published_at=post.published_at,
            category_id=post.category_id,
            category=category_resp,
            reading_time=reading_time,
            view_count=views,
            author_name=author_name,
            related_posts=related,
            seo=seo_dict,
            created_at=post.created_at,
            updated_at=post.updated_at,
        )

    async def _get_related_posts(
        self,
        category_id: Optional[uuid.UUID],
        exclude_id: uuid.UUID,
        limit: int = 3,
    ) -> list[BlogPostResponse]:
        """Fetch related published articles in the same category (or most recent)."""
        stmt = (
            select(BlogPost)
            .options(selectinload(BlogPost.category))
            .where(
                BlogPost.id != exclude_id,
                BlogPost.status == BlogPostStatus.PUBLISHED,
            )
        )
        if category_id:
            stmt = stmt.where(BlogPost.category_id == category_id)

        stmt = stmt.order_by(BlogPost.published_at.desc().nullslast()).limit(limit)
        posts = (await self.db.execute(stmt)).scalars().all()

        results: list[BlogPostResponse] = []
        for p in posts:
            views = await self.get_view_count(p.id)
            cat_resp = BlogCategoryResponse.model_validate(p.category) if p.category else None
            results.append(
                BlogPostResponse(
                    id=p.id,
                    author_id=p.author_id,
                    title=p.title,
                    slug=p.slug,
                    excerpt=p.excerpt,
                    cover_image_url=p.cover_image_url,
                    status=p.status,
                    published_at=p.published_at,
                    category_id=p.category_id,
                    category=cat_resp,
                    reading_time=calculate_reading_time(p.content),
                    view_count=views,
                    author_name=await self.get_author_name(p.author_id),
                    created_at=p.created_at,
                    updated_at=p.updated_at,
                )
            )
        return results

    async def list_posts(
        self,
        category_slug: Optional[str] = None,
        status: Optional[BlogPostStatus] = BlogPostStatus.PUBLISHED,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 10,
    ) -> BlogListResponse:
        """List articles with category filter, status filter, and pagination."""
        stmt = select(BlogPost).options(selectinload(BlogPost.category))

        if status is not None:
            stmt = stmt.where(BlogPost.status == status)

        if category_slug:
            stmt = stmt.join(BlogPost.category).where(BlogCategory.slug == category_slug)

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

        # Ordering & Pagination
        stmt = (
            stmt.order_by(
                BlogPost.published_at.desc().nullslast(),
                BlogPost.created_at.desc(),
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        )

        posts = (await self.db.execute(stmt)).scalars().all()

        items: list[BlogPostResponse] = []
        for p in posts:
            views = await self.get_view_count(p.id)
            cat_resp = BlogCategoryResponse.model_validate(p.category) if p.category else None
            author_name = await self.get_author_name(p.author_id)
            items.append(
                BlogPostResponse(
                    id=p.id,
                    author_id=p.author_id,
                    title=p.title,
                    slug=p.slug,
                    excerpt=p.excerpt,
                    cover_image_url=p.cover_image_url,
                    status=p.status,
                    published_at=p.published_at,
                    category_id=p.category_id,
                    category=cat_resp,
                    reading_time=calculate_reading_time(p.content),
                    view_count=views,
                    author_name=author_name,
                    created_at=p.created_at,
                    updated_at=p.updated_at,
                )
            )

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
        """Fetch recent published articles for home page or sidebar."""
        stmt = (
            select(BlogPost)
            .options(selectinload(BlogPost.category))
            .where(BlogPost.status == BlogPostStatus.PUBLISHED)
            .order_by(BlogPost.published_at.desc().nullslast())
            .limit(limit)
        )
        posts = (await self.db.execute(stmt)).scalars().all()

        items: list[BlogPostResponse] = []
        for p in posts:
            views = await self.get_view_count(p.id)
            cat_resp = BlogCategoryResponse.model_validate(p.category) if p.category else None
            author_name = await self.get_author_name(p.author_id)
            items.append(
                BlogPostResponse(
                    id=p.id,
                    author_id=p.author_id,
                    title=p.title,
                    slug=p.slug,
                    excerpt=p.excerpt,
                    cover_image_url=p.cover_image_url,
                    status=p.status,
                    published_at=p.published_at,
                    category_id=p.category_id,
                    category=cat_resp,
                    reading_time=calculate_reading_time(p.content),
                    view_count=views,
                    author_name=author_name,
                    created_at=p.created_at,
                    updated_at=p.updated_at,
                )
            )
        return items
