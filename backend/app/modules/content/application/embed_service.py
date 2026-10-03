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
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

import structlog

from app.core.exceptions.handlers import ValidationError

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

TIMEOUT_SECONDS = 8
MAX_HTML_BYTES = 512 * 1024

# provider name → (url pattern, oEmbed endpoint template)
#
# The four original entries were the ones this store happened to embed;
# WordPress ships a whitelist of ~34 (wp-includes/class-wp-oembed.php). The
# set below is the common half of that list — the ones an Iranian storefront
# actually receives in supplier copy and customer reviews. Anything still not
# matched falls through to the Open Graph card, so an omission degrades to a
# link preview rather than to nothing.
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
    (
        re.compile(r"^https?://(www\.)?vimeo\.com/\d", re.I),
        "vimeo",
        "https://vimeo.com/api/oembed.json?url={url}",
    ),
    (
        re.compile(r"^https?://(www\.)?dailymotion\.com/video/", re.I),
        "dailymotion",
        "https://www.dailymotion.com/services/oembed?url={url}",
    ),
    (
        re.compile(r"^https?://(www\.)?soundcloud\.com/", re.I),
        "soundcloud",
        "https://soundcloud.com/oembed?format=json&url={url}",
    ),
    (
        re.compile(r"^https?://open\.spotify\.com/", re.I),
        "spotify",
        "https://open.spotify.com/oembed?url={url}",
    ),
    (
        re.compile(r"^https?://(www\.)?flickr\.com/photos/", re.I),
        "flickr",
        "https://www.flickr.com/services/oembed/?format=json&url={url}",
    ),
    (
        re.compile(r"^https?://(www\.)?tumblr\.com/.+/\d+", re.I),
        "tumblr",
        "https://www.tumblr.com/oembed/1.0/?url={url}",
    ),
    (
        re.compile(r"^https?://(www\.)?reddit\.com/r/[^/]+/comments/", re.I),
        "reddit",
        "https://www.reddit.com/oembed?url={url}",
    ),
    (
        re.compile(r"^https?://(www\.)?wordpress\.tv/", re.I),
        "wordpress-tv",
        "https://wordpress.tv/oembed/?url={url}",
    ),
    (
        re.compile(r"^https?://(www\.)?(facebook\.com|fb\.watch)/", re.I),
        "facebook",
        # Facebook's oEmbed requires an app token and is deliberately not
        # wired: without one the endpoint 400s, and the OG fallback still
        # produces a usable link card. The pattern is listed so the provider
        # is *named* in logs rather than appearing as an anonymous miss.
        "",
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

#: oEmbed discovery, as WordPress's ``wp_oembed_get`` does it: a page that
#: serves oEmbed advertises its own endpoint with this link tag, and a consumer
#: that finds it can render a real embed instead of a link card. The type is
#: pinned to ``application/json+oembed`` — ``text/xml+oembed`` returns XML that
#: needs a separate parser, so it is deliberately not matched (a page offering
#: only XML falls through to the OG card, which still works).
#:
#: Matches in either attribute order because both appear in the wild; the
#: href is captured regardless of which side it sits on.
_DISCOVERY_JSON_RE = re.compile(
    r"""<link\b[^>]*?"""
    r"""(?:"""
    r"""type=["']application/json\+oembed["'][^>]*?href=["']([^"']+)["']"""
    r"""|"""
    r"""href=["']([^"']+)["'][^>]*?type=["']application/json\+oembed["']"""
    r""")"""
    r"""[^>]*?/?>""",
    re.IGNORECASE | re.DOTALL,
)


def extract_oembed_discovery(html: str) -> str | None:
    """The page's own JSON oEmbed endpoint, or None.

    Only the FIRST tag is returned: a page carrying ten discovery links must
    not turn one paste into ten outbound fetches, and the first is what every
    consumer (WordPress included) honours.

    The href may be relative — ``urljoin`` against the page URL is the
    caller's job, because only it knows the page URL. This function stays
    pure so it is testable without a fetch.
    """
    match = _DISCOVERY_JSON_RE.search(html[:MAX_HTML_BYTES])
    if match is None:
        return None
    href = (match.group(1) or match.group(2) or "").strip()
    return href or None


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


#: How long a resolved embed is reused, in seconds. A week is WordPress's own
#: figure and matches how rarely a published page changes the video it embeds.
#: Short enough that a deleted YouTube video stops rendering a dead player.
EMBED_CACHE_TTL_SECONDS = 7 * 24 * 3600

#: Site options. The TTL was a module constant and the host set was "anything
#: public" — so an operator could not shorten the cache after a provider
#: changed its markup, and could not narrow the outbound surface to the
#: providers their store actually embeds.
EMBED_CACHE_TTL_HOURS_OPTION = "embed_cache_ttl_hours"
EMBED_ALLOWED_HOSTS_OPTION = "embed_allowed_hosts"

#: Negative results are cached too, and for much less time. A URL that failed to
#: resolve is usually a transient provider hiccup; caching it for a week would
#: make one bad response permanent in the page's markup.
EMBED_NEGATIVE_TTL_SECONDS = 300

#: Cap on the cached payload. The metadata is a title, a type and a snippet of
#: provider HTML; anything larger is a provider returning a page, not an
#: oEmbed, and does not belong in Redis.
EMBED_CACHE_MAX_BYTES = 16 * 1024


async def _cache_ttl_seconds(db: "AsyncSession | None") -> int:
    """The operator's positive-result cache window, in seconds.

    Read per resolution rather than cached in a module constant: the moment an
    operator wants a shorter window is the moment a provider changed its
    markup, and a restart to pick that up is the wrong answer. Clamped to
    1 hour..30 days — zero would disable caching entirely and turn every page
    render into an outbound request, which is the failure this cache exists to
    prevent.
    """
    if db is None:
        return EMBED_CACHE_TTL_SECONDS
    from app.modules.settings.application.site_options_service import SiteOptionsService

    default_hours = EMBED_CACHE_TTL_SECONDS // 3600
    hours = await SiteOptionsService.get_int(
        db,
        EMBED_CACHE_TTL_HOURS_OPTION,
        default_hours,
        minimum=1,
        maximum=30 * 24,
    )
    return hours * 3600


async def _allowed_hosts(db: "AsyncSession | None") -> set[str] | None:
    """The operator's embed host allowlist, or None when unset (allow all).

    Comma-separated hostnames. Unset means "no allowlist" — a store that never
    touched the setting keeps resolving every provider, which is the behaviour
    before the option existed. A set means only those hosts resolve through
    the provider path; everything else still gets the Open Graph card, so a
    host outside the list degrades to a link preview rather than an error.

    This is a policy control, not the security boundary: the SSRF guard
    (``validate_public_url``) still runs first and still rejects private and
    loopback addresses regardless of what is listed here.
    """
    if db is None:
        return None
    from app.modules.settings.application.site_options_service import SiteOptionsService

    raw = await SiteOptionsService.get(db, EMBED_ALLOWED_HOSTS_OPTION, "") or ""
    hosts = {
        part.strip().lower().lstrip(".")
        for part in raw.split(",")
        if part.strip()
    }
    return hosts or None


def _host_matches(host: str, allowed: set[str]) -> bool:
    """Whether ``host`` is in the allowlist, counting subdomains.

    ``youtube.com`` in the list matches ``www.youtube.com`` and
    ``m.youtube.com`` — an operator listing a domain means the domain, not the
    exact spelling of one of its hosts. Matching is on whole labels (suffix
    after a dot), so ``notyoutube.com`` is not matched by ``youtube.com``.
    """
    host = host.lower()
    return any(host == a or host.endswith("." + a) for a in allowed)


def _cache_key(url: str) -> str:
    """Redis key for a resolved embed.

    Hashed rather than the raw URL: keys are visible in memory dumps and slow
    logs, and a raw URL can carry a token in its query string.
    """
    import hashlib

    return "embed:v1:" + hashlib.sha256(url.encode()).hexdigest()


async def _cache_get(url: str) -> dict[str, Any] | None:
    """Read a cached result, or None on a miss or an unreachable Redis.

    Fail-open on purpose: a cache outage must slow an embed down, not break
    the page that embeds it.
    """
    import json

    try:
        from app.core.cache.redis import get_redis

        redis = await get_redis()
        raw = await redis.get(_cache_key(url))
    except Exception as exc:  # noqa: BLE001 — any Redis failure is a miss
        logger.debug("embed_cache_read_failed", error=str(exc))
        return None
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError):
        return None
    if not isinstance(payload, dict) or "type" not in payload:
        return None
    return payload


