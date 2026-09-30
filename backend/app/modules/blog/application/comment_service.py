"""Comment service: moderation, threading, and CRUD for polymorphic comments.

Comments attach to blog posts (legacy ``post_id`` addressing) or CMS pages
(polymorphic ``resource_type``/``resource_id`` addressing) — WordPress parity,
where wp_comments serves both. Threading enforces the site's
``thread_comments_depth`` setting at creation time and nests replies in list
responses; page comments honour the ``comment_moderation`` site option.
"""

from __future__ import annotations

import math
import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import func, select

from app.core.exceptions.handlers import NotFoundError, ValidationError
from app.modules.blog.application.spam_filter import score_comment
from app.modules.blog.domain.models import (
    COMMENT_RESOURCE_BLOG_POST,
    COMMENT_RESOURCE_CMS_PAGE,
    BlogComment,
    BlogPost,
    CommentStatus,
)
from app.modules.blog.schemas.blog import (
    BlogCommentAdminResponse,
    BlogCommentCreate,
    BlogCommentListResponse,
    BlogCommentResponse,
    BlogCommentUpdate,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# Default when the thread_comments_depth option is unset; the option is read
# bounded to [1, 10] so an operator typo can't blow up recursion.
DEFAULT_THREAD_DEPTH = 3
# Hard stop for the parent-chain walk: a corrupt (cyclic) parent chain must
# not turn a comment insert into an infinite loop.
MAX_DEPTH_WALK = 25

_MODERATION_ON = {"1", "true", "yes", "on"}


def _keyword_list(raw: str | None) -> list[str]:
    """Split an operator's keyword option into lowercase terms.

    Newline-separated (WordPress's format), also accepting commas so either
    convention works. Blank lines are dropped and terms are lowercased, since
    the caller matches against an already-lowercased haystack. A single-character
    term is ignored: it would match almost any comment.
    """
    if not raw:
        return []
    parts = raw.replace(",", "\n").split("\n")
    return [p.strip().lower() for p in parts if len(p.strip()) > 1]

#: Markup a comment may keep. Deliberately tiny: inline emphasis, a quoted
#: line, a link, and the line-break tags that carry multi-line prose. A reader
#: comment never legitimately contains a table, an image, an iframe, a form or
#: a heading, and allowing any of those is what turns "escape on render" into
#: "safe by accident" — the renderer's escaping is a property of the component
#: in front of it, not of the stored value.
_COMMENT_ALLOWED_TAGS: frozenset[str] = frozenset(
    {
        "a",
        "b",
        "strong",
        "i",
        "em",
        "u",
        "s",
        "del",
        "ins",
        "code",
        "pre",
        "blockquote",
        "br",
        "p",
        "span",
    }
)
_COMMENT_ALLOWED_ATTRIBUTES: dict[str, list[str]] = {
    "a": ["href", "title", "rel"],
}



def _clean_comment_content(raw: str) -> str:
    """Strip markup from a comment body, the way every comment system does.

    Comments are prose, not markup: nobody writes ``<p>`` in a comment, so the
    generous post allowlist is the wrong tool — it would keep a ``<table>`` or an
    ``<img>`` that a reader's browser then has to render. WordPress runs
    ``wp_kses`` over comment content for the same reason.

    The stored value was raw and unfiltered, and while the public renderer is
    React-escaped so it could not execute there, the moderation tab renders the
    same stored string, and any future consumer reaching for
    ``dangerouslySetInnerHTML`` would inherit the payload.

    Line breaks survive as ``<br>``/``<p>`` because a reader's comment is
    multi-line prose more often than not, and everything else is reduced to its
    text.
    """
    import bleach

    from app.shared.content.html_sanitizer import ALLOWED_PROTOCOLS, drop_code_blocks

    # Script/style bodies would otherwise survive as literal text once bleach
    # strips the tags — the same leak the CMS sanitizer had.
    cleaned = bleach.clean(
        drop_code_blocks(raw or ""),
        tags=_COMMENT_ALLOWED_TAGS,
        attributes=_COMMENT_ALLOWED_ATTRIBUTES,
        protocols=ALLOWED_PROTOCOLS,
        strip=True,
        strip_comments=True,
    )
    return cleaned.strip()


class CommentService:
    """Service for blog/page comment operations (WordPress parity)."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Target resolution ─────────────────────────────────────────────────

    @staticmethod
    def _normalize_target(
        data: BlogCommentCreate,
    ) -> tuple[str, uuid.UUID, uuid.UUID | None]:
        """Resolve the comment's target to (resource_type, resource_id, post_id).

        ``post_id`` is legacy sugar for (blog_post, post_id); the two
        addressings must not contradict each other.
        """
        if data.post_id is not None:
            if data.resource_type == COMMENT_RESOURCE_CMS_PAGE:
                raise ValidationError("post_id با resource_type=cms_page سازگار نیست")
            if data.resource_id is not None and data.resource_id != data.post_id:
                raise ValidationError("post_id و resource_id باید یکسان باشند")
            return COMMENT_RESOURCE_BLOG_POST, data.post_id, data.post_id
        if data.resource_id is None:
            raise ValidationError("یکی از post_id یا resource_id الزامی است")
        return data.resource_type, data.resource_id, None

    async def _ensure_post_accepts_comments(self, post_id: uuid.UUID) -> None:
        """Legacy rule: the post must exist and allow comments."""
        post = await self.db.get(BlogPost, post_id)
        if not post:
            raise NotFoundError("BlogPost", f"Post {post_id} not found")
        if not post.allow_comments:
            raise ValidationError("این پست امکان نظردهی ندارد")

    async def _ensure_page_accepts_comments(self, page_id: uuid.UUID) -> None:
        """Only published, non-deleted CMS pages accept comments."""
        from app.modules.content.domain.models import CmsPage, PageStatus

        page = await self.db.get(CmsPage, page_id)
        if not page:
            raise NotFoundError("CmsPage", f"Page {page_id} not found")
        if page.deleted_at is not None or page.status != PageStatus.PUBLISHED:
            raise ValidationError("این صفحه امکان نظردهی ندارد")

    async def _ensure_same_resource(
        self,
        parent: BlogComment,
        resource_type: str,
        resource_id: uuid.UUID,
    ) -> None:
        """A reply's parent must live on the same object (same 404 as a
        missing parent, so callers cannot probe other resources' comment ids).
        """
        parent_type = parent.resource_type or COMMENT_RESOURCE_BLOG_POST
        parent_target = parent.resource_id or parent.post_id
        if parent_type != resource_type or parent_target != resource_id:
            raise NotFoundError("BlogComment", "Parent comment not found")

    # ── Threading ─────────────────────────────────────────────────────────

    async def _thread_depth_setting(self) -> int:
        from app.modules.settings.application.site_options_service import (
            SiteOptionsService,
        )

        return await SiteOptionsService.get_int(
            self.db, "thread_comments_depth", DEFAULT_THREAD_DEPTH, minimum=1, maximum=10
        )

    async def _comments_per_page_setting(self) -> int:
        """``comments_per_page``, clamped so a typo cannot return the whole table."""
        from app.modules.settings.application.site_options_service import (
            SiteOptionsService,
        )

        return await SiteOptionsService.get_int(
            self.db, "comments_per_page", 20, minimum=1, maximum=100
        )

    async def _max_links_setting(self) -> int:
        """``comment_max_links`` — 0 means "no links allowed" (WordPress default)."""
        from app.modules.settings.application.site_options_service import (
            SiteOptionsService,
        )

        return await SiteOptionsService.get_int(
            self.db, "comment_max_links", 2, minimum=0, maximum=50
        )

    async def _check_flood(self, author_ip: str | None) -> None:
        """Reject a second comment from one IP inside the cooldown.

        WordPress's ``check_comment_flood`` blocks any repeat from the same
        address within 15 seconds. This endpoint is unauthenticated-optional
        and had no per-IP limit of its own — the only ceiling was the global
        200/minute middleware, which a script reaches easily. The address is
        already recorded on every comment, so the check is one indexed query.

        Moderators are exempt, matching WordPress: an administrator triaging
        the queue from the same address should not lock themselves out.
        """
        if not author_ip:
            return
        from app.modules.settings.application.site_options_service import (
            SiteOptionsService,
        )

        window = await SiteOptionsService.get_int(
            self.db, "comment_flood_seconds", 15, minimum=0, maximum=3600
        )
        if window <= 0:
            return
        cutoff = datetime.now(UTC) - timedelta(seconds=window)
        recent = (
            await self.db.execute(
                select(func.count())
                .select_from(BlogComment)
                .where(
                    BlogComment.author_ip == author_ip,
                    BlogComment.created_at > cutoff,
                )
            )
        ).scalar_one()
        if recent:
            raise ValidationError(
                f"برای ثبت دیدگاه تازه {window} ثانیه صبر کنید."
            )

    async def _check_link_limit(self, content: str) -> None:
        """Reject a comment carrying more links than ``comment_max_links`` allows.

        This is the cheap half of WordPress's spam control: a comment that is
        mostly links is advertising, and a reviewer should never have to open
        one to find out. Only explicit ``http://`` / ``https://`` markup counts
        — a bare "www.example.com" written as prose is not a link, and
        punishing it would reject ordinary Persian sentences.
        """
        import re

        max_links = await self._max_links_setting()
        links = re.findall(r"https?://\S+", content or "", re.IGNORECASE)
        if len(links) <= max_links:
            return
        if max_links == 0:
            raise ValidationError("متن دیدگاه نباید پیوند داشته باشد.")
        raise ValidationError(
            f"متن دیدگاه بیش از {max_links} پیوند دارد و پذیرفته نشد."
        )

    async def _registration_required(self) -> bool:
        """Whether only authenticated users may comment (WordPress
        ``comment_registration``). Unset or unrecognised keeps guest comments
        open — this site's long-standing default; closing the door must be an
        explicit operator choice, never a side effect of a missing row.
        """
        from app.modules.settings.application.site_options_service import (
            SiteOptionsService,
        )

        raw = await SiteOptionsService.get(self.db, "comment_registration", "0")
        return str(raw if raw is not None else "0").strip().lower() in _MODERATION_ON

    async def _comment_depth(self, comment: BlogComment) -> int:
        """Depth of a comment in its thread (top-level = 1).

        Walks the parent chain — at most ``thread_comments_depth`` hops in
        practice, hard-bounded so a cyclic chain cannot loop forever.
        """
        depth = 1
        seen: set[uuid.UUID] = set()
        current = comment
        while current.parent_id is not None and depth < MAX_DEPTH_WALK:
            if current.id in seen:  # cycle guard
                break
            seen.add(current.id)
            parent = await self.db.get(BlogComment, current.parent_id)
            if parent is None:
                break
            depth += 1
            current = parent
        return depth

    # ── Moderation ────────────────────────────────────────────────────────

    async def _resolve_status(
        self,
        resource_type: str,
        author_id: uuid.UUID | None,
        auto_approve: bool,
        content: str = "",
        author_name: str | None = None,
        author_url: str | None = None,
    ) -> CommentStatus:
        """Decide the initial moderation status.

        ``comment_moderation`` is the site-wide hold-everything switch and
        applies to *every* commentable object, on both sides. It used to be
        consulted only for CMS pages, with an early return for blog posts, so
        the seed value of "1" meant "queue everything" on pages and "queue
        nothing" on blog posts — and a logged-in reader's blog comment
        auto-published regardless of the operator's setting.

        Below that: an authenticated author publishes immediately, and guests
        land in PENDING.
        """
        from app.modules.settings.application.site_options_service import (
            SiteOptionsService,
        )

        # Operator-editable keyword lists, WordPress parity. `disallowed_keys`
        # refuses a comment outright; `moderation_keys` holds it for review.
        # These are the two controls an administrator actually reaches for when
        # spam starts arriving, and neither existed — the only word list was a
        # hard-coded tuple in the spam scorer, which no one could change.
        #
        # Checked BEFORE the site-wide hold, deliberately: a refusal is a
        # refusal regardless of how much the site queues anyway, and with the
        # hold first (its default is "1") the disallowed list would never run.
        verdict = await self._check_keyword_lists(
            BlogCommentCreate(
                content=content, author_name=author_name, author_url=author_url
            )
        )
        if verdict is CommentStatus.PENDING:
            return CommentStatus.PENDING

        raw = await SiteOptionsService.get(self.db, "comment_moderation", "1")
        if str(raw if raw is not None else "1").strip().lower() in _MODERATION_ON:
            return CommentStatus.PENDING

        return CommentStatus.APPROVED if (author_id or auto_approve) else CommentStatus.PENDING

    async def _check_keyword_lists(self, data: BlogCommentCreate) -> CommentStatus:
        """Apply the site's ``moderation_keys`` and ``disallowed_keys``.

        Returns ``PENDING`` to hold, or ``APPROVED`` for "no opinion" — the
        caller then applies the ordinary rules. A ``disallowed_keys`` hit is a
        hard refusal, raised rather than queued, because that is the point of
        the list: the comment is never stored.
        """
        from app.modules.settings.application.site_options_service import (
            SiteOptionsService,
        )

        haystack = " ".join(
            part for part in (data.content, data.author_name, data.author_url) if part
        ).lower()
        if not haystack.strip():
            return CommentStatus.APPROVED

        disallowed = _keyword_list(
            await SiteOptionsService.get(self.db, "disallowed_keys", "")
        )
        if any(word in haystack for word in disallowed):
            raise ValidationError("این دیدگاه به دلیل محتوای مجاز ارسال نمی‌شود.")

        moderation = _keyword_list(
            await SiteOptionsService.get(self.db, "moderation_keys", "")
        )
        if any(word in haystack for word in moderation):
            return CommentStatus.PENDING
        return CommentStatus.APPROVED

    # ── CRUD ──────────────────────────────────────────────────────────────

    async def _moderator_ids(self) -> list[uuid.UUID]:
        """Active users who hold ``blog:moderate_comments``.

        WordPress's ``wp_new_comment_notify_moderator`` is how an administrator
        learns a comment is waiting. Without it the only way to notice a
        pending comment was to open the blog admin by hand, so in practice the
        queue was never looked at.
        """
        from app.modules.rbac.domain.models import (
            Permission,
            Role,
            RolePermission,
            UserRole,
        )
        from app.modules.users.domain.models import User

        rows = (
            await self.db.execute(
                select(UserRole.user_id)
                .join(Role, Role.id == UserRole.role_id)
                .join(RolePermission, RolePermission.role_id == Role.id)
                .join(Permission, Permission.id == RolePermission.permission_id)
                .join(User, User.id == UserRole.user_id)
                .where(
                    Permission.slug == "blog:moderate_comments",
                    User.is_active.is_(True),
                )
                .distinct()
            )
        ).scalars().all()
        return [uuid.UUID(str(r)) for r in rows]

    async def create_comment(
        self,
        data: BlogCommentCreate,
        *,
        author_id: uuid.UUID | None = None,
        author_ip: str | None = None,
        author_user_agent: str | None = None,
        auto_approve: bool = False,
    ) -> BlogCommentResponse:
        """Create a new comment (pending moderation by default)."""
        resource_type, resource_id, post_id = self._normalize_target(data)

        # WordPress comment_registration: when the operator requires accounts,
        # a guest submission is rejected before any target validation — the
        # caller needs to know to log in, not that the post id was wrong.
        if author_id is None and await self._registration_required():
            raise ValidationError("برای ثبت دیدگاه ابتدا وارد حساب کاربری خود شوید.")

        # Validate the target exists and accepts comments
        if resource_type == COMMENT_RESOURCE_CMS_PAGE:
            await self._ensure_page_accepts_comments(resource_id)
        else:
            await self._ensure_post_accepts_comments(resource_id)

        await self._check_link_limit(data.content)
        await self._check_flood(author_ip)

        # Validate parent comment if threaded reply: must exist, sit on the
        # same resource, and stay within the configured thread depth.
        if data.parent_id:
            parent = await self.db.get(BlogComment, data.parent_id)
            if not parent:
                raise NotFoundError("BlogComment", "Parent comment not found")
            await self._ensure_same_resource(parent, resource_type, resource_id)
            max_depth = await self._thread_depth_setting()
            parent_depth = await self._comment_depth(parent)
            if parent_depth >= max_depth:
                raise ValidationError(
                    f"حداکثر عمق پاسخ‌دهی به نظرها {max_depth} سطح است"
                )

        status = await self._resolve_status(
            resource_type,
            author_id,
            auto_approve,
            content=data.content,
            author_name=data.author_name,
            author_url=data.author_url,
        )

        # Spam check. A comment that scores as spam is held for moderation
        # rather than published — the alternative (WordPress's behaviour with
        # no Akismet key) is that it goes straight to the front page. A
        # logged-in author is exempt: they can be held for moderation, but
        # they are never auto-approved on a heuristic alone either way.
        verdict = score_comment(
            data.content,
            author_name=data.author_name,
            author_url=data.author_url,
            user_agent=author_user_agent,
        )
        if verdict.is_spam and status == CommentStatus.APPROVED:
            status = CommentStatus.PENDING
            await logger.ainfo(
                "comment_held_as_spam",
                score=verdict.score,
                reasons=list(verdict.reasons),
            )

        comment = BlogComment(
            post_id=post_id,
            resource_type=resource_type,
            resource_id=resource_id,
            author_id=author_id,
            author_name=data.author_name,
            author_email=data.author_email,
            author_url=data.author_url,
            author_ip=author_ip,
            author_user_agent=author_user_agent,
            content=_clean_comment_content(data.content),
            status=status,
            parent_id=data.parent_id,
        )
        self.db.add(comment)
        await self.db.commit()
        await self.db.refresh(comment)

        logger.info(
            "comment_created",
            comment_id=str(comment.id),
            resource_type=resource_type,
            resource_id=str(resource_id),
            status=status.value,
        )

        # Only an approved comment is visible to the people being notified;
        # announcing a pending one would leak its content to the post author
        # before moderation. Best-effort — a notify failure never fails the
        # comment write.
        if status == CommentStatus.APPROVED and resource_type == COMMENT_RESOURCE_BLOG_POST:
            await self._notify_comment(
                comment=comment,
                resource_id=resource_id,
                commenter_name=data.author_name,
            )

        response = BlogCommentResponse.model_validate(comment)
        await self._attach_avatars([response])
        return response

    async def _notify_comment(
        self,
        *,
        comment: BlogComment,
        resource_id: uuid.UUID,
        commenter_name: str | None,
    ) -> None:
        """Tell the post author (and any parent commenter) about a new comment."""
        try:
            from app.modules.blog.application.notification_service import (
                BlogNotificationService,
            )

            post = await self.db.get(BlogPost, resource_id)
            if post is None:
                return
            parent_author_id = None
            if comment.parent_id:
                parent = await self.db.get(BlogComment, comment.parent_id)
                parent_author_id = parent.author_id if parent else None
            name = commenter_name or comment.author_name or "کاربر"
            await BlogNotificationService(self.db).notify_new_comment(
                comment_id=comment.id,
                post_id=resource_id,
                post_title=post.title,
                commenter_name=name,
                post_author_id=post.author_id,
                parent_comment_author_id=parent_author_id,
                moderator_ids=(
                    await self._moderator_ids()
                    if comment.status is CommentStatus.PENDING
                    else []
                ),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("comment_notify_failed", comment_id=str(comment.id), error=str(exc))

    async def update_comment(
        self,
        comment_id: uuid.UUID,
        data: BlogCommentUpdate,
    ) -> BlogCommentResponse:
        """Update comment content or status."""
        comment = await self.db.get(BlogComment, comment_id)
        if not comment:
            raise NotFoundError("BlogComment", f"Comment {comment_id} not found")

        if data.content is not None:
            comment.content = _clean_comment_content(data.content)
        if data.status is not None:
            comment.status = data.status

        await self.db.commit()
        await self.db.refresh(comment)

        logger.info("comment_updated", comment_id=str(comment_id))
        # Admin path: the moderation surface needs the email and the status.
        return BlogCommentAdminResponse.model_validate(comment)

    async def delete_comment(self, comment_id: uuid.UUID) -> None:
        """Permanently delete a comment (soft delete to TRASH first recommended)."""
        comment = await self.db.get(BlogComment, comment_id)
        if not comment:
            raise NotFoundError("BlogComment", f"Comment {comment_id} not found")

        await self.db.delete(comment)
        await self.db.commit()
        logger.info("comment_deleted", comment_id=str(comment_id))

    async def moderate_comment(
        self,
        comment_id: uuid.UUID,
        status: CommentStatus,
    ) -> BlogCommentResponse:
        """Change comment moderation status (approve, spam, trash)."""
        comment = await self.db.get(BlogComment, comment_id)
        if not comment:
            raise NotFoundError("BlogComment", f"Comment {comment_id} not found")

        old_status = comment.status
        comment.status = status
        await self.db.commit()
        await self.db.refresh(comment)

        logger.info(
            "comment_moderated",
            comment_id=str(comment_id),
            old_status=old_status.value,
            new_status=status.value,
        )

        # Tell the commenter their comment went live — but only on the
        # pending -> approved edge. Re-approving an already-approved comment
        # must not send a second "your comment is live" mail.
        if status == CommentStatus.APPROVED and old_status != CommentStatus.APPROVED:
            try:
                from app.modules.blog.application.notification_service import (
                    BlogNotificationService,
                )

                post = await self.db.get(BlogPost, comment.resource_id)
                await BlogNotificationService(self.db).notify_comment_approved(
                    comment_id=comment.id,
                    post_title=post.title if post else "",
                    comment_author_email=comment.author_email,
                    comment_author_id=comment.author_id,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "comment_approved_notify_failed",
                    comment_id=str(comment_id),
                    error=str(exc),
                )

        return BlogCommentAdminResponse.model_validate(comment)

    async def get_comment(self, comment_id: uuid.UUID) -> BlogCommentResponse:
        """Fetch a single comment by ID."""
        comment = await self.db.get(BlogComment, comment_id)
        if not comment:
            raise NotFoundError("BlogComment", f"Comment {comment_id} not found")
        response = BlogCommentResponse.model_validate(comment)
        await self._attach_avatars([response])
        return response

    async def list_comments(
        self,
        post_id: uuid.UUID | None = None,
        status: CommentStatus | None = CommentStatus.APPROVED,
        page: int = 1,
        page_size: int | None = None,
        include_replies: bool = True,
        resource_type: str | None = None,
        resource_id: uuid.UUID | None = None,
        include_moderation_fields: bool = False,
    ) -> BlogCommentListResponse:
        """List comments with optional filtering and pagination.

        ``include_moderation_fields`` builds the admin schema, which carries
        ``author_email`` and ``status``. It must stay False on every public
        route: the anonymous comment list is the one endpoint that would hand a
        visitor every commenter's address.

        Address the target either by legacy ``post_id`` or by the polymorphic
        ``resource_type``/``resource_id`` pair (``resource_type`` alone
        filters across every object of that type).

        When include_replies is True, returns top-level comments with their
        threaded replies nested in the `replies` field; False yields the flat
        shape (every comment, replies included as plain items).

        ``page_size=None`` means "use the ``comments_per_page`` site option";
        an explicit value always wins, so a caller asking for 5 gets 5.
        """
        stmt = select(BlogComment)

        if post_id is not None:
            stmt = stmt.where(BlogComment.post_id == post_id)
        elif resource_id is not None:
            stmt = stmt.where(
                BlogComment.resource_type == (resource_type or COMMENT_RESOURCE_BLOG_POST),
                BlogComment.resource_id == resource_id,
            )
        elif resource_type is not None:
            stmt = stmt.where(BlogComment.resource_type == resource_type)
        if status:
            stmt = stmt.where(BlogComment.status == status)

        # Only fetch top-level comments (no parent) when threading
        if include_replies:
            stmt = stmt.where(BlogComment.parent_id.is_(None))

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.db.execute(count_stmt)).scalar_one()

        if page_size is None:
            page_size = await self._comments_per_page_setting()
        stmt = (
            stmt.order_by(BlogComment.created_at.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        comments = (await self.db.execute(stmt)).scalars().all()

        # Bound the reply recursion. Each level costs one SELECT, and an
        # unbounded chain also risks Python's recursion limit — a runaway
        # thread must not turn a comment list into a 500.
        max_depth = 3
        if include_replies:
            max_depth = await self._thread_depth_setting()

        items: list[BlogCommentResponse] = []
        for comment in comments:
            response = self._build_response(comment, include_moderation_fields)
            if include_replies:
                response.replies = await self._get_replies(
                    comment.id,
                    remaining=max_depth,
                    include_moderation_fields=include_moderation_fields,
                    status=status,
                )
            items.append(response)

        # One batched lookup for the whole page rather than per comment.
        await self._attach_avatars(items)

        total_pages = max(1, math.ceil(total / page_size)) if total > 0 else 0

        return BlogCommentListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_prev=page > 1,
        )

    async def _attach_avatars(self, comments: list[BlogCommentResponse]) -> None:
        """Fill in ``author_avatar_url`` for a whole thread in one pass.

        Registered authors resolve through the profile/Gravatar lookup (two
        queries for the whole batch); guests fall back to their Gravatar when
        they left an email, which is what WordPress does. Recurses into
        replies so a nested comment is not the one missing an avatar.
        """
        from app.shared.content.gravatar import avatars_for_users, resolve_avatar_url

        author_ids = [c.author_id for c in comments if c.author_id]
        resolved = await avatars_for_users(self.db, author_ids)

        for comment in comments:
            if comment.author_id and comment.author_id in resolved:
                comment.author_avatar_url = resolved[comment.author_id]
            else:
                # A guest, or an author with neither a profile image nor a
                # row in the users table this batch: Gravatar by email only.
                comment.author_avatar_url = resolve_avatar_url(
                    local_url=None, email=comment.author_email
                )
            if comment.replies:
                await self._attach_avatars(comment.replies)

    @staticmethod
    def _build_response(
        comment: BlogComment, *, moderation_fields: bool
    ) -> BlogCommentResponse:
        """Project a row onto the public or the moderation schema.

        Splitting this out keeps the "which schema" decision in one place, so a
        new call site cannot accidentally expose ``author_email`` by forgetting
        to think about it.
        """
        if moderation_fields:
            return BlogCommentAdminResponse.model_validate(comment)
        return BlogCommentResponse.model_validate(comment)

    async def _get_replies(
        self,
        parent_id: uuid.UUID,
        *,
        remaining: int,
        include_moderation_fields: bool = False,
        status: CommentStatus | None = None,
    ) -> list[BlogCommentResponse]:
        """Fetch a comment's replies, recursing at most ``remaining`` levels.

        Replies past the limit are omitted rather than fetched: a thread
        nested deeper than the admin configured is truncated, which is the
        behaviour the depth setting describes. Callers pass
        ``thread_comments_depth``; the bound also caps the number of
        sequential SELECTs a single list render can issue.

        ``status`` MUST be applied here, not only to the top-level query. It
        used to be absent, so a PENDING guest reply to an APPROVED comment was
        served by the public list at depth 2 and 3 — the moderation queue did
        not hold for threaded comments. ``list_comments`` passes its own
        filter down; passing None (the default) means no filter, which is only
        correct for a caller that has already filtered.
        """
        if remaining <= 0:
            return []

        stmt = select(BlogComment).where(BlogComment.parent_id == parent_id)
        if status is not None:
            stmt = stmt.where(BlogComment.status == status)
        stmt = stmt.order_by(BlogComment.created_at.asc())
        replies = (await self.db.execute(stmt)).scalars().all()

        results: list[BlogCommentResponse] = []
        for reply in replies:
            response = self._build_response(
                reply, moderation_fields=include_moderation_fields
            )
            response.replies = await self._get_replies(
                reply.id,
                remaining=remaining - 1,
                include_moderation_fields=include_moderation_fields,
                status=status,
            )
            results.append(response)
        return results

    async def get_comment_count(
        self,
        post_id: uuid.UUID,
        status: CommentStatus = CommentStatus.APPROVED,
    ) -> int:
        """Count comments for a post by status."""
        stmt = select(func.count(BlogComment.id)).where(
            BlogComment.post_id == post_id,
            BlogComment.status == status,
        )
        return (await self.db.execute(stmt)).scalar_one()

    async def get_resource_comment_count(
        self,
        resource_type: str,
        resource_id: uuid.UUID,
        status: CommentStatus = CommentStatus.APPROVED,
    ) -> int:
        """Count approved comments for any commentable object by status."""
        stmt = select(func.count(BlogComment.id)).where(
            BlogComment.resource_type == resource_type,
            BlogComment.resource_id == resource_id,
            BlogComment.status == status,
        )
        return (await self.db.execute(stmt)).scalar_one()
