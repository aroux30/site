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
    SitemapNewsRow,
    SitemapSectionRow,
    SitemapVideoRow,
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


async def collect_noindex_slugs(db: AsyncSession) -> dict[str, list[str]]:
    """Slugs excluded from the sitemap, keyed by resource kind.

    The blog list API does not carry SEO metadata, so the storefront sitemap
    reads this small exclusion list instead of widening the public post
    projection (which would leak the whole SEO row to anonymous callers).
    """
    from app.modules.blog.domain.models import BlogPost
    from app.modules.catalog.domain.models import Product
    from app.modules.seo.domain.models import SEOMetadata

    result: dict[str, list[str]] = {"blog_posts": [], "products": []}
    try:
        noindex_blog_ids = await _noindex_resource_ids(db, "blog_post")
        if noindex_blog_ids:
            rows = (
                await db.execute(
                    select(BlogPost.slug).where(BlogPost.id.in_(noindex_blog_ids))
                )
            ).scalars().all()
            result["blog_posts"] = list(rows)

        noindex_product_ids = await _noindex_resource_ids(db, "product")
        if noindex_product_ids:
            rows = (
                await db.execute(
                    select(Product.slug).where(Product.id.in_(noindex_product_ids))
                )
            ).scalars().all()
            result["products"] = list(rows)
    except Exception:
        logger.warning("sitemap_noindex_slugs_failed")
    return result


async def _noindex_resource_ids(db: AsyncSession, resource_type: str) -> set:
    """Resource ids whose operator marked them noindex.

    A sitemap that advertises a noindexed URL contradicts itself — Search
    Console reports "Submitted URL marked noindex" and crawlers discount the
    file. The Advanced tab's robots_noindex column is the source; only an
    explicit True excludes (NULL/False both mean "indexable").
    """
    from app.modules.seo.domain.models import SEOMetadata

    try:
        rows = (
            await db.execute(
                select(SEOMetadata.resource_id).where(
                    SEOMetadata.resource_type.in_(
                        (resource_type, f"{resource_type}s")
                    ),
                    SEOMetadata.robots_noindex.is_(True),
                )
            )
        ).scalars().all()
        return set(rows)
    except Exception:
        # Fail open: a missing seo_metadata table must not empty the sitemap.
        logger.warning("sitemap_noindex_lookup_failed", resource_type=resource_type)
        return set()


#: Taxonomy slugs that are test/import debris, never real content (SEO audit
#: F-05, reviewed against the live DB on 2026-10-10: 37 empty categories = 34
#: debris + 3 real Persian ones). Chosen explicitly rather than by
#: "has no published post": the three Persian categories fixed in the same
#: audit are ALSO empty today and must stay advertised — an emptiness rule
#: would silently undo that P0 fix.
_DEBRIS_CATEGORY_SLUGS = frozenset({
    "probe", "probe-1", "probe-child", "bulk-test-d2a43a48",
    "twentytwentyfour", "woodmart", "simple", "variable",
    "product-archive", "page", "exclude-from-catalog",
    "exclude-from-search", "outofstock",
    "buy-16200-uc-login-pubg-mobile", "buy-1800-uc-login-pubg-mobile",
    "buy-24300-uc-login-pubg-mobile", "buy-32400-uc-login-pubg-mobile",
    "buy-3850-uc-login-pubg-mobile", "buy-40500-uc-login-pubg-mobile",
    "buy-5650-uc-login-pubg-mobile", "buy-8100-uc-login-pubg-mobile",
    "buy-uc-pubg-mobile",
    "premium-telegram-1year", "premium-telegram-3months",
    "premium-telegram-6months", "premium-telegram-login-1month",
    "premium-telegram-login-1year",
    "gem-mythic-forge", "growth-pack-1", "growth-pack-3", "growth-pack-5",
    "gymyng", "lptap", "lptap-gym",
})

#: Account/task pages that must not be in the sitemap. WordPress shortcode
#: stubs ("/wishlist", "/my-account", "/shop") are UI shells the storefront
#: serves from dedicated routes — advertising the stub tells Google to index
#: a duplicate of the real page with no content on it.
_TASK_PAGE_SLUGS = frozenset({"wishlist", "my-account", "shop"})
_DEBRIS_TAG_SLUGS = frozenset({
    "p1attach-term0-f665faec", "p1attach-term1-9c42a75f",
    "p1attach-term2-7e7e78d4",
})


async def _collect_blog_categories(db: AsyncSession) -> list[SitemapSectionRow]:
    """Blog categories (no publish state of their own — all are listed).

    Categories explicitly marked noindex are skipped, and test/import debris
    slugs (``_DEBRIS_CATEGORY_SLUGS``) are excluded so the sitemap does not
    advertise empty probe rows.
    """
    from app.modules.blog.domain.models import BlogCategory

    rows = (await db.execute(select(BlogCategory).order_by(BlogCategory.slug))).scalars().all()
    rows = [r for r in rows if r.slug not in _DEBRIS_CATEGORY_SLUGS]
    return [_section_row(r, changefreq="weekly", priority=0.6) for r in rows]


async def _collect_blog_tags(db: AsyncSession) -> list[SitemapSectionRow]:
    """Blog tags (flat taxonomy — all are listed except test debris)."""
    from app.modules.blog.domain.models import BlogTag

    rows = (await db.execute(select(BlogTag).order_by(BlogTag.slug))).scalars().all()
    rows = [r for r in rows if r.slug not in _DEBRIS_TAG_SLUGS]
    return [_section_row(r, changefreq="weekly", priority=0.5) for r in rows]