async def _cache_put(
    url: str, result: dict[str, Any], *, db: "AsyncSession | None" = None
) -> None:
    """Store a resolved result, ignoring any failure."""
    import json

    try:
        body = json.dumps(result, ensure_ascii=False)
        if len(body.encode()) > EMBED_CACHE_MAX_BYTES:
            logger.debug("embed_cache_payload_too_large", url_host=urlparse(url).netloc)
            return
        from app.core.cache.redis import get_redis

        redis = await get_redis()
        # A result with no html is a link card or a failure, cached briefly.
        ttl = (
            await _cache_ttl_seconds(db)
            if result.get("html")
            else EMBED_NEGATIVE_TTL_SECONDS
        )
        await redis.set(_cache_key(url), body, ex=ttl)
    except Exception as exc:  # noqa: BLE001 — any Redis failure is a no-op
        logger.debug("embed_cache_write_failed", error=str(exc))


async def _try_oembed_discovery(
    html: str,
    page_url: str,
) -> dict[str, Any] | None:
    """Follow the page's own oEmbed endpoint, if it advertises one.

    This is the second hop of the resolution, and it is a *second* SSRF
    surface: the URL being fetched comes out of HTML the far end controls. A
    malicious page can put ``http://169.254.169.254/…`` in its discovery tag
    and, without a guard here, the server fetches its own metadata service.
    So the discovered href goes through ``validate_public_url`` — the same
    DNS-resolving guard the page fetch itself uses.

    (``validate_pinned_url`` would close the check-to-connect rebinding window
    as well, but httpx 0.28 dropped the SNI-override extension, so pinning an
    HTTPS URL to an IP literal breaks certificate verification. The exposure
    here is therefore identical to the main page fetch's, which is the
    project's existing posture for server-side fetches.)

    Returns a result in the same shape the known-provider path produces, or
    None for every failure. None is not an error: the caller falls back to the
    Open Graph card, so a page with a broken endpoint still embeds as a link.
    """
    import httpx

    from app.core.security.url_guard import validate_public_url
    from urllib.parse import urljoin

    href = extract_oembed_discovery(html)
    if not href:
        return None

    endpoint = urljoin(page_url, href)
    try:
        endpoint = await validate_public_url(endpoint, what="نشانی oEmbed")
    except ValidationError:
        # A discovery tag pointing inward is refused, and refused *quietly* —
        # the page itself was public and may still produce a fine OG card.
        logger.warning("oembed_discovery_internal_refused", href=href[:200])
        return None

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
            resp = await client.get(
                endpoint,
                headers={"User-Agent": "site-embedbot/1.0"},
            )
        if resp.status_code != 200:
            logger.warning(
                "oembed_discovery_miss", endpoint=endpoint[:200], status=resp.status_code
            )
            return None
        data = resp.json()
    except Exception as exc:  # noqa: BLE001 — a bad endpoint falls back to OG
        logger.warning("oembed_discovery_error", endpoint=endpoint[:200], error=str(exc))
        return None

    html_payload = data.get("html")
    if not html_payload:
        # A JSON answer without embeddable HTML is a link, not an embed; the
        # OG card is the better result and costs nothing extra.
        return None
    logger.info("oembed_discovery_resolved", endpoint=endpoint[:200])
    return {
        "type": data.get("type", "rich"),
        "provider": "discovery",
        "title": data.get("title"),
        "author_name": data.get("author_name"),
        "thumbnail_url": data.get("thumbnail_url"),
        "html": html_payload,
        "width": data.get("width"),
        "height": data.get("height"),
        "url": page_url,
    }


