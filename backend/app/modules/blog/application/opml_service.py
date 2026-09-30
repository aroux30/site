"""OPML 2.0 import/export (WordPress parity).

OPML is how readers subscribe to a site's feeds and bookmarks. WordPress
exports two outlines from one document: ``outlines[0]`` holds the feeds (blog
and per-category), ``outlines[1]`` holds the links (curated bookmarks) grouped
by their category.

Both directions are implemented. Export alone would be a dead end: a reader
that imports a feed listing but no links silently loses everything an
operator had curated, and nothing in the UI would say so.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING
from xml.etree import ElementTree
from xml.sax.saxutils import escape, quoteattr

import structlog
from sqlalchemy import select

from app.core.exceptions.handlers import ValidationError
from app.modules.blog.domain.models import BlogCategory, BlogLink
from app.shared.domain.slug import generate_slug

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

#: An OPML document is a subscription list; a body bigger than this is either
#: a mistake or an attempt to make the parser allocate without bound.
MAX_OPML_BYTES = 5 * 1024 * 1024

_ALLOWED_SCHEMES = ("http://", "https://", "feed://", "itpc://")


@dataclass(frozen=True)
class OpmlLink:
    """One imported outline entry."""

    title: str
    url: str
    category: str | None = None


def _is_safe_url(url: str) -> bool:
    """Reject anything that is not a fetchable web/feed URL.

    An OPML import is operator-supplied XML, but a link row ends up in
    rendered HTML; a ``javascript:`` URL there would be stored XSS, so the
    scheme is checked rather than the string merely being non-empty.
    """
    candidate = (url or "").strip()
    if not candidate:
        return False
    lowered = candidate.lower()
    if lowered.startswith(_ALLOWED_SCHEMES):
        return True
    # Anything carrying a scheme is rejected unless it is on the allowlist.
    # Checking for "://" alone was not enough: "javascript:alert(1)" has no
    # slashes yet is still executable when rendered as an href.
    scheme, sep, _rest = lowered.partition(":")
    if sep and "/" not in scheme and scheme.isascii() and scheme.isalpha():
        return False
    # A bare host is legal in OPML and readers resolve it as https.
    if lowered.startswith(("#", "/")):
        return False
    return "://" not in lowered


def build_opml(
    *,
    site_title: str,
    site_url: str,
    feed_posts_url: str,
    categories: list[tuple[str, str]] | None = None,
    links: list[BlogLink] | None = None,
    post_feed_url: str | None = None,
) -> str:
    """Render an OPML 2.0 document.

    ``categories`` is ``(name, feed_url)`` pairs; each becomes its own outline
    in the head so a reader can subscribe to one category instead of the whole
    blog. ``links`` become the second outline, grouped by ``category``.
    """
    now = format_created_date()
    parts: list[str] = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<opml version="2.0">',
        "  <head>",
        f"    <title>{escape(site_title)}</title>",
        f"    <dateCreated>{now}</dateCreated>",
        f"    <ownerName>{escape(site_title)}</ownerName>",
        f"    <docs>http://opml.org/spec2.opml</docs>",
        "  </head>",
        "  <body>",
        f"    <outline text={quoteattr(site_title)} title={quoteattr(site_title)} type=\"rss\""
        f" xmlUrl={quoteattr(feed_posts_url)} htmlUrl={quoteattr(site_url)} />",
    ]

    for name, feed_url in categories or []:
        parts.append(
            f"    <outline text={quoteattr(name)} title={quoteattr(name)} type=\"rss\""
            f" xmlUrl={quoteattr(feed_url)} />"
        )

    if post_feed_url:
        parts.append(
            f"    <outline text=\"آخرین نوشته‌ها\" type=\"rss\""
            f" xmlUrl={quoteattr(post_feed_url)} />"
        )

    # Second outline: the curated links, grouped by category.
    by_category: dict[str, list[BlogLink]] = {}
    for link in links or []:
        if not link.is_visible:
            continue
        by_category.setdefault(link.category or "", []).append(link)

    for category, items in sorted(by_category.items()):
        label = category or "پیوندها"
        children = "".join(
            f"\n        <outline text={quoteattr(i.title)} title={quoteattr(i.title)}"
            f" type=\"link\" url={quoteattr(i.url)} />"
            for i in sorted(items, key=lambda x: (x.position, x.created_at is None, x.created_at))
        )
        parts.append(f"    <outline text={quoteattr(label)} title={quoteattr(label)}>{children}\n    </outline>")

    parts.append("  </body>")
    parts.append("</opml>")
    return "\n".join(parts)


def format_created_date() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).strftime("%a, %d %b %Y %H:%M:%S %z")


async def export_opml(
    db: "AsyncSession",
    *,
    site_title: str = "فروشگاه",
    site_url: str = "https://example.com",
    post_feed_url: str = "/api/v1/blog/feed/rss",
    limit_categories: int = 50,
    limit_links: int = 500,
) -> str:
    """Build the export document from live rows."""
    from app.modules.settings.application.site_options_service import SiteOptionsService

    title = await SiteOptionsService.get(db, "blogname", site_title) or site_title
    home = (await SiteOptionsService.get(db, "home", site_url) or site_url).rstrip("/")
    rss = await SiteOptionsService.get(db, "posts_per_rss", "20") or "20"

    cats = (
        (
            await db.execute(
                select(BlogCategory)
                .order_by(BlogCategory.name.asc())
                .limit(limit_categories)
            )
        )
        .scalars()
        .all()
    )
    categories = [
        (c.name, f"{home}/api/v1/blog/feed/rss/{c.slug}") for c in cats
    ]

    links = (
        (
            await db.execute(
                select(BlogLink)
                .where(BlogLink.is_visible.is_(True))
                .order_by(BlogLink.position.asc(), BlogLink.created_at.asc())
                .limit(limit_links)
            )
        )
        .scalars()
        .all()
    )

    return build_opml(
        site_title=title,
        site_url=home,
        feed_posts_url=f"{home}{post_feed_url}",
        post_feed_url=f"{home}{post_feed_url}?limit={rss}",
        categories=categories,
        links=list(links),
    )


def parse_opml(xml_text: str) -> tuple[list[OpmlLink], list[str]]:
    """Parse an OPML document into link outlines and feed titles.

    Returns ``(links, feed_titles)``. Feed outlines are reported rather than
    imported: subscribing a reader to this site's own feeds from its own export
    is not a thing the operator can mean, and silently creating them would
    produce subscriptions to URLs this site serves itself.

    Raises ``ValidationError`` on unparseable or oversized input rather than
    letting a malformed document reach the caller as a confusing 500.
    """
    raw = (xml_text or "").encode("utf-8")
    if len(raw) > MAX_OPML_BYTES:
        raise ValidationError(detail="حجم فایل OPML بیش از حد مجاز است")

    try:
        root = ElementTree.fromstring(raw)
    except ElementTree.ParseError as exc:
        raise ValidationError(detail=f"فایل OPML قابل خواندن نیست: {exc}") from exc

    if root.tag.lower() != "opml":
        raise ValidationError(detail="ریشه‌ی سند باید <opml> باشد")

    links: list[OpmlLink] = []
    feeds: list[str] = []
    body = root.find("body")
    if body is None:
        return links, feeds

    def _walk(node: ElementTree.Element, group: str | None) -> None:
        for outline in node.findall("outline"):
            text = (outline.get("text") or outline.get("title") or "").strip()
            url = (outline.get("url") or "").strip()
            xml_url = (outline.get("xmlUrl") or "").strip()
            children = outline.findall("outline")

            if xml_url:
                feeds.append(text or xml_url)
            elif url and _is_safe_url(url):
                links.append(OpmlLink(title=text or url, url=url, category=group))
            elif children:
                # A group outline: remember the label and descend into it.
                _walk(outline, text or group)

    _walk(body, None)
    return links, feeds


async def import_opml(
    db: "AsyncSession",
    xml_text: str,
    *,
    created_by: uuid.UUID | None = None,
    default_category: str | None = None,
    replace_existing: bool = False,
) -> dict[str, int]:
    """Import outline links. Returns a summary.

    Existing slugs are updated rather than duplicated, so importing the same
    file twice converges instead of doubling the sidebar.
    """
    parsed, _feeds = parse_opml(xml_text)
    if not parsed:
        return {"imported": 0, "updated": 0, "skipped": 0}

    if replace_existing:
        await db.execute(BlogLink.__table__.delete())

    existing = {
        row.slug: row
        for row in (await db.execute(select(BlogLink).where(BlogLink.slug.in_(
            [generate_slug(link.title) for link in parsed]
        )))).scalars().all()
    }

    imported = updated = skipped = 0
    for link in parsed:
        # parse_opml already drops unsafe schemes; this is the second gate for
        # anything that reached here another way.
        if not _is_safe_url(link.url):
            skipped += 1
            continue

        slug = generate_slug(link.title) or generate_slug(link.url, fallback="link")
        row = existing.get(slug)
        if row is not None:
            row.url = link.url
            if link.title:
                row.title = link.title
            row.category = link.category or default_category
            updated += 1
            continue
        db.add(
            BlogLink(
                title=link.title,
                url=link.url,
                slug=slug,
                category=link.category or default_category,
                created_by=created_by,
            )
        )
        imported += 1

    await db.flush()
    await logger.ainfo("opml_imported", imported=imported, updated=updated, skipped=skipped)
    return {"imported": imported, "updated": updated, "skipped": skipped}