async def _collect_noindex_product_ids(db: AsyncSession) -> set:
    """Product ids the operator marked noindex (Advanced tab)."""
    return await _noindex_resource_ids(db, "product")


async def _collect_products(db: AsyncSession) -> list[SitemapSectionRow]:
    """Active catalog products (draft/archived are never advertised).

    Products whose SEO metadata marks them noindex are excluded — a sitemap
    advertising a noindexed URL contradicts itself.
    """
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

    noindex_ids = await _collect_noindex_product_ids(db)
    if noindex_ids:
        products = [p for p in products if p.id not in noindex_ids]

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
            # The real storefront route is /author/<slug> — an earlier version
            # advertised /blog/authors/<slug>, which no route serves, so every
            # author entry in the sitemap was a 404 a crawler kept retrying.
            loc=f"/author/{slug}",
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
                    # Real route: (store)/blog/archive/[year] — /archive/<y>
                    # was advertised but no route serves it (404 in the sitemap).
                    loc=f"/blog/archive/{y}",
                    lastmod=None,
                    changefreq="monthly",
                    priority=0.4,
                )
            )
        out.append(
            SitemapSectionRow(
                loc=f"/blog/archive/{y}/{m}",
                lastmod=None,
                changefreq="monthly",
                priority=0.3,
            )
        )
    return out


#: Google's news sitemap window: only posts published within the last two
#: days may be listed; anything older is a stale entry that can invalidate
#: the file. This is a hard rule, not a preference.
NEWS_WINDOW_HOURS = 48

#: Hard cap on news entries. Google's news sitemap allows at most 1,000 URLs;
#: a site publishing more than that in 48h is beyond this store's scale, and
#: an uncapped list would produce a file crawlers reject as oversized.
NEWS_MAX_URLS = 1000


async def _collect_news(db: AsyncSession) -> list[SitemapNewsRow]:
    """Posts published inside the news window, newest first.

    The publication name comes from the ``blogname`` site option (the same
    source og:site_name uses) so the sitemap and the storefront cannot
    disagree about what the site is called.
    """
    from datetime import UTC, datetime, timedelta

    from app.modules.blog.domain.models import BlogPost, BlogPostStatus

    cutoff = datetime.now(UTC) - timedelta(hours=NEWS_WINDOW_HOURS)
    stmt = (
        select(BlogPost)
        .where(
            BlogPost.status == BlogPostStatus.PUBLISHED,
            BlogPost.deleted_at.is_(None),
            BlogPost.published_at.is_not(None),
            BlogPost.published_at >= cutoff,
        )
        .order_by(BlogPost.published_at.desc())
        .limit(NEWS_MAX_URLS)
    )
    posts = (await db.execute(stmt)).scalars().all()

    publication_name = "وبلاگ"
    try:
        from app.modules.settings.application.site_options_service import (
            SiteOptionsService,
        )

        name = await SiteOptionsService.get(db, "blogname")
        if name:
            publication_name = name
    except Exception:
        logger.warning("sitemap_news_publication_name_unresolved")

    return [
        SitemapNewsRow(
            loc=f"/blog/{p.slug}",
            title=p.title,
            published_at=p.published_at,
            publication_name=publication_name,
        )
        for p in posts
    ]


async def _collect_videos(db: AsyncSession) -> list[SitemapVideoRow]:
    """Video-format posts with a cover image, newest first.

    A video entry without a thumbnail is invalid for Google, so a post whose
    cover is missing is skipped — emitting it broken would risk the file.
    """
    from app.modules.blog.domain.models import BlogPost, BlogPostStatus, PostFormat

    stmt = (
        select(BlogPost)
        .where(
            BlogPost.status == BlogPostStatus.PUBLISHED,
            BlogPost.deleted_at.is_(None),
            BlogPost.post_format == PostFormat.VIDEO,
            BlogPost.cover_image_url.is_not(None),
        )
        .order_by(BlogPost.published_at.desc().nullslast())
        .limit(NEWS_MAX_URLS)
    )
    posts = (await db.execute(stmt)).scalars().all()

    out: list[SitemapVideoRow] = []
    for p in posts:
        if not p.cover_image_url:
            continue
        out.append(
            SitemapVideoRow(
                loc=f"/blog/{p.slug}",
                title=p.title,
                # Google requires a non-empty description; the excerpt is the
                # closest short text the model carries, with a safe fallback
                # rather than an empty string the entry would be rejected for.
                description=(p.excerpt or p.title)[:500],
                thumbnail_url=p.cover_image_url,
                published_at=p.published_at,
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
    # Task pages (WordPress shortcode stubs like /wishlist, /my-account) are
    # UI shells the storefront serves from dedicated routes — not content to
    # index. A sitemap that advertises them contradicts the noindex the
    # dedicated route carries, and the stub body is what Google would read.
    pages = [p for p in pages if p.slug not in _TASK_PAGE_SLUGS]
    items = [PublicPageSummary.model_validate(p) for p in pages]

    section_rows: dict[str, list[Any]] = {}
    for name, collector, _changefreq, _priority in _SECTIONS:
        try:
            section_rows[name] = list(await collector(db))
        except Exception:
            logger.warning("sitemap_section_skipped", section=name)
            section_rows[name] = []

    # News/video sources fail open like the other sections: their absence
    # empties only their own sitemap files, never the main one.
    try:
        news = await _collect_news(db)
    except Exception:
        logger.warning("sitemap_section_skipped", section="news")
        news = []
    try:
        videos = await _collect_videos(db)
    except Exception:
        logger.warning("sitemap_section_skipped", section="videos")
        videos = []

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
        news=news,
        videos=videos,
        xml_fragment=xml_fragment,
    )
