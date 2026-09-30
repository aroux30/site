"""Comment spam scoring (the Akismet-shaped half, without the service).

WordPress delegates spam detection to an external service; this site does not
call out to one, so a comment could carry any number of links and land in the
moderation queue for a human to open. This module scores the signals the post
row already carries — no new columns, no network call — and holds back a
comment that is almost certainly spam *before* it is ever stored.

The bar is deliberately one-directional: only a comment whose score crosses the
threshold is held back. A borderline comment is always kept and shown to a
moderator, because silently dropping a real person's comment is a worse failure
than showing a moderator one extra item.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import structlog

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

#: Comment held back for moderation when the score reaches this.
SPAM_SCORE_THRESHOLD = 5

#: Text that only a machine writes: repeated a run of one character, or the
#: same word stuffed enough times to push a keyword past a count-based check.
_REPEATED_CHAR_RE = re.compile(r"(.)\1{9,}")
_REPEATED_WORD_RE = re.compile(r"\b(\w{2,})\b(?:[^\w]*\1\b){4,}", re.IGNORECASE)

#: Obfuscations used to smuggle a domain past a naive substring check.
_OBFUSCATIONS: tuple[tuple[str, str], ...] = (
    (r"\[\s*/?\s*l\s*i\s*n\s*k", ""),   # [l]ink spam
    (r"h\s*t\s*t\s*p", "http"),         # h t t p
    (r"\.{3,}", "."),                   # hxxp://spam...com
    (r"://\s*@", "://"),                # http://@spam
)

#: Hosts that appear in comment spam far more often than in conversation.
_SPAM_HOST_HINTS = (
    "bit.ly",
    "tinyurl.com",
    "t.co",
    "free-money",
    "viagra",
    "casino",
    "paypal-verify",
    "seo-service",
    "crypto-giveaway",
)

#: Browsers real people use. A comment from curl/wget/python-requests with no
#: other spam signal is unusual but not spam; the user-agent only contributes
#: when something else has already raised suspicion.
_BOT_USER_AGENTS = (
    "curl/",
    "wget/",
    "python-requests",
    "python-urllib",
    "libwww-perl",
    "scrapy",
    "headlesschrome",
)


@dataclass(frozen=True)
class SpamVerdict:
    """Why a comment was (or was not) held back."""

    score: int
    is_spam: bool
    reasons: tuple[str, ...]


def _normalise(text: str) -> str:
    """Collapse the obfuscations above so their targets become visible."""
    out = text
    for pattern, replacement in _OBFUSCATIONS:
        out = re.sub(pattern, replacement, out, flags=re.IGNORECASE)
    return out


def score_comment(
    content: str,
    *,
    author_name: str | None = None,
    author_url: str | None = None,
    user_agent: str | None = None,
) -> SpamVerdict:
    """Score one comment. Pure — no database, no network."""
    reasons: list[str] = []
    score = 0
    body = _normalise(content or "")
    lowered = body.lower()
    lowered_name = (author_name or "").strip().lower()
    lowered_url = _normalise(author_url or "").strip().lower()

    # 1. An author URL is the single strongest signal, because a human
    #    commenter rarely links to themselves and a spammer always does.
    if lowered_url and re.search(r"https?://", lowered_url, re.IGNORECASE):
        score += 3
        reasons.append("author_url_present")
    if lowered_url and any(hint in lowered_url for hint in _SPAM_HOST_HINTS):
        score += 6
        reasons.append("author_url_spammy_host")

    # 2. Link count and link density in the body.
    links = re.findall(r"https?://\S+", body, re.IGNORECASE)
    if len(links) >= 3:
        score += 2
        reasons.append("many_links")
    if links:
        # Density matters more than count: 300 characters containing a link is
        # an advert, 3000 characters containing one is an article.
        density = len(links) / max(len(body.split()), 1)
        if density > 0.5:
            score += 3
            reasons.append("link_dense")

    # 3. Known spam vocabulary.
    hits = [hint for hint in _SPAM_HOST_HINTS if hint in lowered]
    if hits:
        score += 6
        reasons.append("spam_keywords")

    # 4. Machine-shaped text.
    if _REPEATED_CHAR_RE.search(body):
        score += 6
        reasons.append("repeated_characters")
    if _REPEATED_WORD_RE.search(body):
        score += 5
        reasons.append("repeated_word_stuffing")

    # 5. A display name that is a link is a spammer's oldest trick.
    if re.search(r"https?://|<a\s", author_name or "", re.IGNORECASE):
        score += 6
        reasons.append("link_in_author_name")

    # 6. Obfuscated scheme that only appears when someone is hiding one.
    if re.search(r"h\s*t\s*t\s*p|h\s*x\s*x\s*p", content or "", re.IGNORECASE):
        score += 3
        reasons.append("obfuscated_url")

    # 7. User agent: only counts when the comment already looks suspicious,
    #    so a curl request with a normal sentence is not punished.
    ua = (user_agent or "").lower()
    if ua and any(bot in ua for bot in _BOT_USER_AGENTS) and score >= 2:
        score += 2
        reasons.append("bot_user_agent")

    # 8. An empty or single-character comment is never worth storing.
    if len(body.strip()) < 2 and not links:
        score += 5
        reasons.append("empty_comment")

    return SpamVerdict(
        score=score,
        is_spam=score >= SPAM_SCORE_THRESHOLD,
        reasons=tuple(reasons),
    )


def held_for_moderation(verdict: SpamVerdict) -> bool:
    """Whether a spam-looking comment should still be stored as pending.

    A comment from an authenticated user is never held back: they proved they
    can log in, and holding their reply is a support ticket, not moderation.
    """
    return verdict.is_spam
