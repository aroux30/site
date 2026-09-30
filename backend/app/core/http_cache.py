"""HTTP cache layer: ETag/304 negotiation + optional Redis page cache.

Two orthogonal, independent middlewares:

:``ETagMiddleware`` — conditional-request support for the public API.
Successful (2xx) GET responses under the API prefix, for UNAUTHENTICATED
requests, get a strong ``ETag`` (sha256 of the exact response body). A
request that repeats with a matching ``If-None-Match`` gets ``304 Not
Modified`` with an empty body — same bytes out, a fraction of the bandwidth.
Authenticated requests are skipped wholesale: their bodies are per-user and
their ``Cache-Control: no-store`` must never be second-guessed. Responses
that are not fully buffered (no ``content-length``), are not JSON, or are
already marked ``no-store``/``private`` are passed through untouched, so
streaming endpoints and media files are never read into memory here.

:``PageCacheMiddleware`` — optional full-response cache for anonymous
traffic. OFF by default (``PAGE_CACHE_ENABLED``); when enabled it serves
repeat public GETs under a whitelist of path prefixes from Redis for a short
TTL, so an anonymous traffic spike does not re-run page queries. It never
caches: non-200 responses, responses carrying ``Set-Cookie``, endpoints that
opt out with ``no-store``/``private``, or anything requested with
credentials (same unauthenticated gate as the ETag).

Middleware order (see ``create_app``): both sit OUTSIDE
``SecurityHeadersMiddleware`` so they observe the final ``Cache-Control``
stamp on sensitive prefixes, and a 304 built here copies the security
headers that were already applied one layer down.
"""

from __future__ import annotations

import base64
import hashlib
import json
from typing import TYPE_CHECKING

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.core.cache.redis import cache_get, cache_set
from app.core.config.settings import get_settings

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from fastapi import Request

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# Cookie names that mark a request as session-carrying. Any of these in the
# request's Cookie header (not just a bearer token) opts the request out of
# shared-caching behaviour — per-user responses must not be negotiated or
# stored for anyone else.
_SESSION_COOKIE_NAMES = frozenset(
    {"access_token", "refresh_token", "session", "sessionid"}
)

# Bodies above this size are streamed past untouched; caching/etagging them
# would turn a cheap passthrough into a memory spike.
_MAX_BUFFERED_BODY_BYTES = 2 * 1024 * 1024

# Header names dropped from cached copies: per-response transport metadata
# that must never be replayed from Redis.
_UNCACHEABLE_HEADERS = frozenset(
    {
        "content-length",
        "transfer-encoding",
        "connection",
        "keep-alive",
        "date",
        "server",
        "set-cookie",
    }
)


def _has_auth_credentials(request: Request) -> bool:
    """True when the request carries a bearer token or a session cookie."""
    if request.headers.get("authorization"):
        return True
    cookie_header = request.headers.get("cookie")
    if not cookie_header:
        return False
    for pair in cookie_header.split(";"):
        name = pair.strip().split("=", 1)[0].strip().lower()
        if name in _SESSION_COOKIE_NAMES:
            return True
    return False


def _cache_control_opts(response: Response) -> set[str]:
    """Directives present in the response's Cache-Control header."""
    header = response.headers.get("cache-control", "")
    return {part.strip().lower() for part in header.split(",") if part.strip()}


def _etag_matches(if_none_match: str | None, etag: str) -> bool:
    """RFC 7232 If-None-Match comparison (list, ``*`` and weak-tolerant)."""
    if not if_none_match:
        return False
    for candidate in if_none_match.split(","):
        candidate = candidate.strip()
        if candidate == "*":
            return True
        if candidate.startswith("W/"):
            candidate = candidate[2:]
        if candidate == etag:
            return True
    return False


def _vary_append(response: Response, names: tuple[str, ...]) -> None:
    """Extend the response's Vary header without losing existing entries."""
    existing = response.headers.get("vary", "")
    parts = [p.strip() for p in existing.split(",") if p.strip()] if existing else []
    merged = list(parts)
    for name in names:
        if name not in merged:
            merged.append(name)
    if merged:
        response.headers["vary"] = ", ".join(merged)


async def _read_buffered_body(response: Response) -> bytes | None:
    """Read a fully-buffered response body, or None when not safe to buffer."""
    headers = response.headers
    if "content-length" not in headers:
        return None  # streaming / chunked: never consumed here
    try:
        declared = int(headers["content-length"])
    except (TypeError, ValueError):
        return None
    if declared > _MAX_BUFFERED_BODY_BYTES:
        return None
    body = b"".join([chunk async for chunk in response.body_iterator])
    return body


# ── ETag / 304 ────────────────────────────────────────────────────────────


