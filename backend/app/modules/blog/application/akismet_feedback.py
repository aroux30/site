"""Akismet feedback — what a moderator decided, told back to the service.

`akismet_client` can classify a comment and can submit a verdict. Neither is
worth anything on its own: a check that never learns is permanently as good as
the day it was configured, and on a store's comment stream the moderator's
approve/trash is the only ground truth that exists.

The decision arrives through `moderate_comment`, and every path that records one
funnels here — the admin table, the moderation tab, and the one-click links an
email carries. That last one matters: WordPress's `pluggable.php` moderation
URLs are exactly where a spammer's comment gets confirmed as spam by a real
person clicking "Spam", and it is the highest-value single training signal the
service gets.

Nothing here is allowed to change the decision. The local row is already
committed by the time this runs, and a failed submission is logged and dropped:
the comment is stored, the moderator's work is not repeated, and the signal is
simply lost for that one comment.
"""

from __future__ import annotations

import uuid
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.blog.application.akismet_client import (
    API_KEY_OPTION,
    API_URL_OPTION,
    AkismetClient,
)
from app.modules.blog.domain.models import BlogComment, CommentStatus

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

#: Which moderator decisions are worth reporting, and how each is spelled to
#: Akismet. A trash is not treated as spam: an operator trashes a comment for
#: being rude or off-topic as often as for being an advert, and reporting every
#: one as spam teaches the service to distrust the word "you" in any tone.
_SPAM_DECISIONS = (CommentStatus.SPAM,)


async def report_moderation(
    db: AsyncSession,
    comment: BlogComment,
    *,
    status: CommentStatus,
    client: AkismetClient | None = None,
) -> bool:
    """Submit one moderator decision to Akismet.

    Returns whether a submission was made and accepted. ``False`` means either
    the site has no key — the WordPress behaviour, and the common case — or the
    call did not land; both are logged and neither raises.
    """
    api_key = await _option(db, API_KEY_OPTION)
    if not api_key or not str(api_key).strip():
        return False

    blog_url = await _site_url(db)
    if not blog_url:
        logger.warning("akismet_feedback_skipped_no_site_url")
        return False

    akismet = client or AkismetClient()
    try:
        accepted = await akismet.submit_feedback(
            api_key=str(api_key).strip(),
            blog_url=blog_url,
            user_ip=comment.author_ip or "",
            user_agent=comment.author_user_agent or "",
            comment_content=comment.content or "",
            is_spam=status in _SPAM_DECISIONS,
            api_url=await _option(db, API_URL_OPTION, default=""),
        )
    except Exception as exc:  # noqa: BLE001
        # The decision is already stored. A third-party failure must not turn a
        # completed moderation action into an error the operator sees.
        logger.warning(
            "akismet_feedback_error", comment_id=str(comment.id), error=str(exc)
        )
        return False

    if accepted:
        logger.info(
            "akismet_feedback_submitted",
            comment_id=str(comment.id),
            is_spam=status in _SPAM_DECISIONS,
        )
    return accepted


async def _option(db: AsyncSession, key: str, default: str = "") -> str:
    from app.modules.settings.application.site_options_service import SiteOptionsService

    return str(await SiteOptionsService.get(db, key, default) or default)


async def _site_url(db: AsyncSession) -> str:
    return str(await _option(db, "site_url", "") or "").rstrip("/")


async def report_by_id(
    db: AsyncSession,
    comment_id: uuid.UUID,
    *,
    status: CommentStatus,
    client: AkismetClient | None = None,
) -> bool:
    """The same, for callers that hold an id rather than the row.

    Returns False for a comment that no longer exists — the moderator action is
    still valid, there is simply nothing left to describe to the service.
    """
    comment = await db.get(BlogComment, comment_id)
    if comment is None:
        return False
    return await report_moderation(db, comment, status=status, client=client)


def describe() -> dict[str, Any]:
    """What this module is, for the admin settings screen.

    It reports the two options and the states honestly rather than implying the
    service is running: with no key configured every one of these returns
    without a network call.
    """
    return {
        "key_option": API_KEY_OPTION,
        "url_option": API_URL_OPTION,
        "enabled_by": API_KEY_OPTION,
        "spam_decisions": [s.value for s in _SPAM_DECISIONS],
        "note": (
            "کلید خالی یعنی بدون سرویس‌دهی بیرونی؛ هیچ درخواستی ارسال نمی‌شود و "
            "فیلتر محلی تصمیم می‌گیرد — همان رفتار وردپرس بدون کلید."
        ),
    }