"""Product-category adapter for the generic import/export framework.

Why this entity exists: the product adapter REJECTS a new product whose
category cannot be resolved (``product_adapter.py``), so migrating a catalog
from another platform starts here — categories first, then products. It is
also the day-to-day bulk target: renaming, re-parenting and re-ordering a
category tree is exactly the work a store owner does in a spreadsheet.

The materialized ``path``/``depth`` columns are maintained here the same way
``CategoryService`` maintains them (parent path + slug, parent depth + 1), so
an imported tree behaves identically to one built through the admin UI.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import select

from app.core.exceptions.handlers import ValidationError
from app.modules.catalog.domain.models import Category
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
        return "نام دسته‌بندی بیش از ۲۰۰ کاراکتر است"
    return None


PRODUCT_CATEGORY_COLUMNS: tuple[ColumnSpec, ...] = (
    ColumnSpec(
        key="slug",
        label="نامک",
        required=True,
        type="string",
        aliases=("نامک دسته", "slug", "category_slug"),
    ),
    ColumnSpec(
        key="name",
        label="نام دسته‌بندی",
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
        key="image_url",
        label="نشانی تصویر",
        required=False,
        type="string",
        aliases=("تصویر", "image"),
    ),
    ColumnSpec(
        key="position",
        label="ترتیب",
        required=False,
        type="integer",
        aliases=("ردیف", "order", "sort"),
    ),
    ColumnSpec(
        key="is_active",
        label="فعال",
        required=False,
        type="boolean",
        aliases=("وضعیت فعال", "active", "enabled"),
    ),
    ColumnSpec(
        key="seo_title",
        label="عنوان سئو",
        required=False,
        type="string",
        aliases=("عنوان متا", "meta_title"),
    ),
    ColumnSpec(
        key="seo_description",
        label="توضیح سئو",
        required=False,
        type="string",
        aliases=("توضیحات متا", "meta_description"),
    ),
)


async def _resolve_parent(db: Any, parent_slug: str, *, exclude_id: Any = None) -> Category:
    matches = (
        await db.execute(select(Category).where(Category.slug == parent_slug))
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
        ancestor = await db.get(Category, ancestor_id)
        if ancestor is None:
            break
        ancestor_id = ancestor.parent_id
        visited += 1
    return parent


async def upsert_product_category_row(db: Any, row: dict[str, Any]) -> str:
    """Create or update a product category matched by slug.

    ``path``/``depth`` recompute from the resolved parent, mirroring
    ``CategoryService.create`` — an imported subtree must behave like one
    built in the admin UI, because the storefront filters rely on ``path``.
    """
    slug = str(row["slug"]).strip()
    category = (
        await db.execute(select(Category).where(Category.slug == slug))
    ).scalar_one_or_none()

    parent: Category | None = None
    if row.get("parent_slug"):
        parent = await _resolve_parent(
            db, str(row["parent_slug"]), exclude_id=category.id if category else None
        )

    path = f"{parent.path}/{slug}" if parent and parent.path else slug
    depth = (parent.depth + 1) if parent else 0

    if category is not None:
        category.name = row["name"]
        if parent is not None:
            category.parent_id = parent.id
        category.path = path
        category.depth = depth
        if row.get("description") is not None:
            category.description = row["description"]
        if row.get("image_url") is not None:
            category.image_url = row["image_url"]
        if row.get("position") is not None:
            category.position = row["position"]
        if "is_active" in row:
            category.is_active = row["is_active"]
        if row.get("seo_title") is not None:
            category.seo_title = row["seo_title"]
        if row.get("seo_description") is not None:
            category.seo_description = row["seo_description"]
        return "updated"

    db.add(
        Category(
            name=row["name"],
            slug=slug,
            parent_id=parent.id if parent is not None else None,
            description=row.get("description"),
            image_url=row.get("image_url"),
            path=path,
            depth=depth,
            position=row.get("position") or 0,
            is_active=row.get("is_active", True),
            seo_title=row.get("seo_title"),
            seo_description=row.get("seo_description"),
        )
    )
    await db.flush()
    return "created"


async def export_product_category_rows(
    db: Any, filters: dict[str, Any]
) -> "AsyncIterator[dict[str, Any]]":
    """Yield one export row per category with the parent's slug resolved."""
    parent_slugs: dict[Any, str] = {}
    rows = (await db.execute(select(Category).order_by(Category.path))).scalars().all()
    parent_ids = {c.parent_id for c in rows if c.parent_id is not None}
    if parent_ids:
        parents = (
            await db.execute(select(Category).where(Category.id.in_(parent_ids)))
        ).scalars().all()
        parent_slugs = {p.id: p.slug for p in parents}

    for c in rows:
        yield {
            "id": str(c.id),
            "slug": c.slug,
            "name": c.name,
            "parent_slug": parent_slugs.get(c.parent_id, ""),
            "description": c.description or "",
            "image_url": c.image_url or "",
            "position": c.position,
            "is_active": c.is_active,
            "seo_title": c.seo_title or "",
            "seo_description": c.seo_description or "",
            "created_at": c.created_at.isoformat() if c.created_at else "",
        }


register_adapter(
    EntityAdapter(
        entity_type="product_category",
        label="دسته‌بندی محصولات",
        columns=PRODUCT_CATEGORY_COLUMNS,
        upsert_row=upsert_product_category_row,
        export_rows=export_product_category_rows,
        business_key="slug",
    )
)
