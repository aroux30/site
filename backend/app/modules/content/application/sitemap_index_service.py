"""Sitemap index and per-provider sitemaps (WordPress wp-sitemap.xml parity).

One flat sitemap stops scaling: a crawler fetches a single file, and a
50 000-URL catalogue makes that file expensive to generate on every request.
WordPress emits a small index plus one file per content type, and so does
this.

Providers are derived from the same rows the flat sitemap already collects,
so the two can never disagree about which URLs are published.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

PROVIDERS = ("pages", "blog", "taxonomy", "products", "authors")

#: Where these routes are actually served. The routers are mounted with
#: ``settings.API_V1_PREFIX`` in ``main._include_routers``, so the index reads
#: it from the same setting rather than hardcoding a path that can drift.
def _api_prefix() -> str:
    from app.core.config.settings import get_settings

    return get_settings().API_V1_PREFIX.rstrip("/")

#: Shown when a provider has no rows — an empty sitemap is better than a
#: dangling index entry, which crawlers treat as an error.
_PROVIDER_PRIORITY = {
    "pages": 0.6,
    "blog": 0.8,
    "taxonomy": 0.5,
    "products": 0.7,
    # Author archives rank below the content they wrote.
    "authors": 0.3,
}


async def _provider_counts(db: AsyncSession) -> dict[str, int]:
    from app.modules.blog.domain.models import BlogCategory, BlogPost, BlogTag
    from app.modules.catalog.domain.models import Product
    from app.modules.content.domain.models import CmsPage
    from app.modules.users.domain.models import User

    live = (BlogPost.status == "published", BlogPost.deleted_at.is_(None))
    return {
        "pages": (await db.execute(
            select(func.count()).select_from(CmsPage).where(
                CmsPage.status == "published", CmsPage.deleted_at.is_(None))
        )).scalar_one(),
        "blog": (await db.execute(
            select(func.count()).select_from(BlogPost).where(*live))).scalar_one(),
        # Distinct author slugs, not authors: one author with five posts must
        # produce one index entry, matching what build_provider emits. The slug
        # lives on the user row, so this joins rather than reading the post.
        "authors": (await db.execute(
            select(func.count(func.distinct(User.author_slug)))
            .select_from(BlogPost)
            .join(User, User.id == BlogPost.author_id)
            .where(
                *live,
                User.author_slug.is_not(None),
                User.author_slug != "",
            )
        )).scalar_one(),
        "taxonomy": (
            (await db.execute(select(func.count()).select_from(BlogCategory))).scalar_one()
            + (await db.execute(select(func.count()).select_from(BlogTag))).scalar_one()
        ),
        "products": (await db.execute(
            select(func.count()).select_from(Product).where(Product.is_active.is_(True))
        )).scalar_one(),
    }


async def build_index(db: AsyncSession, base_url: str) -> str:
    """The sitemap index: a small document listing one file per provider.

    ``base_url`` is the *public* origin (https://shop.example), not the API
    origin, so the child locs must carry the path the crawler can actually
    fetch. These routes are served under the API prefix, so the path is built
    from it rather than guessed at the root: the index used to advertise
    ``{base}/sitemap-blog.xml``, which no rewrite routed, so every child was a
    404.
    """
    counts = await _provider_counts(db)
    base = base_url.rstrip("/")
    prefix = _api_prefix()
    entries = "".join(
        f"<sitemap><loc>{base}{prefix}/content/sitemap-{name}.xml</loc></sitemap>"
        for name in PROVIDERS
        if counts.get(name, 0)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f"{entries}</sitemapindex>"
    )


async def build_provider(db: AsyncSession, provider: str, base_url: str) -> str | None:
    """One provider's URL set as a ``<urlset>``; None when unknown."""
    if provider not in PROVIDERS:
        return None

    from app.modules.content.application.sitemap_service import build_sitemap_payload

    payload: dict[str, Any] = await build_sitemap_payload(db)
    base = base_url.rstrip("/")
    priority = _PROVIDER_PRIORITY[provider]
    default_freq = "daily" if provider in ("blog", "products") else "weekly"

    rows: list[tuple[str, str | None]] = []
    if provider == "pages":
        rows = [
            (f"{base}/{p['slug']}", _iso(p.updated_at))
            for p in payload.get("items", [])
        ]
    elif provider == "blog":
        # Blog posts are not in the shared payload (the storefront consumes the
        # paginated blog feed), so this provider reads them directly.
        from app.modules.blog.domain.models import BlogPost

        posts = (await db.execute(
            select(BlogPost).where(
                BlogPost.status == "published", BlogPost.deleted_at.is_(None)
            )
        )).scalars().all()
        rows = [(f"{base}/blog/{p.slug}", _iso(p.updated_at)) for p in posts]
    elif provider == "taxonomy":
        rows = [
            (f"{base}/blog/category/{r['slug']}", _iso(r.updated_at))
            for r in payload.get("blog_categories", [])
        ] + [
            (f"{base}/blog/tag/{r['slug']}", _iso(r.updated_at))
            for r in payload.get("blog_tags", [])
        ]
    elif provider == "authors":
        # Author archives are real pages at /author/<slug>, and WordPress ships a
        # users provider for them. Without it the only route to an author archive
        # is walking the blog, so none of them get indexed.
        #
        # The slug lives on the user, not on the post — `BlogPost` carries only
        # `author_id`, and reading `BlogPost.author_slug` raises. So this joins
        # the author the same way the storefront and the permalink helper do.
        # Only authors with at least one published post are listed: an archive
        # that renders empty is worse than an absent one.
        from sqlalchemy import func

        from app.modules.blog.domain.models import BlogPost
        from app.modules.users.domain.models import User

        author_rows = (
            await db.execute(
                select(User.author_slug, func.max(BlogPost.updated_at))
                .join(User, User.id == BlogPost.author_id)
                .where(
                    BlogPost.status == "published",
                    BlogPost.deleted_at.is_(None),
                    User.author_slug.is_not(None),
                    User.author_slug != "",
                )
                .group_by(User.author_slug)
            )
        ).all()
        rows = [(f"{base}/author/{slug}", _iso(updated)) for slug, updated in author_rows]
    else:  # products
        rows = [
            (f"{base}/products/{r['slug']}", _iso(r.updated_at))
            for r in payload.get("products", [])
        ]

    entries = "".join(
        f"<url><loc>{_esc(url)}</loc>"
        + (f"<lastmod>{_esc(lastmod)}</lastmod>" if lastmod else "")
        + f"<changefreq>{default_freq}</changefreq>"
        f"<priority>{priority}</priority></url>"
        for url, lastmod in rows
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f"{entries}</urlset>"
    )


def _iso(value: Any) -> str | None:
    return value.isoformat() if value is not None else None


def _esc(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
