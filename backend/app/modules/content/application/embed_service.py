"""URL embeds (oEmbed + Open Graph fallback) for the rich editor.

Given a URL, resolve provider embed metadata:
1. Known oEmbed providers (YouTube, Aparat, Twitter/X, Instagram) are queried
   against their official oEmbed endpoints.
2. Anything else falls back to fetching the page and reading Open Graph /
   Twitter Card meta tags.

SSO-safe by construction: only http(s) URLs, private/loopback IPs rejected,
response size capped, one redirect-hop limit left to httpx with a hard
timeout.
"""

from __future__ import annotations

import ipaddress
import re
from typing import Any
from urllib.parse import urlparse

import structlog

from app.core.exceptions.handlers import ValidationError

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

TIMEOUT_SECONDS = 8
MAX_HTML_BYTES = 512 * 1024

# provider name → (url pattern, oEmbed endpoint template)
_OEMBED_PROVIDERS: list[tuple[re.Pattern[str], str, str]] = [
    (
        re.compile(r"^https?://(www\.)?(youtube\.com/watch|youtu\.be/)", re.I),
        "youtube",
        "https://www.youtube.com/oembed?url={url}&format=json",
    ),
    (
        re.compile(r"^https?://(www\.)?aparat\.com/v/", re.I),
        "aparat",
        "https://www.aparat.com/etc/api/videoembed/videohash/{aparat_id}",
    ),
    (
        re.compile(r"^https?://(www\.)?(twitter\.com|x\.com)/.+/status/", re.I),
        "twitter",
        "https://publish.twitter.com/oembed?url={url}",
    ),
    (
        re.compile(r"^https?://(www\.)?instagram\.com/(p|reel)/", re.I),
        "instagram",
        "https://graph.facebook.com/v18.0/instagram_oembed?url={url}",
    ),
]

_META_RE = re.compile(
    r'<meta[^>]+(?:property|name)=["\']([^"\']+)["\'][^>]+content=["\']([^"\']*)["\']',
    re.IGNORECASE,
)
_META_RE_ALT = re.compile(
    r'<meta[^>]+content=["\']([^"\']*)["\'][^>]+(?:property|name)=["\']([^"\']+)["\']',
    re.IGNORECASE,
)
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)


def _validate_public_url(url: str) -> str:
    """Kept for callers that have not moved to the awaited guard yet.

    This was the original implementation and it had two holes, both measured
    in ``scripts/wp-parity/w5_ssrf_guard.py``: a host is never resolved, so a
    public name pointing at an internal address walks through; and
    ``ipaddress.ip_address`` rejects the hex (``0x7f.0.0.1``) and decimal
    (``2130706433``) spellings of 127.0.0.1, which the bare ``except
    ValueError`` then swallowed.

    Prefer ``app.core.security.url_guard.validate_public_url``, which resolves
    and vets every address. This wrapper keeps the old call sites working and
    applies the cheap subset of that check synchronously — it is a floor, not
    the real guard.
    """
    url = url.strip()
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValidationError("نشانی معتبر نیست")
    host = parsed.hostname.lower().rstrip(".")
    try:
        ip = ipaddress.ip_address(host)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise ValidationError("نشانی‌های داخلی مجاز نیستند")
    except ValueError:
        # Not a literal IP. A bare hostname is NOT cleared here — the caller
        # that can await must run the full DNS check. ``validate_public_url``
        # in app.core.security.url_guard is that check.
        pass
    if host in {"localhost", "localhost.localdomain"} or host.endswith(
        (".internal", ".local", ".lan")
    ):
        raise ValidationError("نشانی‌های داخلی مجاز نیستند")
    return url


def parse_og_tags(html: str) -> dict[str, Any]:
    """Extract Open Graph / Twitter card metadata from an HTML document."""
    tags: dict[str, str] = {}
    for match in _META_RE.finditer(html[:MAX_HTML_BYTES]):
        tags[match.group(1).lower()] = match.group(2)
    for match in _META_RE_ALT.finditer(html[:MAX_HTML_BYTES]):
        tags.setdefault(match.group(2).lower(), match.group(1))

    title = tags.get("og:title") or tags.get("twitter:title")
    if not title:
        m = _TITLE_RE.search(html[:MAX_HTML_BYTES])
        title = m.group(1).strip() if m else None
    return {
        "type": "link",
        "title": title,
        "description": tags.get("og:description") or tags.get("twitter:description"),
        "image": tags.get("og:image") or tags.get("twitter:image"),
        "site_name": tags.get("og:site_name"),
    }


async def resolve_embed(url: str) -> dict[str, Any]:
    """Resolve a URL into embed metadata ({type, html?} or OG link card)."""
    import httpx

    from app.core.security.url_guard import validate_public_url

    # The DNS-resolving guard, not the synchronous subset. This is a
    # server-initiated fetch of a user-supplied URL, so "the name looks public"
    # is not the question — "does it resolve somewhere public" is.
    url = await validate_public_url(url)

    for pattern, provider, endpoint_tpl in _OEMBED_PROVIDERS:
        match = pattern.match(url)
        if not match:
            continue
        endpoint = endpoint_tpl
        if provider == "aparat":
            video_id = url.rstrip("/").split("/")[-1]
            endpoint = endpoint_tpl.format(aparat_id=video_id)
        else:
            from urllib.parse import quote

            endpoint = endpoint_tpl.format(url=quote(url, safe=""))
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
                resp = await client.get(endpoint)
            if resp.status_code == 200:
                data = resp.json()
                logger.info("oembed_resolved", provider=provider, url=url)
                return {
                    "type": data.get("type", "rich"),
                    "provider": provider,
                    "title": data.get("title"),
                    "author_name": data.get("author_name"),
                    "thumbnail_url": data.get("thumbnail_url"),
                    "html": data.get("html"),
                    "width": data.get("width"),
                    "height": data.get("height"),
                    "url": url,
                }
            logger.warning("oembed_provider_miss", provider=provider, status=resp.status_code)
        except Exception as exc:  # fall through to OG
            logger.warning("oembed_provider_error", provider=provider, error=str(exc))
        break  # known provider matched but failed → OG fallback on the page itself

    # Generic fallback: fetch the page and read OG tags.
    try:
        async with httpx.AsyncClient(
            timeout=TIMEOUT_SECONDS, follow_redirects=True, max_redirects=3
        ) as client:
            resp = await client.get(url, headers={"User-Agent": "site-embedbot/1.0"})
        if resp.status_code != 200:
            raise ValidationError(f"صفحه مقصد پاسخ {resp.status_code} داد")
        card = parse_og_tags(resp.text)
        card["url"] = url
        return card
    except ValidationError:
        raise
    except Exception as exc:
        raise ValidationError(f"بازیابی نشانی ممکن نشد: {exc}") from exc
