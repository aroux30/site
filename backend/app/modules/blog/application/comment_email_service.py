"""Comment email delivery — WordPress's wp_notify_postauthor / wp_notify_comment.

What was here before: `notification_service` emitted an in-app event
(`blog.comment.new`) to the post author, the parent commenter and the moderators,
and that was all. A store that answers comments by email had no path at all,
because the event only reaches people who are logged in to the platform.

This module is that missing path, and it carries the one detail the old
list item was really about: the author mail carries `Reply-To` set to the
commenter, so the reply button in a mail client answers them directly.

Two rules the implementation keeps, both from the way WordPress does it:

* a mail only ever goes to an address the commenter *gave*. A username or an
  account id is never guessed into an address, so a signed-in comment with no
  email on file gets no mail rather than a guessed one.
* a failing send never fails the comment. The comment is already stored by the
  time this runs, and losing it because SMTP was down would be worse than a
  missing notification.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class CommentEmailService:
    """Sends the two comment emails. Every method is best-effort."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def notify_post_author(
        self,
        *,
        post_title: str,
        post_slug: str,
        comment_content: str,
        comment_status: str,
        comment_author_name: str | None,
        comment_author_email: str | None,
        author_email: str | None,
        is_pending: bool,
        admin_url: str = "",
        comment_id: str | None = None,
    ) -> bool:
        """Email the post author (and, for a held comment, the moderators).

        ``Reply-To`` is the commenter's address. That is the whole reason this
        exists beyond "notify the author": without it the author has to copy the
        address by hand out of the panel, and in practice does not reply.

        When ``comment_id`` is given the mail also carries WordPress's three
        one-click moderation links. They are minted here rather than in the
        template because the token has to be signed with the app key, and a
        template cannot do that — a template that received a ready URL is the
        only way these can work at all.
        """
        if not author_email:
            # No address to send to. Logged rather than raised: the in-app
            # notification already reached this person.
            logger.info(
                "comment_email_skipped_no_author_address",
                post_title=post_title[:80],
            )
            return False

        manage_url = f"{admin_url.rstrip('/')}/admin/blog" if admin_url else ""
        variables = {
            "post_title": post_title,
            "commenter_name": (comment_author_name or "یک کاربر").strip(),
            "comment_content": comment_content.strip(),
            "comment_status": comment_status,
            "manage_url": manage_url,
            # Empty rather than absent when the id is missing: the template
            # lists these as variables, and a missing one would render a
            # literal `{{approve_url}}` in a mail the moderator will read.
            "approve_url": "",
            "spam_url": "",
            "trash_url": "",
        }
        if comment_id:
            from app.modules.blog.application import comment_moderation_token as cmt

            variables.update(
                approve_url=cmt.build_action_url(comment_id, "approve", admin_url),
                spam_url=cmt.build_action_url(comment_id, "spam", admin_url),
                trash_url=cmt.build_action_url(comment_id, "trash", admin_url),
            )
        return await self._send(
            template_name="comment_new",
            to=author_email,
            reply_to=comment_author_email,
            variables=variables,
        )

    async def notify_commenter_approved(
        self,
        *,
        comment_author_name: str | None,
        comment_author_email: str | None,
        post_title: str,
        post_slug: str,
        comment_content: str,
        site_url: str = "",
    ) -> bool:
        """Tell the commenter their comment went live (wp_notify_comment).

        Only sent when the comment carries an email. A commenter who left none
        has no address to tell, and inventing one is how stores end up mailing
        a stranger.
        """
        if not comment_author_email:
            return False
        return await self._send(
            template_name="comment_approved",
            to=comment_author_email,
            # No Reply-To here: this one is *to* the commenter, and pointing it
            # back at themselves would make "reply" mail the commenter.
            reply_to=None,
            variables={
                "commenter_name": (comment_author_name or "").strip(),
                "post_title": post_title,
                "comment_content": comment_content.strip(),
                "post_url": f"{site_url.rstrip('/')}/blog/{post_slug}" if site_url else "",
            },
        )

    async def _send(
        self,
        *,
        template_name: str,
        to: str,
        reply_to: str | None,
        variables: dict[str, str],
    ) -> bool:
        """Render a built-in template and hand it to the email service.

        Wrapped whole: a template that fails to render, a mail service that is
        not configured, an SMTP timeout — none of them may reach the caller,
        because every caller is running after the comment is already stored.
        """
        try:
            from app.core.config.settings import get_settings
            from app.modules.notifications.application.email_service import (
                default_email_templates,
                render_template,
                send_email,
            )

            # `get_settings()`, not `from app.core.config import settings` —
            # that name is the *module*, and reading an attribute off it returns
            # a default rather than raising, so a setting added tomorrow is
            # silently ignored today.
            store_name = getattr(get_settings(), "store_name", None)
            content = default_email_templates(store_name)[template_name]
            rendered = render_template(content, variables)

            sent, _log = await send_email(
                self.db,
                recipient=to,
                subject=rendered.subject,
                html_body=rendered.html,
                text_body=rendered.text,
                template=template_name,
                # Only when the commenter gave one; the builder validates it
                # against header injection before it reaches the wire.
                reply_to=(reply_to or "").strip() or None,
            )
            if not sent:
                logger.warning(
                    "comment_email_not_delivered",
                    extra={
                        "template_name": template_name,
                        "recipient": to[:64],
                    },
                )
            return sent
        except Exception:  # noqa: BLE001 — a notification must never break the comment
            logger.warning(
                "comment_email_failed",
                exc_info=True,
                extra={
                    "template_name": template_name,
                    "recipient": to[:64],
                },
            )
            return False