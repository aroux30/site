"""Sitemap completeness service: one payload with every crawlable address.

The storefront's ``app/sitemap.ts`` used to assemble the sitemap from three
independent lookups (CMS pages, blog categories/tags via the blog API, and
nothing at all for products). This service gathers all sections server-side —
read-only imports of the blog and catalog models — so one public fetch covers
everything, and the XML ``<url>`` fragment is rendered by the same
:func:`cms_page_service.render_sitemap_entries` the sitemap historically used.

Fail-open like the rest of the platform: if the blog or catalog section is
unavailable (module missing, table absent, query error), that section is
skipped with a logged warning instead of failing the whole sitemap.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import select

from app.modules.content.application import cms_page_service
from app.modules.content.schemas.content import (
    PublicPageSummary,
    SitemapEntriesResponse,
    SitemapSectionRow,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# Same fallback the RSS feed uses when the ``home`` site option is unset.
_DEFAULT_BASE_URL = "https://example.com"


def _section_row(row: Any, *, changefreq: str, priority: float) -> SitemapSectionRow:
    return SitemapSectionRow(
        slug=row.slug,
        updated_at=getattr(row, "updated_at", None) or getattr(row, "created_at", None),
        changefreq=changefreq,
        priority=priority,
    )


async def _collect_blog_categories(db: AsyncSession) -> list[SitemapSectionRow]:
    """Blog categories (no publish state of their own — all are listed)."""
    from app.modules.blog.domain.models import BlogCategory

    rows = (await db.execute(select(BlogCategory).order_by(BlogCategory.slug))).scalars().all()
    return [_section_row(r, changefreq="weekly", priority=0.6) for r in rows]


async def _collect_blog_tags(db: AsyncSession) -> list[SitemapSectionRow]:
    """Blog tags (flat taxonomy — all are listed)."""
    from app.modules.blog.domain.models import BlogTag

    rows = (await db.execute(select(BlogTag).order_by(BlogTag.slug))).scalars().all()
    return [_section_row(r, changefreq="weekly", priority=0.5) for r in rows]


async def _collect_products(db: AsyncSession) -> list[SitemapSectionRow]:
    """Active catalog products (draft/archived are never advertised)."""
    from app.modules.catalog.domain.models import Product, ProductStatus

    stmt = select(Product).where(
        Product.status == ProductStatus.ACTIVE,
        Product.is_active.is_(True),
    )
    rows = (await db.execute(stmt.order_by(Product.slug))).scalars().all()
    return [_section_row(r, changefreq="daily", priority=0.7) for r in rows]


# section key -> (collector, changefreq, priority) for the XML fragment rows
_SECTIONS: tuple[tuple[str, Any, str, str], ...] = (
    ("blog_categories", _collect_blog_categories, "weekly", "0.6"),
    ("blog_tags", _collect_blog_tags, "weekly", "0.5"),
    ("products", _collect_products, "daily", "0.7"),
)


async def _resolve_base_url(db: AsyncSession) -> str:
    """Site home URL from the ``home`` site option (RSS feed parity)."""
    try:
        from app.modules.settings.application.site_options_service import SiteOptionsService

        home = await SiteOptionsService.get(db, "home")
        if home:
            return home
    except Exception:
        logger.warning("sitemap_home_option_unresolved")
    return _DEFAULT_BASE_URL


async def build_sitemap_payload(db: AsyncSession) -> SitemapEntriesResponse:
    """Gather every crawlable section into the extended public payload.

    ``items``/``total`` carry exactly the older ``GET /content/pages`` shape
    (minimal published-page rows), so existing consumers keep working; the
    blog-category, blog-tag, and product sections and the rendered XML
    fragment are additive keys. Blog posts stay on the blog API's paginated
    feed the storefront already consumes.
    """
    pages = await cms_page_service.list_published_page_summaries(db)
    items = [PublicPageSummary.model_validate(p) for p in pages]

    section_rows: dict[str, list[Any]] = {}
    for name, collector, _changefreq, _priority in _SECTIONS:
        try:
            section_rows[name] = list(await collector(db))
        except Exception:
            logger.warning("sitemap_section_skipped", section=name)
            section_rows[name] = []

    xml_fragment = cms_page_service.render_sitemap_entries(
        pages,
        base_url=await _resolve_base_url(db),
        blog_categories=section_rows["blog_categories"],
        blog_tags=section_rows["blog_tags"],
        products=section_rows["products"],
    )
    return SitemapEntriesResponse(
        items=items,
        total=len(items),
        blog_categories=section_rows["blog_categories"],
        blog_tags=section_rows["blog_tags"],
        products=section_rows["products"],
        xml_fragment=xml_fragment,
    )
