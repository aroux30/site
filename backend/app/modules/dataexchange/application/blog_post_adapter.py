"""Blog post entity adapter for the generic import/export framework.

Import upserts a ``BlogPost`` matched by slug (``blog_posts.slug`` is
globally unique): an existing slug updates the row, a new slug creates it.
Taxonomy columns carry comma-separated slugs — categories and tags are
resolved by slug and created when missing (WordPress importer behaviour);
with a single ``category_id`` column the first resolved category becomes the
post's primary category.

SEO columns map to ``BlogPostMeta`` key-value rows (``seo_title`` /
``seo_description``), the same wp_postmeta-style override store the blog
module uses — no schema changes required.

New posts need an author (``blog_posts.author_id`` is NOT NULL): the adapter
declares ``upsert_accepts_created_by`` so the pipeline passes the importing
user; without one it falls back to the first superuser and, failing that,
rejects the row.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import select

from app.core.exceptions.handlers import ValidationError
from app.modules.blog.domain.models import (
    BlogCategory,
    BlogPost,
    BlogPostMeta,
    BlogPostStatus,
    BlogPostTag,
    BlogTag,
)
from app.modules.dataexchange.application.adapters import (
    ColumnSpec,
    EntityAdapter,
    is_valid_slug,
    register_adapter,
)
from app.modules.users.domain.models import User

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

#: Status values actually stored in ``blog_posts.status`` (native_enum=False).
_ALLOWED_STATUSES = {s.value for s in BlogPostStatus}
#: ``BlogPostMeta`` keys the seo_title/seo_description columns map to.
SEO_META_KEYS = ("seo_title", "seo_description")


# ---------------------------------------------------------------------------
# Column-level validators (return a Persian error message or None)
# ---------------------------------------------------------------------------


def _validate_title(value: str) -> str | None:
    if len(value) > 500:
        return "عنوان مطلب بیش از ۵۰۰ کاراکتر است"
    return None


def _validate_slug(value: str) -> str | None:
    if not is_valid_slug(value):
        return f"نامک «{value}» معتبر نیست (فقط حروف، اعداد و خط تیره)"
    return None


def _validate_status(value: str) -> str | None:
    if value.strip().lower() not in _ALLOWED_STATUSES:
        allowed = "، ".join(sorted(_ALLOWED_STATUSES))
        return f"وضعیت «{value}» معتبر نیست (مقادیر مجاز: {allowed})"
    return None


def _validate_locale(value: str) -> str | None:
    if not 2 <= len(value.strip()) <= 10:
        return "کد زبان باید بین ۲ تا ۱۰ کاراکتر باشد (مثلاً fa)"
    return None


def _validate_excerpt(value: str) -> str | None:
    if len(value) > 1000:
        return "چکیده بیش از ۱۰۰۰ کاراکتر است"
    return None


def _validate_seo_title(value: str) -> str | None:
    if len(value) > 200:
        return "عنوان سئو بیش از ۲۰۰ کاراکتر است"
    return None


def _validate_seo_description(value: str) -> str | None:
    if len(value) > 500:
        return "توضیح سئو بیش از ۵۰۰ کاراکتر است"
    return None


def _validate_taxonomy_slugs(value: str) -> str | None:
    for slug in _split_slugs(value):
        if not is_valid_slug(slug):
            return f"نامک «{slug}» معتبر نیست (فقط حروف، اعداد و خط تیره)"
    return None


def _split_slugs(raw: str) -> list[str]:
    """Split a comma-separated slug list, preserving order, dropping blanks."""
    seen: set[str] = set()
    out: list[str] = []
    for part in str(raw).split(","):
        slug = part.strip()
        if slug and slug not in seen:
            seen.add(slug)
            out.append(slug)
    return out


BLOG_POST_COLUMNS: tuple[ColumnSpec, ...] = (
    ColumnSpec(
        key="title",
        label="عنوان مطلب",
        required=True,
        type="string",
        aliases=("عنوان", "name", "post_title"),
        extra_validator=_validate_title,
    ),
    ColumnSpec(
        key="slug",
        label="نامک",
        required=True,
        type="string",
        aliases=("نامک مطلب", "post_slug"),
        extra_validator=_validate_slug,
    ),
    ColumnSpec(
        key="body",
        label="متن (HTML)",
        required=True,
        type="string",
        aliases=("متن", "محتوا", "content", "body_html", "post_content"),
    ),
    ColumnSpec(
        key="excerpt",
        label="چکیده",
        required=False,
        type="string",
        aliases=("چکیده مطلب", "summary"),
        extra_validator=_validate_excerpt,
    ),
    ColumnSpec(
        key="status",
        label="وضعیت",
        required=False,
        type="string",
        aliases=("وضعیت انتشار", "post_status"),
        extra_validator=_validate_status,
    ),
    ColumnSpec(
        key="locale",
        label="زبان",
        required=False,
        type="string",
        aliases=("زبان محتوا", "lang", "language"),
        extra_validator=_validate_locale,
    ),
    ColumnSpec(
        key="category_slugs",
        label="دسته‌بندی‌ها",
        required=False,
        type="string",
        aliases=("دسته", "دسته‌بندی", "دسته‌بندی‌ها", "category", "categories"),
        extra_validator=_validate_taxonomy_slugs,
    ),
    ColumnSpec(
        key="tag_slugs",
        label="برچسب‌ها",
        required=False,
        type="string",
        aliases=("برچسب", "برچسب‌ها", "tags", "tag"),
        extra_validator=_validate_taxonomy_slugs,
    ),
    ColumnSpec(
        key="seo_title",
        label="عنوان سئو",
        required=False,
        type="string",
        aliases=("عنوان سئو مطلب", "meta_title"),
        extra_validator=_validate_seo_title,
    ),
    ColumnSpec(
        key="seo_description",
        label="توضیح سئو",
        required=False,
        type="string",
        aliases=("توضیحات سئو", "meta_description"),
        extra_validator=_validate_seo_description,
    ),
)


# ---------------------------------------------------------------------------
# Taxonomy + meta resolution helpers
# ---------------------------------------------------------------------------


async def _get_or_create_category(db: Any, slug: str) -> BlogCategory:
    found = (
        await db.execute(select(BlogCategory).where(BlogCategory.slug == slug))
    ).scalar_one_or_none()
    if found is not None:
        return found
    category = BlogCategory(name=slug, slug=slug)
    db.add(category)
    await db.flush()
    return category


async def _get_or_create_tag(db: Any, slug: str) -> BlogTag:
    found = (
        await db.execute(select(BlogTag).where(BlogTag.slug == slug))
    ).scalar_one_or_none()
    if found is not None:
        return found
    tag = BlogTag(name=slug, slug=slug)
    db.add(tag)
    await db.flush()
    return tag


async def _replace_tags(db: Any, post: BlogPost, raw: str) -> None:
    """Point the post at exactly the listed tags (order-preserving dedupe).

    Existing links are looked up explicitly (not through the lazy
    ``post_tags`` relationship — safe under asyncio) and flushed before the
    new links are added so the (post_id, tag_id) unique constraint never sees
    a delete+insert of the same pair inside one flush.
    """
    existing = (
        await db.execute(select(BlogPostTag).where(BlogPostTag.post_id == post.id))
    ).scalars().all()
    for link in existing:
        await db.delete(link)
    await db.flush()
    for slug in _split_slugs(raw):
        tag = await _get_or_create_tag(db, slug)
        db.add(BlogPostTag(post_id=post.id, tag_id=tag.id))
    await db.flush()


async def _upsert_seo_meta(db: Any, post: BlogPost, row: dict[str, Any]) -> None:
    """Persist seo_title/seo_description as BlogPostMeta rows (wp_postmeta)."""
    for key in SEO_META_KEYS:
        if key not in row:
            continue
        existing = (
            await db.execute(
                select(BlogPostMeta).where(
                    BlogPostMeta.post_id == post.id,
                    BlogPostMeta.meta_key == key,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            existing.meta_value = row[key]
        else:
            db.add(BlogPostMeta(post_id=post.id, meta_key=key, meta_value=row[key]))


async def _fallback_author_id(db: Any) -> Any:
    """First superuser id — the import-path stand-in author of last resort."""
    return (
        await db.execute(select(User.id).where(User.is_superuser == True).limit(1))  # noqa: E712
    ).scalars().first()


def _parse_status(value: Any) -> BlogPostStatus:
    return BlogPostStatus(str(value).strip().lower())


# ---------------------------------------------------------------------------
# Upsert (idempotent by slug)
# ---------------------------------------------------------------------------


async def upsert_blog_post_row(
    db: Any, row: dict[str, Any], *, created_by: Any = None
) -> str:
    """Create or update a blog post matched by slug.

    Returns ``"created"`` or ``"updated"``. Per-row savepoints are the
    caller's responsibility (the pipeline wraps each row in
    ``db.begin_nested()`` so one bad row cannot poison the batch).
    """
    slug = str(row["slug"]).strip()
    post = (
        await db.execute(select(BlogPost).where(BlogPost.slug == slug))
    ).scalar_one_or_none()

    status = _parse_status(row["status"]) if row.get("status") else None
    category = None
    category_slugs = _split_slugs(row["category_slugs"]) if row.get("category_slugs") else []
    if category_slugs:
        for category_slug in category_slugs:
            await _get_or_create_category(db, category_slug)
        # The schema has a single primary category; the first slug listed wins.
        category = await _get_or_create_category(db, category_slugs[0])

    if post is not None:
        post.title = row["title"]
        post.content = row["body"]
        if row.get("excerpt") is not None:
            post.excerpt = row["excerpt"]
        if status is not None:
            post.status = status
            if status == BlogPostStatus.PUBLISHED and post.published_at is None:
                post.published_at = datetime.now(UTC)
        if row.get("locale"):
            post.locale = row["locale"]
        if category is not None:
            post.category_id = category.id
        await _upsert_seo_meta(db, post, row)
        if row.get("tag_slugs"):
            await _replace_tags(db, post, str(row["tag_slugs"]))
        return "updated"

    author_id = created_by or await _fallback_author_id(db)
    if author_id is None:
        raise ValidationError(
            "برای مطلب جدید نویسنده لازم است (کاربر واردکننده شناسایی نشد)"
        )
    post = BlogPost(
        author_id=author_id,
        title=row["title"],
        slug=slug,
        content=row["body"],
        excerpt=row.get("excerpt"),
        status=status or BlogPostStatus.DRAFT,
        published_at=datetime.now(UTC) if status == BlogPostStatus.PUBLISHED else None,
        locale=row.get("locale") or "fa",
        category_id=category.id if category is not None else None,
    )
    db.add(post)
    await db.flush()
    await _upsert_seo_meta(db, post, row)
    if row.get("tag_slugs"):
        await _replace_tags(db, post, str(row["tag_slugs"]))
    return "created"


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


async def export_blog_post_rows(
    db: Any, filters: dict[str, Any]
) -> AsyncIterator[dict[str, Any]]:
    """Yield one export row per post with category/tag slugs + SEO resolved."""
    stmt = select(BlogPost).order_by(BlogPost.created_at.desc())
    if filters.get("status"):
        stmt = stmt.where(BlogPost.status == _parse_status(filters["status"]))

    posts = (await db.execute(stmt)).scalars().all()
    for post in posts:
        category = None
        if post.category_id is not None:
            category = (
                await db.execute(
                    select(BlogCategory).where(BlogCategory.id == post.category_id)
                )
            ).scalar_one_or_none()
        tags: list[str] = []
        links = (
            await db.execute(
                select(BlogPostTag).where(BlogPostTag.post_id == post.id)
            )
        ).scalars().all()
        for link in links:
            tag = (
                await db.execute(select(BlogTag).where(BlogTag.id == link.tag_id))
            ).scalar_one_or_none()
            if tag is not None:
                tags.append(tag.slug)
        meta_rows = (
            await db.execute(
                select(BlogPostMeta).where(BlogPostMeta.post_id == post.id)
            )
        ).scalars().all()
        meta_map = {m.meta_key: (m.meta_value or "") for m in meta_rows}

        yield {
            "id": str(post.id),
            "title": post.title,
            "slug": post.slug,
            "excerpt": post.excerpt or "",
            "body": post.content,
            "status": post.status.value,
            "locale": post.locale,
            "category_slugs": category.slug if category is not None else "",
            "tag_slugs": ",".join(tags),
            "seo_title": meta_map.get("seo_title", ""),
            "seo_description": meta_map.get("seo_description", ""),
            "created_at": post.created_at.isoformat() if post.created_at else "",
        }


register_adapter(
    EntityAdapter(
        entity_type="blog_post",
        label="مطالب وبلاگ",
        columns=BLOG_POST_COLUMNS,
        upsert_row=upsert_blog_post_row,
        export_rows=export_blog_post_rows,
        business_key="slug",
        upsert_accepts_created_by=True,
    )
)
