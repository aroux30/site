"""Akismet client — the external half of WordPress's spam decision.

WordPress ships no spam filter of its own: `wp_check_comment()` calls Akismet
when a key is configured, and skips it entirely when there is not one, so an
unconfigured site publishes straight through. This module keeps that shape —
no key, no call — but makes the key an operator-editable site option
(``spam_akismet_api_key``, beside the ``media_watermark_*`` ones) rather than an
environment secret, because the key belongs to the site being moderated and
WordPress stores it the same way.

Three things are deliberate and worth stating:

* **The verdict is advisory, never final.** `spam_filter.py` already scores a
  comment locally; this adds a second opinion. When Akismet disagrees with the
  heuristic, the local engine still decides, and the disagreement is recorded.
  An external service being unavailable must never decide whether a real
  person's comment is published.
* **Failure is "no opinion", not "spam".** A timeout or a 500 from the service
  returns `None`, which the caller treats exactly like "not configured". The
  alternative — failing closed — would let one slow third party hold every
  comment on the site.
* **The network call is injectable.** `_transport` defaults to httpx; a test
  passes a fake and asserts the request was never made when the site has no key.
  This client has never been run against the live service — no key, no account —
  so the only honest verification available is the one that does not touch it.

The feedback loop — telling Akismet what a moderator actually decided — lives in
`akismet_feedback`, which this client only feeds.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Protocol

import structlog

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

#: WordPress core's default host. Overridable through the same site option, so a
#: self-hosted Akismet (the recommended setup for a store that cannot leak
#: comment text to a third party) needs no code change.
AKISMET_API_URL = "https://rest.akismet.com/1.1/"

#: Akismet answers in milliseconds and is called inline with the request that
#: submitted the comment. Long enough not to fail on a slow call, short enough
#: that a hung socket cannot hold a user's POST open.
REQUEST_TIMEOUT_SECONDS = 3.0

#: The site option the key is read from.
API_KEY_OPTION = "spam_akismet_api_key"
#: The site option the host is read from, empty means the public service.
API_URL_OPTION = "spam_akismet_api_url"

#: Akismet's own vocabulary. "true" means spam, "false" means ham, "undefined"
#: means it will not classify it — which is an opinion of "no opinion", not a
#: verdict.
SPAM = "true"
HAM = "false"


class Transport(Protocol):
    """The seam a test replaces. One method, so a fake is three lines."""

    async def post_form(
        self, url: str, data: dict[str, str], *, timeout: float
    ) -> tuple[int, str]: ...


@dataclass(frozen=True)
class AkismetVerdict:
    """What the service said, kept alongside *why* so it can be recorded."""

    is_spam: bool
    raw: str
    reason: str = ""

    def as_reasons(self) -> tuple[str, ...]:
        return (f"akismet:{self.raw}",) if self.raw else ()


class HttpxTransport:
    """The real transport. Kept behind the same `post_form` seam as the test's
    fake so there is one calling convention rather than two."""

    async def post_form(
        self, url: str, data: dict[str, str], *, timeout: float
    ) -> tuple[int, str]:
        import httpx

        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, data=data)
            return response.status_code, response.text


class AkismetClient:
    """Calls Akismet, or explains why it did not."""

    def __init__(self, transport: Transport | None = None) -> None:
        # Resolved per call, never at import: a test that swaps the transport
        # after the module is imported would otherwise keep the real one.
        self._transport: Transport = transport or HttpxTransport()

    async def check_comment(
        self,
        *,
        api_key: str,
        blog_url: str,
        user_ip: str,
        user_agent: str,
        comment_content: str,
        comment_author: str = "",
        comment_author_email: str = "",
        comment_author_url: str = "",
        comment_type: str = "comment",
        is_test: bool = False,
        api_url: str = AKISMET_API_URL,
    ) -> AkismetVerdict | None:
        """Ask Akismet about one comment.

        Returns `None` — not a verdict — when there is no key or the call did
        not produce an answer. The caller must treat that as "no opinion", and
        the type makes it hard to mistake for `is_spam=False`: only an explicit
        ``false`` from the service clears a comment, and only a local engine can
        do that without a key.
        """
        if not api_key or not api_key.strip():
            return None
        if not blog_url:
            return None

        base = api_url or AKISMET_API_URL
        if not base.endswith("/"):
            base += "/"
        endpoint = f"{base}comment-check"

        data = {
            "blog": blog_url,
            "user_ip": user_ip or "",
            "user_agent": user_agent or "",
            "comment_content": comment_content,
            "comment_author": comment_author,
            "comment_author_email": comment_author_email,
            "comment_author_url": comment_author_url,
            "comment_type": comment_type,
            "blog_charset": "UTF-8",
            "blog_lang": "fa",
        }
        if is_test:
            data["is_test"] = "1"

        try:
            status, body = await self._transport.post_form(
                f"{endpoint}?key={api_key}",
                data,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        except (asyncio.TimeoutError, OSError) as exc:
            # A third party being slow is our problem to absorb, not the
            # commenter's. Failing closed here would let one hung socket decide
            # that every comment on the store is spam.
            logger.warning("akismet_unreachable", error=f"{type(exc).__name__}")
            return None
        except Exception as exc:  # a client bug must not take the comment with it
            logger.warning("akismet_call_failed", error=f"{type(exc).__name__}")
            return None

        if status != 200:
            logger.warning("akismet_bad_status", status=status)
            return None

        verdict = (body or "").strip().lower()
        # Akismet documents three answers. `undefined` means it declines to
        # classify, which is exactly the "no opinion" case and must not be read
        # as ham — a service that changed its mind would silently start letting
        # spam through if `undefined` were treated as `false`.
        if verdict not in (SPAM, HAM):
            logger.info("akismet_undecided", raw=verdict[:32])
            return None

        return AkismetVerdict(is_spam=verdict == SPAM, raw=verdict)

    async def submit_feedback(
        self,
        *,
        api_key: str,
        blog_url: str,
        user_ip: str,
        user_agent: str,
        comment_content: str,
        is_spam: bool,
        api_url: str = AKISMET_API_URL,
    ) -> bool:
        """Tell Akismet what a human decided about this comment.

        This is the half that makes the service worth having: the check is only
        as good as what it learns, and a moderator's approve/trash is the only
        ground truth available.

        Returns whether the submission was accepted. Callers deliberately do not
        retry — the decision is already stored locally, and a moderator's time
        is not worth spending on a request that failed.
        """
        if not api_key or not api_key.strip() or not blog_url:
            return False

        base = api_url or AKISMET_API_URL
        if not base.endswith("/"):
            base += "/"
        endpoint = f"{base}submit-spam" if is_spam else f"{base}submit-ham"

        try:
            status, _ = await self._transport.post_form(
                f"{endpoint}?key={api_key}",
                {
                    "blog": blog_url,
                    "user_ip": user_ip or "",
                    "user_agent": user_agent or "",
                    "comment_content": comment_content,
                    "blog_charset": "UTF-8",
                },
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        except Exception as exc:
            logger.info("akismet_feedback_failed", error=type(exc).__name__)
            return False

        if status != 200:
            logger.info("akismet_feedback_rejected", status=status)
            return False
        return True


#: What the site is reachable at, as Akismet requires. Built from the site's own
#: option rather than a request header, because Akismet compares it against the
#: configured site URL and a proxy's `X-Forwarded-Host` is attacker-controlled.
async def site_url(db: Any) -> str:
    from app.modules.settings.application.site_options_service import SiteOptionsService

    url = await SiteOptionsService.get(db, "site_url", "") or ""
    return str(url).rstrip("/")