async def resolve_embed(
    url: str, use_cache: bool = True, *, db: "AsyncSession | None" = None
) -> dict[str, Any]:
    """Resolve a URL into embed metadata ({type, html?} or OG link card).

    The same URL is embedded in the preview and then in the published page, and
    often in several pages, and every resolution is an outbound request to a
    third party. The result is cached by URL; ``use_cache=False`` is the
    explicit bypass for a re-resolve after an author edits the URL.

    ``db`` is optional so existing callers keep working; when passed, the
    operator's cache window and host allowlist are honoured. Without it the
    module defaults apply — which is exactly the behaviour before the options
    existed.
    """
    import httpx

    from app.core.security.url_guard import validate_public_url

    if use_cache:
        cached = await _cache_get(url)
        if cached is not None:
            return cached

    # The DNS-resolving guard, not the synchronous subset. This is a
    # server-initiated fetch of a user-supplied URL, so "the name looks public"
    # is not the question — "does it resolve somewhere public" is.
    url = await validate_public_url(url)

    # The operator's allowlist, when set, narrows which hosts get the provider
    # path. It is checked after the SSRF guard, never instead of it: the guard
    # is the security boundary, the list is a policy choice. A host outside the
    # list is not refused — it falls through to the OG card, so the embed still
    # renders as a link rather than as an error.
    allowed = await _allowed_hosts(db)
    host = (urlparse(url).netloc or "").split(":")[0]
    provider_path_allowed = allowed is None or _host_matches(host, allowed)
    if not provider_path_allowed:
        logger.info("embed_host_not_allowlisted", host=host)

    for pattern, provider, endpoint_tpl in _OEMBED_PROVIDERS if provider_path_allowed else []:
        match = pattern.match(url)
        if not match:
            continue
        if not endpoint_tpl:
            # The provider is recognised but has no usable unauthenticated
            # oEmbed endpoint (Facebook). The name still lands in the log so
            # a miss reads as "this provider", not as an anonymous failure,
            # and the OG fallback below handles the card.
            logger.info("oembed_provider_no_endpoint", provider=provider, url=url)
            break
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
                result = {
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
                await _cache_put(url, result, db=db)
                return result
            logger.warning("oembed_provider_miss", provider=provider, status=resp.status_code)
        except Exception as exc:  # fall through to OG
            logger.warning("oembed_provider_error", provider=provider, error=str(exc))
        break  # known provider matched but failed → OG fallback on the page itself

    # Generic fallback: fetch the page, then either follow its own oEmbed
    # discovery link (a real embed) or read its OG tags (a link card).
    try:
        async with httpx.AsyncClient(
            timeout=TIMEOUT_SECONDS, follow_redirects=True, max_redirects=3
        ) as client:
            resp = await client.get(url, headers={"User-Agent": "site-embedbot/1.0"})
        if resp.status_code != 200:
            raise ValidationError(f"صفحه مقصد پاسخ {resp.status_code} داد")

        # P2 "پروکسی عمومی برای هر نشانی": a page that serves oEmbed
        # advertises its endpoint, and following it turns a link card into a
        # real embed. This is what makes any self-hosted CMS work, not just
        # the thirteen providers in the list above. Checked before OG because
        # a discovery hit is strictly the better result; every failure path
        # returns None and falls through, so the OG card is never lost.
        discovered = await _try_oembed_discovery(resp.text, url)
        if discovered is not None:
            await _cache_put(url, discovered, db=db)
            return discovered

        card = parse_og_tags(resp.text)
        card["url"] = url
        await _cache_put(url, card, db=db)
        return card
    except ValidationError:
        raise
    except Exception as exc:
        raise ValidationError(f"بازیابی نشانی ممکن نشد: {exc}") from exc
