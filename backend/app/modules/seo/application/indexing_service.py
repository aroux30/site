"""Instant Indexing — IndexNow submission (Rank Math's Instant Indexing).

IndexNow is a key-based protocol: the site hosts a key file at
``/{key}.txt`` containing the key, and submits URLs to the shared endpoint
``https://api.indexnow.org/indexnow`` (or a search-engine-specific one).
Bing and Yandex consume it directly; the key file is what proves the
submitter owns the host.

Key facts that shape this module:

- **The key is public.** It sits in a readable text file and in every request
  URL — it is an ownership token, not a secret. site_options storage is fine.
- **Submissions are batched** (up to 10,000 URLs per request; this module caps
  far lower) and rate-limit tolerant: a 429 means "slow down", not "broken".
- **Google does NOT use IndexNow.** Its Indexing API is a separate,
  service-account-authenticated channel that only covers JobPosting and
  BroadcastEvent for general sites. The Google half here is therefore an
  interface + honest "not connected" state; no request is ever sent to Google
  without a real credential, because a credential-less request fails silently
  and burns quota for nothing.
"""

from __future__ import annotations

import json
import secrets
from typing import TYPE_CHECKING, Any

import httpx
import structlog

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

#: The shared endpoint. Search engines agreed on one; a per-engine endpoint
#: exists but the shared one fans out to all participants.
INDEXNOW_ENDPOINT = "https://api.indexnow.org/indexnow"

#: IndexNow accepts up to 10,000 URLs; this cap keeps one publish from
#: producing a huge request and matches Rank Math's practical batch size.
MAX_URLS_PER_REQUEST = 500

#: The path the key file is ACTUALLY served at, relative to the site origin.
#: The protocol allows any keyLocation as long as it is fetchable — and this
#: is where the route lives (public SEO router, proxied by the storefront's
#: /api/v1 rewrite). Advertising the domain root here would send IndexNow's
#: verifier to a 404 and every submission would be rejected.
KEY_FILE_PATH_TEMPLATE = "/api/v1/seo/indexnow/{key}.txt"

_REQUEST_TIMEOUT = 10.0

KEY_OPTION = "indexnow_key"
ENABLED_OPTION = "indexnow_enabled"


def key_file_url(base: str, key: str) -> str:
    """The absolute keyLocation for a submission — one builder, so the
    payload and the status endpoint can never advertise different paths."""
    return f"{base.rstrip('/')}{KEY_FILE_PATH_TEMPLATE.format(key=key)}"


def generate_key() -> str:
    """A fresh IndexNow key: 32 lowercase hex chars.

    The protocol requires 8-128 hex-ish characters; 32 hex is what the
    IndexNow docs use in examples and what Rank Math generates.
    """
    return secrets.token_hex(16)


async def get_or_create_key(db: AsyncSession) -> str:
    """The site's IndexNow key, generating and storing one on first use."""
    from app.modules.settings.application.site_options_service import (
        SiteOptionsService,
    )

    existing = await SiteOptionsService.get(db, KEY_OPTION)
    if existing:
        return existing
    key = generate_key()
    await SiteOptionsService.set(db, KEY_OPTION, key)
    logger.info("indexnow_key_generated")
    return key


async def is_enabled(db: AsyncSession) -> bool:
    from app.modules.settings.application.site_options_service import (
        SiteOptionsService,
    )

    value = await SiteOptionsService.get(db, ENABLED_OPTION, "0") or "0"
    return value in ("1", "true", "yes", "on")


async def submit_urls(db: AsyncSession, urls: list[str]) -> dict[str, Any]:
    """Submit URLs to IndexNow; returns a per-call outcome.

    Never raises: indexing is additive, and a publish must not fail because a
    search engine's endpoint is down (the same rule the low-stock automation
    trigger follows). The outcome says exactly what happened so the admin log
    is truthful — ``skipped`` reasons included.
    """
    from app.modules.settings.application.site_options_service import (
        SiteOptionsService,
        public_base_url,
    )

    if not urls:
        return {"submitted": 0, "status": "skipped", "reason": "no_urls"}

    if not await is_enabled(db):
        return {"submitted": 0, "status": "skipped", "reason": "disabled"}

    key = await get_or_create_key(db)
    base = await public_base_url(db)
    host = httpx.URL(base).host if base else ""
    if not host:
        return {"submitted": 0, "status": "skipped", "reason": "no_site_url"}

    batch = urls[:MAX_URLS_PER_REQUEST]
    payload = {
        "host": host,
        "key": key,
        # The real route path, not the domain root — see KEY_FILE_PATH_TEMPLATE.
        "keyLocation": key_file_url(base, key),
        "urlList": batch,
    }

    try:
        async with httpx.AsyncClient(
            timeout=_REQUEST_TIMEOUT,
            # Same reason as the sideload client: this machine's ambient proxy
            # settings must not silently take over a server-side fetch.
            trust_env=False,
        ) as client:
            response = await client.post(
                INDEXNOW_ENDPOINT,
                content=json.dumps(payload),
                headers={"Content-Type": "application/json; charset=utf-8"},
            )
    except Exception as exc:  # noqa: BLE001 — additive side effect
        logger.warning("indexnow_submit_failed", error=str(exc)[:200])
        return {"submitted": 0, "status": "error", "reason": str(exc)[:200]}

    # 200 = accepted; 202 = accepted, key validation pending. 422 = the
    # request shape is wrong (key/URLs mismatch) — reported, not retried.
    if response.status_code in (200, 202):
        logger.info("indexnow_submitted", count=len(batch), status=response.status_code)
        return {"submitted": len(batch), "status": "ok", "http_status": response.status_code}
    if response.status_code == 429:
        return {
            "submitted": 0,
            "status": "rate_limited",
            "http_status": 429,
            "reason": "too_many_requests",
        }
    logger.warning(
        "indexnow_rejected", status=response.status_code, body=response.text[:200]
    )
    return {
        "submitted": 0,
        "status": "rejected",
        "http_status": response.status_code,
        "reason": response.text[:200],
    }


async def submit_post_published(db: AsyncSession, *, slug: str) -> dict[str, Any]:
    """Submit one freshly published post's URL. Called from the publish hook."""
    from app.modules.settings.application.site_options_service import public_base_url

    base = (await public_base_url(db)).rstrip("/")
    return await submit_urls(db, [f"{base}/blog/{slug}"])


# ── Google Indexing API — honest skeleton ──────────────────────────────────


async def google_status(db: AsyncSession) -> dict[str, Any]:
    """Whether Google Indexing API credentials are configured.

    Deliberately a status read, not an integration: the API needs a service
    account with a private key (and even then only covers JobPosting /
    BroadcastEvent for general sites). Reporting "not connected" truthfully is
    the feature; a credential-less request would fail silently and the UI
    would claim URLs were submitted.
    """
    from app.modules.settings.application.site_options_service import (
        SiteOptionsService,
    )

    credentials = await SiteOptionsService.get(db, "google_indexing_credentials")
    return {
        "connected": bool(credentials),
        "note": (
            "برای ارسال به Google، حساب سرویس (service account) لازم است — "
            "محدود به JobPosting و BroadcastEvent. IndexNow برای Bing و Yandex کافی است."
        ),
    }