class ETagMiddleware(BaseHTTPMiddleware):
    """Strong ETag + 304 for unauthenticated successful API GETs."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        api_prefix = get_settings().API_V1_PREFIX
        if (
            request.method != "GET"
            or not request.url.path.startswith(api_prefix)
            or _has_auth_credentials(request)
        ):
            return await call_next(request)

        response = await call_next(request)

        if not (200 <= response.status_code < 300):
            return response
        if response.headers.get("content-type", "").split(";")[0].strip() not in (
            "application/json",
            "application/problem+json",
        ):
            return response  # media, HTML streams, SSE: untouched
        if {"no-store", "private"} & _cache_control_opts(response):
            return response  # endpoint/security headers opted out explicitly

        existing_etag = response.headers.get("etag")
        etag = existing_etag or None
        body = b""
        if etag is None:
            body = await _read_buffered_body(response)
            if body is None:
                return response  # not safely bufferable — passthrough as-is
            etag = '"' + hashlib.sha256(body).hexdigest() + '"'

        if _etag_matches(request.headers.get("if-none-match"), etag):
            not_modified = Response(status_code=304)
            not_modified.headers["etag"] = etag
            # Preserve what downstream already decided about caching, and
            # mark the negotiability for intermediaries.
            for header_name in ("cache-control", "expires"):
                if header_name in response.headers:
                    not_modified.headers[header_name] = response.headers[header_name]
            _vary_append(not_modified, ("Authorization", "Cookie"))
            return not_modified

        if existing_etag is None:
            rebuilt = Response(content=body, status_code=response.status_code)
            rebuilt.raw_headers = list(response.headers.raw)
            rebuilt.headers["etag"] = etag
            _vary_append(rebuilt, ("Authorization", "Cookie"))
            rebuilt.headers["content-length"] = str(len(body))
            return rebuilt

        # Response carried its own ETag (e.g. a page-cache hit): it already
        # matches the body — just pass it through.
        return response


# ── Optional Redis-backed page cache ──────────────────────────────────────


class PageCacheMiddleware(BaseHTTPMiddleware):
    """Serve repeat anonymous GETs on whitelisted prefixes from Redis.

    Strictly opt-in via ``PAGE_CACHE_ENABLED``; when the flag is false the
    middleware is a pure passthrough with zero Redis traffic.
    """

    _KEY_PREFIX = "pagecache:"

    def _is_cacheable_path(self, path: str) -> bool:
        for raw_prefix in get_settings().PAGE_CACHE_PATH_PREFIXES:
            prefix = raw_prefix.rstrip("/")
            if path == prefix or path.startswith(prefix + "/"):
                return True
        return False

    @staticmethod
    def _cache_key(request: Request) -> str:
        # Sorted query pairs give one key per logical resource regardless of
        # parameter order; Accept-Language participates because public content
        # endpoints localize. Only anonymous requests reach this code, so no
        # credential enters the key.
        from urllib.parse import parse_qsl, urlencode

        pairs = sorted(parse_qsl(request.url.query, keep_blank_values=True))
        digest_input = request.url.path + "?" + urlencode(pairs)
        accept_language = request.headers.get("accept-language", "")
        digest = hashlib.sha256(
            (digest_input + "|" + accept_language).encode("utf-8")
        ).hexdigest()
        return f"{PageCacheMiddleware._KEY_PREFIX}{digest}"

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        settings = get_settings()
        if (
            not settings.PAGE_CACHE_ENABLED
            or request.method != "GET"
            or not self._is_cacheable_path(request.url.path)
            or _has_auth_credentials(request)
        ):
            return await call_next(request)

        key = self._cache_key(request)

        raw = await cache_get(key)
        if raw is not None:
            try:
                payload = json.loads(raw)
                body = base64.b64decode(payload["b"])
                cached_headers = [(k.encode(), v.encode()) for k, v in payload["h"]]
                hit = Response(content=body, status_code=200)
                hit.raw_headers = cached_headers
                hit.headers["content-length"] = str(len(body))
                hit.headers["x-cache"] = "HIT"
                return hit
            except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                logger.warning("page_cache_corrupt_entry", key=key)  # fall through

        response = await call_next(request)

        cacheable = (
            response.status_code == 200
            and "set-cookie" not in response.headers
            and response.headers.get("content-type", "").split(";")[0].strip()
            == "application/json"
            and not ({"no-store", "private"} & _cache_control_opts(response))
        )
        if not cacheable:
            return response

        body = await _read_buffered_body(response)
        if body is None:
            return response

        stored_headers = [
            (k.decode("latin-1"), v.decode("latin-1"))
            for k, v in response.headers.raw
            if k.decode("latin-1").lower() not in _UNCACHEABLE_HEADERS
        ]
        payload = json.dumps({"h": stored_headers, "b": base64.b64encode(body).decode()})
        await cache_set(key, payload, ttl=settings.PAGE_CACHE_TTL_SECONDS)

        rebuilt = Response(content=body, status_code=200)
        rebuilt.raw_headers = list(response.headers.raw)
        rebuilt.headers["x-cache"] = "MISS"
        rebuilt.headers["content-length"] = str(len(body))
        return rebuilt
