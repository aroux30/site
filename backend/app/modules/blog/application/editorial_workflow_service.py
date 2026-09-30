"""Multi-author editorial workflow (WordPress parity).

Adds a PENDING_REVIEW status to the blog post workflow so contributors
can submit posts that editors must approve before publishing.

Workflow: DRAFT -> PENDING_REVIEW -> PUBLISHED (or back to DRAFT)
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

import structlog
from fastapi import HTTPException, status
from sqlalchemy import select

from app.core.security.object_capabilities import OBJECT_RULES, caller_id, require_object_capability
from app.modules.blog.domain.models import BlogPost, BlogPostStatus

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class EditorialWorkflowService:
    """Multi-author submission and approval workflow.

    ``actor_payload`` is the authenticated caller's token payload. It is
    required on the three methods that change another author's work, because
    the route guard in front of them only proves ``blog:write`` — which every
    contributor holds. Without it a contributor could submit their own draft
    and then approve it, publishing their own work through a workflow whose
    whole purpose is that somebody else signs off.
    """

    def __init__(self, db: "AsyncSession", *, actor_payload: dict[str, Any] | None = None) -> None:
        self.db = db
        self.actor_payload = actor_payload

    async def _require_reviewer(self, post: BlogPost, action: str) -> None:
        """Refuse self-approval: a post may not be signed off by its author.

        This is deliberately *not*
        :func:`require_object_capability`. That helper is the right check for
        editing, where ownership is a legitimate shortcut — the author may
        always edit their own draft. Here ownership is the exact thing being
        tested, so the helper would wave the case through and the workflow
        would approve itself.

        The rule WordPress draws is the same one: approving is resolved against
        ``edit_others_posts``, never against ``edit_posts``. A caller must
        therefore hold ``blog:write`` (to be a writer at all) **and**
        ``blog:write_others`` (to sign off on work that is not theirs). A
        contributor holds the first and not the second, which is precisely the
        author/contributor split — and precisely the loop this closes.
        """
        if self.actor_payload is None:
            return

        from app.core.security.object_capabilities import capabilities_of, is_superuser

        if is_superuser(self.actor_payload):
            return

        capabilities = await capabilities_of(self.actor_payload)
        missing = [c for c in ("edit_posts", "edit_others_posts") if c not in capabilities]
        if not missing:
            return

        owner = getattr(post, "author_id", None)
        if owner is not None and owner == caller_id(self.actor_payload):
            detail = (
                "You cannot approve your own post; approval is a second pair of "
                "eyes by design."
            )
        else:
            detail = "Missing required capability: " + ", ".join(missing)

        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)

    async def submit_for_review(self, post_id: uuid.UUID) -> dict[str, str]:
        """Move a draft post to pending review status."""
        post = await self.db.get(BlogPost, post_id)
        if not post:
            return {"error": "Post not found"}
        if post.status != BlogPostStatus.DRAFT:
            return {"error": "Only drafts can be submitted for review"}
        # Submission is the author's own act, but it is not *only* theirs: it
        # moves someone else's draft into another person's review queue, which
        # is a write to their workflow. Ownership is therefore required — the
        # check is the same per-object matrix used everywhere else, and it lets
        # an author submit their own draft as before.
        if self.actor_payload is not None:
            from app.core.security.object_capabilities import (
                OBJECT_RULES,
                require_object_capability,
            )

            await require_object_capability(
                self.actor_payload, post, OBJECT_RULES["posts"], owner_fields=("author_id",)
            )
        post.status = BlogPostStatus.PENDING_REVIEW
        await self.db.commit()
        logger.info("post_submitted_for_review", post_id=str(post_id))
        return {"status": "pending_review", "post_id": str(post_id)}

    async def approve_post(self, post_id: uuid.UUID) -> dict[str, str]:
        """Approve a pending post and publish it."""
        post = await self.db.get(BlogPost, post_id)
        if not post:
            return {"error": "Post not found"}
        # Only a post actually awaiting review may be approved. Approving an
        # archived post would silently publish it and set published_at.
        if post.status != BlogPostStatus.PENDING_REVIEW:
            return {"error": "Only posts pending review can be approved"}
        # Checked after the status gate so the error a caller sees names the
        # real problem: a post that is not awaiting review cannot be approved
        # for any caller, while the self-approval rule is about who may sign off.
        await self._require_reviewer(post, "approve")
        post.status = BlogPostStatus.PUBLISHED
        from datetime import UTC, datetime
        if post.published_at is None:
            post.published_at = datetime.now(UTC)
        await self.db.commit()
        logger.info("post_approved", post_id=str(post_id))
        return {"status": "published", "post_id": str(post_id)}

    async def reject_post(self, post_id: uuid.UUID, reason: str = "") -> dict[str, str]:
        """Reject a pending post back to draft.

        Deliberately *not* behind ``_require_reviewer``: rejecting does not
        publish anything, it returns the post to its author. An author must be
        able to withdraw their own submission, otherwise a mistaken submit is
        stuck awaiting an editor who may not exist. The publishing step is the
        one that needs separation.
        """
        post = await self.db.get(BlogPost, post_id)
        if not post:
            return {"error": "Post not found"}
        if post.status != BlogPostStatus.PENDING_REVIEW:
            return {"error": "Only posts pending review can be rejected"}
        post.status = BlogPostStatus.DRAFT
        await self.db.commit()
        logger.info("post_rejected", post_id=str(post_id), reason=reason)
        return {"status": "draft", "post_id": str(post_id), "reason": reason}

    async def get_pending_posts(self, page: int = 1, page_size: int = 20) -> list[dict]:
        """List posts awaiting editorial approval."""
        stmt = (
            select(BlogPost)
            .where(BlogPost.status == BlogPostStatus.PENDING_REVIEW)
            .where(BlogPost.deleted_at.is_(None))
            .order_by(BlogPost.updated_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        posts = (await self.db.execute(stmt)).scalars().all()
        return [
            {"id": str(p.id), "title": p.title, "slug": p.slug, "updated_at": str(p.updated_at)}
            for p in posts
        ]
