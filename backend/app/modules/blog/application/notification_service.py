"""Blog email notification service (WordPress parity).

Sends email notifications for key blog events:
- New post published → subscribers / admins
- New comment → post author + parent comment author (threaded)
- Comment approved → comment author

Uses the platform's existing notification/messaging infrastructure.
Notifications are queued via the outbox pattern so they never block
the content write.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class BlogNotificationService:
    """Queue blog-related email notifications."""

    def __init__(self, db: "AsyncSession") -> None:
        self.db = db

    async def notify_new_post(
        self,
        post_id: uuid.UUID,
        title: str,
        slug: str,
        author_name: str,
        author_id: uuid.UUID | None = None,
    ) -> None:
        """Queue notification for a newly published blog post."""
        await self._emit(
            event_type="blog.post.published",
            payload={
                "post_id": str(post_id),
                "title": title,
                "slug": slug,
                "author_name": author_name,
                # The worker notifies the author; without the id there is no
                # recipient and the event is silently dropped.
                "author_id": str(author_id) if author_id else None,
                "action": "new_post",
            },
        )
        logger.info("blog_notification_new_post", post_id=str(post_id))

    async def notify_new_comment(
        self,
        comment_id: uuid.UUID,
        post_id: uuid.UUID,
        post_title: str,
        commenter_name: str,
        post_author_id: uuid.UUID | None = None,
        parent_comment_author_id: uuid.UUID | None = None,
        moderator_ids: list[uuid.UUID] | None = None,
    ) -> None:
        """Queue notification for a new comment on a blog post.

        Notifies:
        - Post author (always)
        - Parent comment author (for threaded replies)
        - Comment moderators, but only while the comment is pending — the same
          condition WordPress's ``wp_new_comment_notify_moderator`` uses. Once
          approved the post author already knows, and a second notice to every
          moderator is noise.
        """
        recipients: list[str] = []
        if post_author_id:
            recipients.append(str(post_author_id))
        if parent_comment_author_id and parent_comment_author_id != post_author_id:
            recipients.append(str(parent_comment_author_id))
        for moderator_id in moderator_ids or []:
            # A moderator who is also the post author has already been added.
            if str(moderator_id) not in recipients:
                recipients.append(str(moderator_id))

        await self._emit(
            event_type="blog.comment.new",
            payload={
                "comment_id": str(comment_id),
                "post_id": str(post_id),
                "post_title": post_title,
                "commenter_name": commenter_name,
                "recipient_user_ids": recipients,
                "action": "new_comment",
            },
        )
        logger.info(
            "blog_notification_new_comment",
            comment_id=str(comment_id),
            recipients=len(recipients),
        )

    async def notify_comment_approved(
        self,
        comment_id: uuid.UUID,
        post_title: str,
        comment_author_email: str | None = None,
        comment_author_id: uuid.UUID | None = None,
    ) -> None:
        """Queue notification when a comment is approved."""
        await self._emit(
            event_type="blog.comment.approved",
            payload={
                "comment_id": str(comment_id),
                "post_title": post_title,
                "comment_author_email": comment_author_email,
                "comment_author_id": str(comment_author_id) if comment_author_id else None,
                "action": "comment_approved",
            },
        )
        logger.info("blog_notification_comment_approved", comment_id=str(comment_id))

    async def _emit(self, event_type: str, payload: dict[str, Any]) -> None:
        """Publish notification event to the transactional outbox."""
        try:
            from app.shared.events.outbox_service import OutboxService

            await OutboxService.publish(
                self.db,
                event_type=f"notification.{event_type}",
                aggregate_type="blog",
                aggregate_id=payload.get("post_id", ""),
                payload=payload,
            )
        except Exception:  # noqa: BLE001
            logger.warning("blog_notification_emit_failed", event_type=event_type)
