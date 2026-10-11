"""Extract and store the links in a post body (Rank Math's link indexing).

On every save the operator's post body is scanned for anchors. Each managed
anchor (internal or external) becomes a row in ``seo_internal_links``, with
``target_post_id`` filled when the URL resolves to a post on this site. The
table is the answer to "which posts link to this one?" — the question the
suggestion panel and the orphan report both need — and re-parsing every body
on each request would not scale past a few hundred posts.

Extraction uses an HTML parser, not a regex. The architecture note calls this
out explicitly: a regex over ``<a ...>`` misses an anchor split across lines,
an attribute order it did not anticipate, or a ``<a>`` inside a comment. The
standard library's ``html.parser`` is enough — the input is already
bleach-sanitized on write.
"""

from __future__ import annotations

import hashlib
import uuid
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.seo.domain.link_models import SeoInternalLink


class _AnchorCollector(HTMLParser):
    """Collect ``(href, anchor_text, is_nofollow, target_blank)`` per anchor."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.anchors: list[tuple[str, str, bool, bool]] = []
        self._current: dict[str, object] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        attr = {k.lower(): (v or "") for k, v in attrs}
        href = attr.get("href", "").strip()
        rel = attr.get("rel", "").lower()
        self._current = {
            "href": href,
            "text": [],
            "nofollow": "nofollow" in rel.split(),
            "blank": attr.get("target", "").lower() == "_blank",
        }

    def handle_data(self, data: str) -> None:
        if self._current is not None:
            text = self._current["text"]
            assert isinstance(text, list)
            text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag != "a" or self._current is None:
            return
        href = str(self._current["href"])
        text = " ".join(str(p) for p in self._current["text"]).strip()
        self.anchors.append(
            (
                href,
                text,
                bool(self._current["nofollow"]),
                bool(self._current["blank"]),
            )
        )
        self._current = None


def normalize_url(url: str, *, base: str | None = None) -> str:
    """Canonical form of a URL for hashing: scheme+host lowercased, fragment
    stripped, trailing slash trimmed. Path case is preserved (it is
    case-sensitive on most servers)."""
    url = url.strip()
    if not url:
        return ""
    if base and not url.startswith(("http://", "https://", "//", "/", "#", "mailto:", "tel:")):
        url = urljoin(base, url)
    try:
        parsed = urlparse(url)
    except ValueError:
        return url
    scheme = (parsed.scheme or "").lower()
    host = (parsed.hostname or "").lower()
    if not scheme and not host:
        # A site-relative path — keep it as-is (minus any fragment).
        return parsed.path.rstrip("/") or "/"
    port = f":{parsed.port}" if parsed.port else ""
    path = parsed.path.rstrip("/") or "/"
    return f"{scheme}://{host}{port}{path}"


def url_hash(url: str) -> str:
    return hashlib.md5(url.encode("utf-8")).hexdigest()


def extract_anchors(content: str) -> list[tuple[str, str, bool, bool]]:
    """Return the raw anchors in a body. Never raises on malformed HTML."""
    parser = _AnchorCollector()
    try:
        parser.feed(content or "")
        parser.close()
    except Exception:
        # A malformed body must not break a save; whatever was collected is
        # returned (usually empty).
        pass
    return parser.anchors


def _classify(href: str, site_hosts: set[str]) -> str | None:
    """Return ``internal``/``external``, or None for anchors we do not index."""
    href = href.strip()
    if not href or href.startswith("#"):
        return None
    if href.startswith(("mailto:", "tel:", "javascript:", "data:")):
        return None
    if href.startswith(("/", "./", "../")) and not href.startswith("//"):
        return "internal"
    try:
        host = (urlparse(href).hostname or "").lower()
    except ValueError:
        return None
    if not host:
        return None
    return "internal" if host in site_hosts else "external"


async def index_post_links(
    db: AsyncSession,
    *,
    post_id: uuid.UUID,
    content: str,
    site_hosts: set[str],
    base_url: str | None = None,
) -> int:
    """Replace this post's link rows with a fresh scan of ``content``.

    Delete-then-insert, not upsert: a link the operator removed must disappear
    from the index, and an upsert would leave it behind. The write is one
    transaction, so a failure leaves the previous rows intact.

    Returns the number of rows written.
    """
    from app.modules.blog.domain.models import BlogPost

    anchors = extract_anchors(content or "")

    # Resolve internal URLs to post ids in one pass: collect the candidate
    # slugs first, then one query, rather than a query per anchor.
    seen: set[tuple[str, str]] = set()
    rows: list[dict[str, object]] = []
    internal_slugs: set[str] = set()
    prepared: list[tuple[str, str, str, bool, bool]] = []
    for href, text, nofollow, blank in anchors:
        kind = _classify(href, site_hosts)
        if kind is None:
            continue
        norm = normalize_url(href, base=base_url)
        # Dedup on (hash, anchor) so the same URL linked with the same anchor
        # twice in one body is one row — matching the unique constraint.
        key = (url_hash(norm), text[:500])
        if key in seen:
            continue
        seen.add(key)
        prepared.append((norm, text[:500], kind, nofollow, blank))
        if kind == "internal":
            slug = _slug_from_url(norm)
            if slug:
                internal_slugs.add(slug)

    slug_to_id: dict[str, uuid.UUID] = {}
    if internal_slugs:
        result = await db.execute(
            select(BlogPost.slug, BlogPost.id).where(BlogPost.slug.in_(internal_slugs))
        )
        slug_to_id = {slug: pid for slug, pid in result.all()}

    for norm, text, kind, nofollow, blank in prepared:
        target_id = None
        if kind == "internal":
            slug = _slug_from_url(norm)
            if slug:
                target_id = slug_to_id.get(slug)
        rows.append(
            {
                "post_id": post_id,
                "target_post_id": target_id,
                "url": norm[:500],
                "url_hash": url_hash(norm),
                "anchor_text": text,
                "link_type": kind,
                "is_nofollow": nofollow,
                "target_blank": blank,
            }
        )

    await db.execute(delete(SeoInternalLink).where(SeoInternalLink.post_id == post_id))
    for row in rows:
        db.add(SeoInternalLink(**row))  # type: ignore[arg-type]
    await db.commit()
    return len(rows)


def _slug_from_url(normalized_url: str) -> str | None:
    """Extract a blog slug from an internal URL (``/blog/<slug>``).

    Only ``/blog/<slug>`` resolves to a BlogPost; a link to ``/products/x`` is
    internal but has no post to point at, so it stays internal with a NULL
    target (the link is still counted, it just cannot seed a reverse-link edge).
    """
    try:
        path = urlparse(normalized_url).path
    except ValueError:
        return None
    parts = [p for p in path.split("/") if p]
    if len(parts) >= 2 and parts[0] == "blog":
        return parts[1]
    return None
