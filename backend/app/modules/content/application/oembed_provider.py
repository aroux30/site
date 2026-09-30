"""oEmbed provider: make this site's content embeddable by others.

We already *consume* oEmbed in the editor (`embed_service` resolves a pasted
URL into a card), but nothing served the other direction: pasting one of our
blog URLs into another CMS produced nothing, because no endpoint answered.

The provider form (`/oembed/1.0/embed`) is the simple one; the discovery link
is what a consumer's editor actually fetches first, so both are here.
"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

#: oEmbed's 1.0 spec fixes these; version 1.0 (draft) is the widely supported
#: baseline that WordPress, Squarespace and Coze all speak.
PROVIDER_NAME = "Iranian Tech Store"
PROVIDER_URL = "https://iranian-tech.store"
PROVIDER_VERSION = "1.0"

_HTML_EMBED = (
    '<iframe src="{url}" width="{width}" height="{height}" frameborder="0" '
    'allowfullscreen loading="lazy" title="{title}"></iframe>'
)

#: Only content we actually serve may be embedded; an arbitrary path that 404s
#: must not produce a valid embed card.
_EMBEDDABLE = re.compile(
    r"^/(blog/[^/]+|products/[^/]+|shop/[^/]+|news/[^/]+)$"
)


def _base_url(request_base: str) -> str:
    return request_base.rstrip("/")


async def _resolve(
    db: AsyncSession,
    url: str,
    base: str,
    *,
    maxwidth: int = 640,
    maxheight: int = 0,
) -> dict[str, Any] | None:
    """Find the content behind a site-relative path, or None.

    `maxwidth`/`maxheight` come from the consuming editor: it asks for a
    width and the provider must not hand back a wider card, so the embed is
    rendered at the requested size rather than a fixed one.
    """
    path = url[len(base):] if url.startswith(base) else url
    path = path.split("?", 1)[0].split("#", 1)[0]
    if not _EMBEDDABLE.match(path):
        return None

    from app.modules.blog.domain.models import BlogPost
    from app.modules.catalog.domain.models import Product
    from app.modules.content.domain.models import CmsPage, PageStatus

    segments = [s for s in path.split("/") if s]
    kind, slug = segments[0], segments[1]

    if kind == "blog":
        row = (await db.execute(
            select(BlogPost).where(
                BlogPost.slug == slug,
                BlogPost.status == "published",
                BlogPost.deleted_at.is_(None),
            )
        )).scalar_one_or_none()
        if row is None:
            return None
        return {
            "type": "rich",
            "version": PROVIDER_VERSION,
            "provider_name": PROVIDER_NAME,
            "provider_url": PROVIDER_URL,
            "title": row.title,
            "author_name": row.author_name if hasattr(row, "author_name") else None,
            "thumbnail_url": row.cover_image_url,
            "html": _HTML_EMBED.format(
                url=f"{base}/blog/{row.slug}",
                width=maxwidth, height=maxheight or 360, title=row.title,
            ),
            "width": maxwidth,
            "height": maxheight or 360,
        }

    if kind == "products":
        row = (await db.execute(
            select(Product).where(Product.slug == slug, Product.is_active.is_(True))
        )).scalar_one_or_none()
        if row is None:
            return None
        return {
            "type": "rich",
            "version": PROVIDER_VERSION,
            "provider_name": PROVIDER_NAME,
            "provider_url": PROVIDER_URL,
            "title": row.name,
            "thumbnail_url": getattr(row, "primary_image_url", None),
            "html": _HTML_EMBED.format(
                url=f"{base}/products/{row.slug}",
                width=maxwidth, height=maxheight or 500, title=row.name,
            ),
            "width": maxwidth,
            "height": maxheight or 500,
        }

    # Bare /<slug> is a CMS page.
    row = (await db.execute(
        select(CmsPage).where(
            CmsPage.slug == slug,
            CmsPage.status == PageStatus.PUBLISHED,
            CmsPage.deleted_at.is_(None),
        )
    )).scalar_one_or_none()
    if row is None:
        return None
    return {
        "type": "rich",
        "version": PROVIDER_VERSION,
        "provider_name": PROVIDER_NAME,
        "provider_url": PROVIDER_URL,
        "title": row.title,
        "html": _HTML_EMBED.format(
            url=f"{base}/{row.slug}",
            width=maxwidth, height=maxheight or 360, title=row.title,
        ),
        "width": maxwidth,
        "height": maxheight or 360,
    }
