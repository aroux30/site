"""CMS page entity adapter for the generic import/export framework.

Import upserts a ``CmsPage`` matched by slug (``cms_pages.slug`` is globally
unique). ``parent_slug`` resolves to ``parent_id``: an unknown slug rejects
the row, a slug matching several rows is reported as ambiguous, and a parent
that resolves to the page itself (or one of its ancestors) is rejected as a
cycle — the same invariants the hierarchical page tree relies on.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import select

from app.core.exceptions.handlers import ValidationError
from app.modules.content.domain.models import CmsPage, PageStatus
from app.modules.dataexchange.application.adapters import (
    ColumnSpec,
    EntityAdapter,
    is_valid_slug,
    register_adapter,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

#: Status values actually stored in ``cms_pages.status`` (native_enum=False).
_ALLOWED_STATUSES = {s.value for s in PageStatus}
#: Guard for ancestor-walk cycle detection (page trees are shallow).
_MAX_TREE_DEPTH = 32


# ---------------------------------------------------------------------------
# Column-level validators (return a Persian error message or None)
# ---------------------------------------------------------------------------


def _validate_title(value: str) -> str | None:
    if len(value) > 300:
        return "عنوان برگه بیش از ۳۰۰ کاراکتر است"
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


def _validate_seo_title(value: str) -> str | None:
    if len(value) > 200:
        return "عنوان سئو بیش از ۲۰۰ کاراکتر است"
    return None


def _validate_seo_description(value: str) -> str | None:
    if len(value) > 500:
        return "توضیح سئو بیش از ۵۰۰ کاراکتر است"
    return None


def _validate_page_template(value: str) -> str | None:
    if len(value) > 100:
        return "نام قالب برگه بیش از ۱۰۰ کاراکتر است"
    return None


CMS_PAGE_COLUMNS: tuple[ColumnSpec, ...] = (
    ColumnSpec(
        key="title",
        label="عنوان برگه",
        required=True,
        type="string",
        aliases=("عنوان", "page_title"),
    ),
    ColumnSpec(
        key="slug",
        label="نامک",
        required=True,
        type="string",
        aliases=("نامک برگه", "page_slug"),
        extra_validator=_validate_slug,
    ),
    ColumnSpec(
        key="body",
        label="محتوا (HTML)",
        required=True,
        type="string",
        aliases=("محتوا", "متن", "body_html", "content", "page_body"),
    ),
    ColumnSpec(
        key="parent_slug",
        label="نامک والد",
        required=False,
        type="string",
        aliases=("برگه والد", "والد", "parent", "parent_page"),
        extra_validator=_validate_slug,
    ),
    ColumnSpec(
        key="status",
        label="وضعیت",
        required=False,
        type="string",
        aliases=("وضعیت انتشار", "page_status"),
        extra_validator=_validate_status,
    ),
    ColumnSpec(
        key="seo_title",
        label="عنوان سئو",
        required=False,
        type="string",
        aliases=("عنوان سئو برگه", "meta_title"),
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
    ColumnSpec(
        key="page_template",
        label="قالب برگه",
        required=False,
        type="string",
        aliases=("قالب", "template"),
        extra_validator=_validate_page_template,
    ),
)


# ---------------------------------------------------------------------------
# Parent resolution
# ---------------------------------------------------------------------------


async def _resolve_parent(
    db: Any, parent_slug: str, *, exclude_id: Any = None
) -> CmsPage:
    """Resolve ``parent_slug`` to a page, rejecting unknown/ambiguous/cyclic."""
    matches = (
        await db.execute(select(CmsPage).where(CmsPage.slug == parent_slug))
    ).scalars().all()
    if not matches:
        raise ValidationError(f"برگه والد با نامک «{parent_slug}» یافت نشد")
    if len(matches) > 1:
        raise ValidationError(
            f"نامک والد «{parent_slug}» مبهم است ({len(matches)} برگه با این نامک)"
        )
    parent = matches[0]
    if exclude_id is not None and parent.id == exclude_id:
        raise ValidationError("برگه نمی‌تواند والد خودش باشد")

    # Walk up the ancestor chain: making a descendant the parent would create
    # a cycle the page tree can never render.
    ancestor_id = parent.parent_id
    visited = 0
    while ancestor_id is not None and visited < _MAX_TREE_DEPTH:
        if exclude_id is not None and ancestor_id == exclude_id:
            raise ValidationError(
                "برگه نمی‌تواند والد یکی از زیرشاخه‌های خودش باشد (حلقه)"
            )
        ancestor = await db.get(CmsPage, ancestor_id)
        if ancestor is None:
            break
        ancestor_id = ancestor.parent_id
        visited += 1
    return parent


def _parse_status(value: Any) -> PageStatus:
    return PageStatus(str(value).strip().lower())


# ---------------------------------------------------------------------------
# Upsert (idempotent by slug)
# ---------------------------------------------------------------------------


async def upsert_cms_page_row(db: Any, row: dict[str, Any]) -> str:
    """Create or update a CMS page matched by slug.

    Returns ``"created"`` or ``"updated"``. Per-row savepoints are the
    caller's responsibility (the pipeline wraps each row in
    ``db.begin_nested()`` so one bad row cannot poison the batch).
    """
    slug = str(row["slug"]).strip()
    page = (
        await db.execute(select(CmsPage).where(CmsPage.slug == slug))
    ).scalar_one_or_none()

    parent = None
    if row.get("parent_slug"):
        parent = await _resolve_parent(
            db, str(row["parent_slug"]), exclude_id=page.id if page is not None else None
        )

    status = _parse_status(row["status"]) if row.get("status") else None

    if page is not None:
        page.title = row["title"]
        page.body_html = row["body"]
        if status is not None:
            page.status = status
            if status == PageStatus.PUBLISHED and page.published_at is None:
                page.published_at = datetime.now(UTC)
        if parent is not None:
            page.parent_id = parent.id
        if row.get("seo_title") is not None:
            page.seo_title = row["seo_title"]
        if row.get("seo_description") is not None:
            page.seo_description = row["seo_description"]
        if row.get("page_template"):
            page.page_template = row["page_template"]
        return "updated"

    page = CmsPage(
        title=row["title"],
        slug=slug,
        body_html=row["body"],
        status=status or PageStatus.DRAFT,
        published_at=datetime.now(UTC) if status == PageStatus.PUBLISHED else None,
        seo_title=row.get("seo_title"),
        seo_description=row.get("seo_description"),
        parent_id=parent.id if parent is not None else None,
        page_template=row.get("page_template"),
    )
    db.add(page)
    await db.flush()
    return "created"


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


async def export_cms_page_rows(
    db: Any, filters: dict[str, Any]
) -> AsyncIterator[dict[str, Any]]:
    """Yield one export row per page with the parent's slug resolved."""
    stmt = select(CmsPage).order_by(CmsPage.created_at.desc())
    if filters.get("status"):
        stmt = stmt.where(CmsPage.status == _parse_status(filters["status"]))

    pages = (await db.execute(stmt)).scalars().all()
    for page in pages:
        parent_slug = ""
        if page.parent_id is not None:
            parent = await db.get(CmsPage, page.parent_id)
            if parent is not None:
                parent_slug = parent.slug
        yield {
            "id": str(page.id),
            "title": page.title,
            "slug": page.slug,
            "body": page.body_html,
            "parent_slug": parent_slug,
            "status": page.status.value,
            "seo_title": page.seo_title or "",
            "seo_description": page.seo_description or "",
            "page_template": page.page_template or "",
            "created_at": page.created_at.isoformat() if page.created_at else "",
        }


register_adapter(
    EntityAdapter(
        entity_type="cms_page",
        label="برگه‌های سایت",
        columns=CMS_PAGE_COLUMNS,
        upsert_row=upsert_cms_page_row,
        export_rows=export_cms_page_rows,
        business_key="slug",
    )
)
