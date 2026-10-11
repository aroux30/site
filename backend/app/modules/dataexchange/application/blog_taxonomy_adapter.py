"""Blog-category and blog-tag adapters for the import/export framework.

The blog_post adapter already get-or-creates categories/tags from a post's
`category_slugs`/`tag_slugs` — but with ``name = slug``, because a post CSV
has no room for a category's real name, description or parent. A WXR import
hands over the real names. These two adapters carry the full taxonomy:
rename, describe, re-parent, and export it back.

Two entities in one module because they are one concern (taxonomy) with two
flat shapes; the category one has the parent machinery, the tag one does not.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import select

from app.core.exceptions.handlers import ValidationError
from app.modules.blog.domain.models import BlogCategory, BlogTag
from app.modules.dataexchange.application.adapters import (
    ColumnSpec,
    EntityAdapter,
    register_adapter,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


def _validate_name(value: str) -> str | None:
    if len(value) > 200:
        return "نام بیش از ۲۰۰ کاراکتر است"
    return None


BLOG_CATEGORY_COLUMNS: tuple[ColumnSpec, ...] = (
    ColumnSpec(
        key="slug",
        label="نامک",
        required=True,
        type="string",
        aliases=("نامک دسته", "slug", "category_slug"),
    ),
    ColumnSpec(
        key="name",
        label="نام دسته",
        required=True,
        type="string",
        aliases=("نام", "عنوان", "title"),
        extra_validator=_validate_name,
    ),
    ColumnSpec(
        key="parent_slug",
        label="نامک والد",
        required=False,
        type="string",
        aliases=("والد", "دسته والد", "parent"),
    ),
    ColumnSpec(
        key="description",
        label="توضیحات",
        required=False,
        type="string",
        aliases=("توضیح", "شرح", "desc"),
    ),
    ColumnSpec(
        key="position",
        label="ترتیب",
        required=False,
        type="integer",
        aliases=("ردیف", "order", "sort"),
    ),
)

BLOG_TAG_COLUMNS: tuple[ColumnSpec, ...] = (
    ColumnSpec(
        key="slug",
        label="نامک",
        required=True,
        type="string",
        aliases=("نامک برچسب", "slug", "tag_slug"),
    ),
    ColumnSpec(
        key="name",
        label="نام برچسب",
        required=True,
        type="string",
        aliases=("نام", "عنوان", "title"),
        extra_validator=_validate_name,
    ),
    ColumnSpec(
        key="description",
        label="توضیحات",
        required=False,
        type="string",
        aliases=("توضیح", "شرح", "desc"),
    ),
)


async def _resolve_blog_parent(
    db: Any, parent_slug: str, *, exclude_id: Any = None
) -> BlogCategory:
    matches = (
        await db.execute(select(BlogCategory).where(BlogCategory.slug == parent_slug))
    ).scalars().all()
    if not matches:
        raise ValidationError(f"دستهٔ والد با نامک «{parent_slug}» یافت نشد")
    if len(matches) > 1:
        raise ValidationError(f"نامک والد «{parent_slug}» مبهم است")
    parent = matches[0]
    if exclude_id is not None and parent.id == exclude_id:
        raise ValidationError("دسته نمی‌تواند والد خودش باشد")
    ancestor_id = parent.parent_id
    visited = 0
    while ancestor_id is not None and visited < 100:
        if exclude_id is not None and ancestor_id == exclude_id:
            raise ValidationError("دسته نمی‌تواند والد یکی از زیرشاخه‌های خودش باشد (حلقه)")
        ancestor = await db.get(BlogCategory, ancestor_id)
        if ancestor is None:
            break
        ancestor_id = ancestor.parent_id
        visited += 1
    return parent


async def upsert_blog_category_row(db: Any, row: dict[str, Any]) -> str:
    """Create or update a blog category matched by slug."""
    slug = str(row["slug"]).strip()
    category = (
        await db.execute(select(BlogCategory).where(BlogCategory.slug == slug))
    ).scalar_one_or_none()

    parent: BlogCategory | None = None
    if row.get("parent_slug"):
        parent = await _resolve_blog_parent(
            db, str(row["parent_slug"]), exclude_id=category.id if category else None
        )

    if category is not None:
        category.name = row["name"]
        if parent is not None:
            category.parent_id = parent.id
        if row.get("description") is not None:
            category.description = row["description"]
        if row.get("position") is not None:
            category.position = row["position"]
        return "updated"

    db.add(
        BlogCategory(
            name=row["name"],
            slug=slug,
            parent_id=parent.id if parent is not None else None,
            description=row.get("description"),
            position=row.get("position") or 0,
        )
    )
    await db.flush()
    return "created"


async def export_blog_category_rows(
    db: Any, filters: dict[str, Any]
) -> "AsyncIterator[dict[str, Any]]":
    """Yield one export row per blog category with the parent slug resolved."""
    rows = (
        await db.execute(select(BlogCategory).order_by(BlogCategory.position, BlogCategory.name))
    ).scalars().all()
    parent_ids = {c.parent_id for c in rows if c.parent_id is not None}
    parent_slugs: dict[Any, str] = {}
    if parent_ids:
        parents = (
            await db.execute(select(BlogCategory).where(BlogCategory.id.in_(parent_ids)))
        ).scalars().all()
        parent_slugs = {p.id: p.slug for p in parents}
    for c in rows:
        yield {
            "id": str(c.id),
            "slug": c.slug,
            "name": c.name,
            "parent_slug": parent_slugs.get(c.parent_id, ""),
            "description": c.description or "",
            "position": c.position,
            "created_at": c.created_at.isoformat() if c.created_at else "",
        }


async def upsert_blog_tag_row(db: Any, row: dict[str, Any]) -> str:
    """Create or update a blog tag matched by slug."""
    slug = str(row["slug"]).strip()
    tag = (
        await db.execute(select(BlogTag).where(BlogTag.slug == slug))
    ).scalar_one_or_none()

    if tag is not None:
        tag.name = row["name"]
        if row.get("description") is not None:
            tag.description = row["description"]
        return "updated"

    db.add(
        BlogTag(
            name=row["name"],
            slug=slug,
            description=row.get("description"),
        )
    )
    await db.flush()
    return "created"


async def export_blog_tag_rows(
    db: Any, filters: dict[str, Any]
) -> "AsyncIterator[dict[str, Any]]":
    """Yield one export row per blog tag."""
    rows = (await db.execute(select(BlogTag).order_by(BlogTag.name))).scalars().all()
    for t in rows:
        yield {
            "id": str(t.id),
            "slug": t.slug,
            "name": t.name,
            "description": t.description or "",
            "created_at": t.created_at.isoformat() if t.created_at else "",
        }


register_adapter(
    EntityAdapter(
        entity_type="blog_category",
        label="دسته‌های وبلاگ",
        columns=BLOG_CATEGORY_COLUMNS,
        upsert_row=upsert_blog_category_row,
        export_rows=export_blog_category_rows,
        business_key="slug",
    )
)

register_adapter(
    EntityAdapter(
        entity_type="blog_tag",
        label="برچسب‌های وبلاگ",
        columns=BLOG_TAG_COLUMNS,
        upsert_row=upsert_blog_tag_row,
        export_rows=export_blog_tag_rows,
        business_key="slug",
    )
)
