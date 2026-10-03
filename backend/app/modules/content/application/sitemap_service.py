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
    from app.modules.catalog.domain.models import (
        Product,
        ProductImage,
        ProductStatus,
    )

    stmt = select(Product).where(
        Product.status == ProductStatus.ACTIVE,
        Product.is_active.is_(True),
    )
    products = (await db.execute(stmt.order_by(Product.slug))).scalars().all()

    # The image lives in `product_images`, not on the product row — `Product` has
    # no image column, so the first version raised AttributeError and the whole
    # product section was skipped. One query for the primaries, keyed by product,
    # rather than a correlated subquery per product: a lateral subquery with a
    # LIMIT is the kind of thing that renders fine and fails at execution time.
    images: dict[str, str] = {}
    if products:
        img_stmt = (
            select(ProductImage.product_id, ProductImage.url)
            .where(ProductImage.is_primary.is_(True))
            .order_by(ProductImage.position)
        )
        for pid, url in (await db.execute(img_stmt)).all():
            images.setdefault(str(pid), url)

    return [
        SitemapSectionRow(
            slug=r.slug,
            updated_at=r.updated_at,
            changefreq="daily",
            priority=0.7,
            # A product's image is the result a search engine shows. For a
            # storefront this is the single highest-value thing to put in a
            # sitemap, and it was absent — the section carried slugs only.
            image_url=images.get(str(r.id)),
        )
        for r in products
    ]


async def _collect_authors(db: AsyncSession) -> list[SitemapSectionRow]:
    """Author archives that have at least one published post.

    An author with nothing published has no archive worth crawling, and an
    empty archive URL in a sitemap is a 404 a crawler will keep retrying.
    """
    from sqlalchemy import func

    from app.modules.blog.domain.models import BlogPost, BlogPostStatus
    from app.modules.users.domain.models import User

    # The slug lives on the users row, not on user_profiles — an earlier
    # version joined the profile table and every query failed with
    # UndefinedColumnError, which then aborted the transaction and made the
    # sitemap look empty rather than broken.
    # Group by the slug, not the id: `User` has a relationship that makes
    # SQLAlchemy join the profile table, and PostgreSQL then requires every
    # selected column in the GROUP BY. Selecting `User` and grouping by its id
    # fails with "column user_profiles_1.id must appear in the GROUP BY", and
    # the section loop swallows it — so the archive section was simply empty.
    stmt = (
        select(User.author_slug, func.count(BlogPost.id))
        .join(BlogPost, BlogPost.author_id == User.id)
        .where(
            BlogPost.status == BlogPostStatus.PUBLISHED,
            BlogPost.deleted_at.is_(None),
            User.author_slug.is_not(None),
        )
        .group_by(User.author_slug)
        .having(func.count(BlogPost.id) > 0)
        .order_by(User.author_slug)
    )
    rows = (await db.execute(stmt)).all()
    return [
        SitemapSectionRow(
            loc=f"/blog/authors/{slug}",
            lastmod=None,
            changefreq="weekly",
            priority=0.5,
        )
        for slug, _count in rows
    ]


async def _collect_date_archives(db: AsyncSession) -> list[SitemapSectionRow]:
    """Year and month archives that actually exist.

    Advertising every possible year/month would be an unbounded list of 404s,
    so this reads the distinct values the published posts actually occupy.
    """
    from sqlalchemy import func

    from app.modules.blog.domain.models import BlogPost, BlogPostStatus

    stmt = (
        select(
            func.extract("year", BlogPost.published_at).label("y"),
            func.extract("month", BlogPost.published_at).label("m"),
        )
        .where(
            BlogPost.status == BlogPostStatus.PUBLISHED,
            BlogPost.deleted_at.is_(None),
            BlogPost.published_at.is_not(None),
        )
        .distinct()
        .order_by("y", "m")
    )
    rows = (await db.execute(stmt)).all()

    out: list[SitemapSectionRow] = []
    seen_years: set[int] = set()
    for year, month in rows:
        y, m = int(year), int(month)
        if y not in seen_years:
            seen_years.add(y)
            out.append(
                SitemapSectionRow(
                    loc=f"/archive/{y}",
                    lastmod=None,
                    changefreq="monthly",
                    priority=0.4,
                )
            )
        out.append(
            SitemapSectionRow(
                loc=f"/archive/{y}/{m}",
                lastmod=None,
                changefreq="monthly",
                priority=0.3,
            )
        )
    return out


# section key -> (collector, changefreq, priority) for the XML fragment rows
_SECTIONS: tuple[tuple[str, Any, str, str], ...] = (
    ("blog_categories", _collect_blog_categories, "weekly", "0.6"),
    ("blog_tags", _collect_blog_tags, "weekly", "0.5"),
    ("products", _collect_products, "daily", "0.7"),
    ("blog_authors", _collect_authors, "weekly", "0.5"),
    ("blog_date_archives", _collect_date_archives, "monthly", "0.4"),
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
        blog_authors=section_rows["blog_authors"],
        blog_date_archives=section_rows["blog_date_archives"],
    )
    return SitemapEntriesResponse(
        items=items,
        total=len(items),
        blog_categories=section_rows["blog_categories"],
        blog_tags=section_rows["blog_tags"],
        products=section_rows["products"],
        blog_authors=section_rows["blog_authors"],
        blog_date_archives=section_rows["blog_date_archives"],
        xml_fragment=xml_fragment,
    )
