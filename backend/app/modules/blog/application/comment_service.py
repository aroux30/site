"""Comment service: moderation, threading, and CRUD for polymorphic comments.

Comments attach to blog posts (legacy ``post_id`` addressing) or CMS pages
(polymorphic ``resource_type``/``resource_id`` addressing) — WordPress parity,
where wp_comments serves both. Threading enforces the site's
``thread_comments_depth`` setting at creation time and nests replies in list
responses; page comments honour the ``comment_moderation`` site option.
"""

from __future__ import annotations

import math
import re
import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import func, or_, select

from app.core.exceptions.handlers import NotFoundError, ValidationError
from app.modules.blog.application.comment_email_service import CommentEmailService
from app.modules.blog.application.spam_filter import score_comment
from app.modules.blog.domain.models import (
    COMMENT_RESOURCE_BLOG_POST,
    COMMENT_RESOURCE_CMS_PAGE,
    COMMENT_RESOURCE_TYPES,
    COMMENT_TYPE_COMMENT,
    COMMENT_TYPE_NOTE,
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

#: Values that mean "newest first" for `comment_order`. Anything else — an
#: empty string, a typo, a value from a newer WordPress — falls back to oldest
#: first rather than raising, so a bad setting degrades to the default instead
#: of emptying the comment list.
_COMMENT_ORDER_DESC = {"desc", "descending", "newest", "new", "2"}


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


_COMMENT_URL_RE = re.compile(r"^https?://[^\s/$.?#][^\s]*$", re.IGNORECASE)


def _normalize_comment_url(raw: str | None) -> str | None:
    """Accept only a real web address for a commenter's site.

    The column, the schema and the public response all carried this field while
    nothing ever filled it in, so a guest could post ``javascript:alert(1)`` and
    it would sit in the table until the first renderer linkified it. The public
    list renders these as anchors, so the check belongs on the way in, not only
    in the view: a value written by an API client or an import has to be refused
    for the same reason.

    Returns None for anything that is not an absolute http(s) URL, which is what
    the renderer's own test agrees with.
    """
    value = (raw or "").strip()
    if not value:
        return None
    if not _COMMENT_URL_RE.match(value):
        return None
    return value[:500]


class CommentService:
    """Service for blog/page comment operations (WordPress parity)."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        # comment id -> author email, for the guest-Gravatar fallback.
        # ``BlogCommentResponse`` omits the email on purpose, so the avatar
        # pass cannot read it off the response; it is staged here from the
        # models that were just loaded and never serialized.
        self._email_by_comment: dict[str, str | None] = {}

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

    async def _ensure_content_type_accepts_comments(self, entry_id: uuid.UUID) -> None:
        """Whether this custom post type is commentable, per its own flag.

        WordPress's ``supports`` checkbox decides this. It was stored and
        serialised and never consulted, so turning it on did nothing at all —
        which is the whole content of the gap: a checkbox in the admin that
        lies.

        The flag lives on the *type*, not the entry, so this reads the entry's
        type rather than the entry. An entry of a type with comments off is
        refused even if the entry itself is published, and vice versa — which
        is what an operator expects when they tick the box once for a whole
        content type.
        """
        from app.modules.blog.domain.custom_post_types import (
            CustomPostEntry,
            CustomPostType,
        )

        entry = await self.db.get(CustomPostEntry, entry_id)
        if entry is None:
            raise ValidationError("محتوای درخواستی یافت نشد")

        ctype = await self.db.get(CustomPostType, entry.post_type_id)
        if ctype is None:
            raise ValidationError("نوع محتوای درخواستی یافت نشد")
        if not ctype.supports_comments:
            raise ValidationError(
                "دیدگاه برای این نوع محتوا فعال نیست."
            )

    async def _ensure_post_accepts_comments(self, post_id: uuid.UUID) -> None:
        """The post must exist, allow comments, and still be young enough.

        The age check is WordPress's ``close_comments_for_old_posts`` measured
        on the post, not on the comment: the claim being made is that the
        conversation on *this* post is finished, which is a fact about the post.
        A month threshold that looked at the comment would let an old post keep
        collecting new replies forever, which is the thing the option exists to
        stop.

        Off when the option is 0, so nothing changes for a store that has not
        asked for it.
        """
        post = await self.db.get(BlogPost, post_id)
        if not post:
            raise NotFoundError("BlogPost", f"Post {post_id} not found")
        if not post.allow_comments:
            raise ValidationError("این پست امکان نظردهی ندارد")

        days = await self._comments_closed_setting()
        if days <= 0:
            return
        # A post with no publication date cannot be old, and treating it as
        # epoch-old would close comments on every draft.
        anchor = post.published_at or post.created_at
        if anchor is None:
            return
        if anchor.tzinfo is None:
            anchor = anchor.replace(tzinfo=UTC)
        age_days = (datetime.now(UTC) - anchor).days
        if age_days >= days:
            raise ValidationError(
                f"نظردهی روی این نوشته بسته است: {age_days} روز از انتشار آن گذشته "
                f"و سقف تنظیم‌شده {days} روز است."
            )

    async def _ensure_page_accepts_comments(self, page_id: uuid.UUID) -> None:
        """Only published, non-deleted CMS pages that opted in accept comments.

        ``allow_comments`` defaults to false, so a page is a static document
        until its editor turns the thread on. Without this check the page
        resource was writable in practice: any published page accepted a
        comment, including a legal or policy page.
        """
        from app.modules.content.domain.models import CmsPage, PageStatus

        page = await self.db.get(CmsPage, page_id)
        if not page:
            raise NotFoundError("CmsPage", f"Page {page_id} not found")
        if page.deleted_at is not None or page.status != PageStatus.PUBLISHED:
            raise ValidationError("این صفحه امکان نظردهی ندارد")
        if not page.allow_comments:
            raise ValidationError("نظردهی برای این صفحه غیرفعال است")

        # The same age limit as posts. Leaving it off pages would be a hole
        # straight through the rule: the oldest thread in the store is usually
        # on a page, not a post.
        days = await self._comments_closed_setting()
        if days <= 0:
            return
        anchor = page.published_at or page.created_at
        if anchor is None:
            return
        if anchor.tzinfo is None:
            anchor = anchor.replace(tzinfo=UTC)
        age_days = (datetime.now(UTC) - anchor).days
        if age_days >= days:
            raise ValidationError(
                f"نظردهی روی این صفحه بسته است: {age_days} روز از انتشار آن گذشته "
                f"و سقف تنظیم‌شده {days} روز است."
            )

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

    async def _comment_order(self):
        """The sort order for a comment list, from ``comment_order``.

        WordPress offers asc/desc here (comment-template.php:2418) and this was
        hard-coded ascending, so an operator who set "newest first" got no
        change and no error. Ascending stays the default because that is what
        the admin moderation queue needs — a comment you are working through is
        the one you want at the top — and because changing it would silently
        reorder every existing thread's replies.

        The `created_at` tiebreak is not decoration: comments written inside the
        same second would otherwise come back in whatever order Postgres
        happened to produce, so paging through a thread could repeat or skip
        one. `id` is monotonic and breaks the tie the same way every run.
        """
        from app.modules.settings.application.site_options_service import (
            SiteOptionsService,
        )

        raw = await SiteOptionsService.get(self.db, "comment_order", "asc")
        descending = str(raw or "asc").strip().lower() in _COMMENT_ORDER_DESC
        first = BlogComment.created_at.desc() if descending else BlogComment.created_at.asc()
        return [first, BlogComment.id.asc()]

    async def _max_links_setting(self) -> int:
        """``comment_max_links`` — 0 means "no links allowed" (WordPress default)."""
        from app.modules.settings.application.site_options_service import (
            SiteOptionsService,
        )

        return await SiteOptionsService.get_int(
            self.db, "comment_max_links", 2, minimum=0, maximum=50
        )

    async def _require_name_email_setting(self) -> bool:
        """``require_name_email``: a guest comment must carry a name and an email.

        Off by default, matching this site's existing posture, because
        guest comments are open. The point of the option is that an operator who
        *does* turn it on gets an enforcement, not just a form hint — and a
        form hint is not enforcement, because the API is the same endpoint the
        form posts to.
        """
        from app.modules.settings.application.site_options_service import (
            SiteOptionsService,
        )

        raw = await SiteOptionsService.get(self.db, "require_name_email", "0")
        return str(raw).strip().lower() in {"1", "true", "yes", "on"}

    async def _check_rate_limit(self, author_ip: str | None) -> None:
        """Cap comments per address per hour and per day.

        ``_check_flood`` covers the 15-second burst. This is the other half and
        the one that matters against a script: a flood check stops an impatient
        person, but a bot posting one comment a minute never trips it and fills
        the queue with a hundred rows that a moderator has to read and delete.

        Both windows are site options, and both are exempt for moderators the
        way the flood check is — triaging from the same address must not lock
        the moderator out of their own queue.

        No address, no limit to apply: every comment is a signed-in user's at
        that point, and the account itself is the limiter.
        """
        if not author_ip:
            return
        from app.core.exceptions.handlers import ValidationError
        from app.modules.settings.application.site_options_service import (
            SiteOptionsService,
        )

        now = datetime.now(UTC)
        for option, default, delta, label in (
            ("comments_per_hour", 5, timedelta(hours=1), "ساعت"),
            ("comments_per_day", 20, timedelta(days=1), "روز"),
        ):
            limit = await SiteOptionsService.get_int(
                self.db, option, default, minimum=0, maximum=10_000
            )
            # `limit == 0` disables the ceiling, which is how an operator turns
            # it off for a site that moderates by eye. Removing that case was a
            # sabotage once: with `recent >= 0` true on every call, *no comment
            # could ever be posted*, and the message said "more than 0".
            if limit <= 0:
                continue
            recent = (
                await self.db.execute(
                    select(func.count())
                    .select_from(BlogComment)
                    .where(
                        BlogComment.author_ip == author_ip,
                        BlogComment.created_at >= now - delta,
                    )
                )
            ).scalar_one()
            if recent >= limit:
                raise ValidationError(
                    detail=(
                        f"از این نشانی بیش از {limit} دیدگاه در هر {label} ثبت شده است. "
                        "لطفاً کمی بعد دوباره تلاش کنید."
                    )
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
        author_email: str | None = None,
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

        # comment_previously_approved: someone who has already been approved
        # once goes through automatically. Above the site-wide hold, because
        # that is where WordPress puts it (comment.php:133) and because the
        # hold's job is "nothing is trusted until a human looks", which a
        # returning commenter is the exception to.
        if await self._previously_approved(author_name, author_email, author_id):
            return CommentStatus.APPROVED

        raw = await SiteOptionsService.get(self.db, "comment_moderation", "1")
        if str(raw if raw is not None else "1").strip().lower() in _MODERATION_ON:
            return CommentStatus.PENDING

        return CommentStatus.APPROVED if (author_id or auto_approve) else CommentStatus.PENDING

    async def _previously_approved(
        self,
        author_name: str | None,
        author_email: str | None,
        author_id: uuid.UUID | None,
    ) -> bool:
        """Has this commenter had a comment approved before?

        WordPress's `comment_previously_approved`, and the trust it builds is
        the difference between a store whose comment queue empties itself and
        one where every returning customer waits a day for a reply. The lookup
        is deliberately the one core uses — an account by id, otherwise the
        name *and* the email together, never the name alone, because names are
        the easiest thing for a spammer to borrow.

        The keyword escape hatch is part of this and not a detail: an address
        that matches a moderation keyword must still be queued, so someone who
        got into the database before that word list existed cannot hold their
        approval hostage to it.
        """
        from app.modules.settings.application.site_options_service import (
            SiteOptionsService,
        )

        raw = await SiteOptionsService.get(self.db, "comment_previously_approved", "0")
        if str(raw if raw is not None else "0").strip() != "1":
            return False

        email = (author_email or "").strip().lower()
        name = (author_name or "").strip()
        # Both fields required, exactly as core does: an empty name or an empty
        # email would otherwise match a row where that column is null, which
        # approves every nameless or address-less comment on the site.
        if not name or not email:
            return False

        query = select(BlogComment.id).where(
            BlogComment.status == CommentStatus.APPROVED,
            BlogComment.author_email == email,
        )
        if author_id:
            query = query.where(
                BlogComment.author_id == author_id,
            )
        else:
            query = query.where(BlogComment.author_name == name)

        found = (await self.db.execute(query.limit(1))).first()
        if found is None:
            return False

        mod_keys = await SiteOptionsService.get(self.db, "moderation_keys", "")
        keys = str(mod_keys or "")
        if keys and email in keys.lower():
            logger.info("comment_previous_approval_overridden", author_email=email[:64])
            return False
        return True

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
        elif resource_type == COMMENT_RESOURCE_BLOG_POST:
            await self._ensure_post_accepts_comments(resource_id)
        else:
            # Previously this was a bare `else`, so a custom post type with
            # `supports_comments` enabled fell through to the blog-post branch
            # and failed on a post id that does not exist — an error about the
            # wrong thing, on a type the operator had explicitly enabled
            # comments for. The flag is read here rather than assumed: it is
            # the only thing that says whether a CPT is commentable.
            await self._ensure_content_type_accepts_comments(resource_id)

        await self._check_link_limit(data.content)
        await self._check_flood(author_ip)
        # The flood window stops a burst; this stops a bot posting steadily for
        # an hour, which the flood window never notices. Both guards are on the
        # create path, so neither can be bypassed by posting to the API instead
        # of the form.
        await self._check_rate_limit(author_ip)
        # require_name_email is enforced here rather than in the schema because
        # a signed-in commenter already has both, and the schema cannot tell
        # that from the request alone.
        if author_id is None and await self._require_name_email_setting():
            missing = [
                label
                for label, value in (
                    ("نام", (data.author_name or "").strip()),
                    ("ایمیل", (data.author_email or "").strip()),
                )
                if not value
            ]
            if missing:
                from app.core.exceptions.handlers import ValidationError

                raise ValidationError(
                    detail=(
                        f"برای ثبت دیدگاه، {missing[0]} الزامی است."
                        if len(missing) == 1
                        else f"برای ثبت دیدگاه، {missing[0]} و {missing[1]} الزامی است."
                    )
                )

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
            author_email=data.author_email,
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

        # The external opinion, when the site has a key. Advisory: it can hold a
        # comment for review that the local engine let through, but it can never
        # clear one — an unreachable or undecided service is `None` and leaves
        # the local verdict standing. Order matters, the local engine decides
        # first and Akismet can only add.
        remote = await self._akismet_opinion(data, author_user_agent)
        if remote is not None and remote.is_spam and status == CommentStatus.APPROVED:
            status = CommentStatus.PENDING
            await logger.ainfo(
                "comment_held_by_akismet",
                raw=remote.raw,
            )

        # A plugin can inspect or rewrite the payload before the row exists —
        # the point where a spam rule or a required-field policy belongs. Fired
        # after the sanitizer and the URL check, so a hook sees what would
        # actually be stored rather than the raw request.
        from app.shared.plugins.registry import (
            HOOK_COMMENT_AFTER_CREATE,
            HOOK_COMMENT_BEFORE_CREATE,
            registry,
        )

        hook_fields = {
            "content": _clean_comment_content(data.content),
            "author_name": data.author_name,
            "author_email": data.author_email,
            "author_url": _normalize_comment_url(data.author_url),
            "status": status,
        }
        hook_fields = await registry.apply_filters(
            HOOK_COMMENT_BEFORE_CREATE,
            hook_fields,
            resource_type=resource_type,
            resource_id=str(resource_id),
        )
        if isinstance(hook_fields, dict):
            # Read back defensively: a hook may have dropped a key, and a
            # missing one has to fall back to the validated value rather than
            # become a NOT NULL violation.
            content_text = _clean_comment_content(
                str(hook_fields.get("content") or data.content)
            )
            author_name = hook_fields.get("author_name", data.author_name)
            author_url = _normalize_comment_url(
                hook_fields.get("author_url", data.author_url)
            )
            try:
                status = CommentStatus(hook_fields.get("status") or status)
            except ValueError:
                # A hook returning a status outside the enum is ignored rather
                # than failing the write; an unknown status would break every
                # later read of the row.
                status = CommentStatus.PENDING

        comment = BlogComment(
            post_id=post_id,
            resource_type=resource_type,
            resource_id=resource_id,
            author_id=author_id,
            author_name=data.author_name,
            author_email=data.author_email,
            author_url=_normalize_comment_url(data.author_url),
            author_ip=author_ip,
            author_user_agent=author_user_agent,
            content=content_text,
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

        # After the commit, so a hook can read the row. Best-effort in the
        # registry itself: a plugin that raises must not lose the comment.
        await registry.do_action(
            HOOK_COMMENT_AFTER_CREATE,
            comment_id=str(comment.id),
            resource_type=resource_type,
            resource_id=str(resource_id),
            status=status.value,
        )

        # WordPress fires wp_notify_postauthor for every new comment, approved
        # or held: the two options decide *who* hears about it, not whether the
        # notification happens. Gating on APPROVED here deleted the whole
        # moderation branch — with it, `moderation_notify` was a switch that
        # could not fire, and a comment from a user the system holds went
        # silently unnoticed.
        if resource_type == COMMENT_RESOURCE_BLOG_POST:
            await self._notify_comment(
                comment=comment,
                resource_id=resource_id,
                commenter_name=data.author_name,
            )

        response = self._build_response(comment, moderation_fields=False)
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

            # wp_notify_postauthor: the author gets this by email too, with
            # Reply-To on the commenter so a reply reaches them directly. The
            # in-app event above only reaches someone who is logged in, which
            # is not the same thing for a store that runs on email.
            # WordPress keeps these two separate, and so does this: the author
            # hears about every comment, the moderators only about the ones
            # waiting for them. Folding them together meant a moderated post
            # notified the moderators *instead of* the author whenever the
            # author had no address on file.
            notify_author = await self._notification_setting("comments_notify", "1")
            notify_moderators = await self._notification_setting(
                "moderation_notify", "1"
            )
            is_pending = comment.status is CommentStatus.PENDING

            author_email = await self._user_email(post.author_id) if notify_author else None
            if not notify_author and is_pending and notify_moderators:
                # Author notification is off, so the moderation address is the
                # only one left — dropping the mail entirely would leave a held
                # comment with nobody told about it.
                author_email = await self._first_moderator_email()
            elif is_pending and notify_moderators:
                moderator_email = await self._first_moderator_email()
                author_email = author_email or moderator_email

            await CommentEmailService(self.db).notify_post_author(
                post_title=post.title,
                post_slug=post.slug,
                comment_content=comment.content,
                comment_status=comment.status.value,
                comment_author_name=comment.author_name,
                comment_author_email=comment.author_email,
                author_email=author_email,
                is_pending=is_pending,
                admin_url=await self._site_url(),
                # Without the id the moderator mail has no one-click links —
                # the only way to approve is to open the panel.
                comment_id=str(comment.id),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("comment_notify_failed", comment_id=str(comment.id), error=str(exc))

    async def _notification_setting(self, key: str, default: str) -> bool:
        """A comment-notification switch, read as a boolean.

        ``comments_notify`` (tell the author a comment arrived) and
        ``moderation_notify`` (tell the moderators one is waiting) are
        WordPress's `Comments Notify` and `Moderation Notify`. Both default to
        on: a store that has just had its notification path built would
        otherwise ship with it silently off, and the symptom — no email, no
        error — reads as "SMTP is broken" rather than "the option is off".
        """
        from app.modules.settings.application.site_options_service import (
            SiteOptionsService,
        )

        raw = await SiteOptionsService.get(self.db, key, default)
        return str(raw).strip().lower() not in {"0", "false", "no", "off"}

    async def _comments_closed_setting(self) -> int:
        """``close_comments_days_old``: refuse comments on an old post. 0 = never.

        WordPress pairs this with ``close_comments_for_old_posts``; here one
        number carries both, because a switch plus a threshold is two places to
        get wrong and one field to explain. Measured on the *post's* age, not
        the comment's: the point is that the conversation on this post is
        finished, which is a fact about the post.
        """
        from app.modules.settings.application.site_options_service import (
            SiteOptionsService,
        )

        return await SiteOptionsService.get_int(
            self.db, "close_comments_days_old", 0, minimum=0, maximum=3650
        )

    async def _user_email(self, user_id: uuid.UUID | None) -> str | None:
        """A user's address, or None. Never guessed from anything but a stored one."""
        if not user_id:
            return None
        from app.modules.users.domain.models import User

        row = (await self.db.execute(
            select(User.email).where(User.id == user_id)
        )).scalar_one_or_none()
        return (row or "").strip() or None

    async def _first_moderator_email(self) -> str | None:
        """One address for the moderation notice.

        A single moderator, not all of them: a held comment on a busy store
        would otherwise be one email per moderator, and they all read the same
        queue anyway.
        """
        from app.modules.users.domain.models import User

        rows = (await self.db.execute(
            select(User.email).where(User.is_active == True)  # noqa: E712
            .order_by(User.is_superuser.desc(), User.created_at)
            .limit(25)
        )).scalars().all()
        for candidate in rows:
            if (candidate or "").strip():
                return candidate.strip()
        return None

    async def _site_url(self) -> str:
        """The store's public origin, for the links inside an email."""
        from app.modules.settings.application.site_options_service import (
            SiteOptionsService,
        )

        return (await SiteOptionsService.get(self.db, "site_url", "")) or ""

    async def _akismet_opinion(self, data: Any, user_agent: str | None):
        """Ask Akismet about a new comment, when the site has configured it.

        Returns `None` — never a verdict — when there is no key, no site URL, or
        the service did not answer. `None` means "no opinion", and the caller
        leaves the local engine's decision alone.

        The key is read before the client is even constructed, so a site without
        one performs no work and makes no call: this is the path every comment
        on an unconfigured store takes, and it must stay the cheap one.
        """
        from app.modules.blog.application.akismet_client import (
            API_KEY_OPTION,
            API_URL_OPTION,
            AkismetClient,
        )
        from app.modules.settings.application.site_options_service import (
            SiteOptionsService,
        )

        api_key = await SiteOptionsService.get(self.db, API_KEY_OPTION, "")
        if not api_key or not str(api_key).strip():
            return None

        blog_url = (await self._site_url()).rstrip("/")
        if not blog_url:
            return None

        client: AkismetClient = getattr(self, "_akismet", None) or AkismetClient()
        try:
            return await client.check_comment(
                api_key=str(api_key).strip(),
                blog_url=blog_url,
                user_ip=str(getattr(data, "author_ip", "") or ""),
                user_agent=user_agent or "",
                comment_content=data.content,
                comment_author=getattr(data, "author_name", "") or "",
                comment_author_email=data.author_email or "",
                comment_author_url=data.author_url or "",
                api_url=await SiteOptionsService.get(self.db, API_URL_OPTION, ""),
            )
        except Exception as exc:  # noqa: BLE001
            # A comment must not fail to post because a third party is unwell.
            logger.warning("akismet_opinion_failed", error=str(exc))
            return None

    async def create_note(
        self,
        resource_type: str,
        resource_id: uuid.UUID,
        content: str,
        author_id: uuid.UUID | None = None,
        author_name: str | None = None,
        parent_id: uuid.UUID | None = None,
    ) -> BlogCommentResponse:
        """Attach a private team note to a post or page.

        WordPress stores a note as a comment row with
        ``comment_type = 'note'``: it shows up in the moderation table and in
        the per-post discussion, and no public query ever returns it. Modelling
        it any other way — a separate table, or a status value — would make one
        of those two surfaces wrong.

        The status is always APPROVED. A note held for moderation would be
        invisible to the team that wrote it, and it is by definition already
        reviewed. It is still excluded from every public read by the
        comment_type filter in ``list_comments``, ``_get_replies`` and the feed.
        """
        text = (content or "").strip()
        if not text:
            raise ValidationError("متن یادداشت نمی‌تواند خالی باشد")
        if resource_type not in (COMMENT_RESOURCE_BLOG_POST, COMMENT_RESOURCE_CMS_PAGE):
            raise ValidationError(f"نوع منبع نامعتبر: {resource_type}")

        note = BlogComment(
            # A note is a row on the same target, so the legacy post_id stays
            # filled for blog posts: the admin filter and the reply tree read it.
            post_id=resource_id if resource_type == COMMENT_RESOURCE_BLOG_POST else None,
            resource_type=resource_type,
            resource_id=resource_id,
            author_id=author_id,
            author_name=author_name,
            content=_clean_comment_content(text),
            status=CommentStatus.APPROVED,
            comment_type=COMMENT_TYPE_NOTE,
            parent_id=parent_id,
        )
        self.db.add(note)
        await self.db.commit()
        await self.db.refresh(note)
        response = self._build_response(note, moderation_fields=True)
        await self._attach_avatars([response])
        return response

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
        # The author fields, only where supplied. `model_fields_set` is what
        # separates "sent empty" from "not sent": without it, a moderator
        # fixing a typo in the body would also wipe the email address that
        # identifies the commenter.
        for field in ("author_name", "author_email", "author_url", "author_date"):
            if field in data.model_fields_set:
                value = getattr(data, field)
                # An empty string means "clear it", matching how every other
                # optional field in this project reads. Not a no-op, because a
                # spam comment with a bogus name is worth clearing.
                setattr(comment, field, value if value else None)

        await self.db.commit()
        await self.db.refresh(comment)

        logger.info("comment_updated", comment_id=str(comment_id))
        # Admin path: the moderation surface needs the email and the status.
        # Routed through _build_response so the "every response stages the
        # author email for the avatar pass" rule holds on this path too — it
        # does not call _attach_avatars today, and a future edit that starts
        # would otherwise silently lose the guest's Gravatar.
        return self._build_response(comment, moderation_fields=True)

    async def bulk_moderate(
        self,
        comment_ids: list[uuid.UUID],
        action: str,
    ) -> dict[str, Any]:
        """Moderate many comments at once, reporting each one's outcome.

        Built on the same principle as the post bulk action: one bad id must
        not abort the batch, and the response says what actually happened
        rather than a single boolean. A moderator selecting 40 comments may
        include one that vanished in another tab, and "40 approved" when 39
        were is a lie the UI would then repeat.

        ``trash`` here is the reversible state — a comment moved to TRASH can
        be restored. It is the state a spam wave should go to, so a mistaken
        bulk action is one click from undone.
        """
        allowed = {"approve", "unapprove", "spam", "trash", "restore", "delete"}
        if action not in allowed:
            from app.core.exceptions.handlers import ValidationError

            raise ValidationError(f"عملیات ناشناخته: {action}")

        target = {
            "approve": CommentStatus.APPROVED,
            "unapprove": CommentStatus.PENDING,
            "spam": CommentStatus.SPAM,
            "trash": CommentStatus.TRASH,
            "restore": CommentStatus.APPROVED,
        }.get(action)

        results: list[dict[str, Any]] = []
        ok = 0
        failed = 0
        # Rows whose status this batch actually changed, so each decision can be
        # reported back after the commit. Collected rather than submitted inline:
        # the calls would then run inside the try block that swallows per-row
        # failures, and a slow third party would stretch the batch — or, worse, a
        # failed submission would be reported as a failed moderation.
        moderated: list[BlogComment] = []
        for cid in comment_ids:
            try:
                comment = await self.db.get(BlogComment, cid)
                if comment is None:
                    raise NotFoundError("BlogComment", f"Comment {cid} not found")
                if action == "delete":
                    await self.db.delete(comment)
                else:
                    comment.status = target
                    moderated.append(comment)
                results.append({"id": str(cid), "ok": True})
                ok += 1
            except Exception as exc:  # noqa: BLE001 — one bad row must not abort the batch
                failed += 1
                results.append({"id": str(cid), "ok": False, "error": str(exc)})

        await self.db.commit()
        logger.info("comments_bulk_moderated", action=action, ok=ok, failed=failed)

        # The single highest-volume source of ground truth: a moderator clearing
        # a spam wave confirms forty decisions at once. Skipping it would leave
        # the service learning only from the one-comment-at-a-time path.
        if moderated and target is not None:
            try:
                from app.modules.blog.application import akismet_feedback

                for comment in moderated:
                    await akismet_feedback.report_moderation(
                        self.db, comment, status=target
                    )
            except Exception as exc:  # noqa: BLE001
                logger.warning("akismet_bulk_feedback_skipped", error=str(exc))

        return {
            "action": action,
            "ok": ok,
            "failed": failed,
            "total": len(comment_ids),
            "results": results,
        }

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
        """Change comment moderation status (approve, spam, trash).

        A plugin can veto or redirect the transition: a known-good commenter
        auto-approved, a wordlist forcing spam. Fired before the write, and an
        out-of-enum value from a hook is ignored rather than corrupting the row.
        """
        comment = await self.db.get(BlogComment, comment_id)
        if not comment:
            raise NotFoundError("BlogComment", f"Comment {comment_id} not found")

        from app.shared.plugins.registry import HOOK_COMMENT_BEFORE_MODERATE, registry

        requested = await registry.apply_filters(
            HOOK_COMMENT_BEFORE_MODERATE,
            status,
            comment_id=str(comment_id),
            old_status=comment.status.value,
            author_id=str(comment.author_id) if comment.author_id else None,
        )
        if isinstance(requested, CommentStatus):
            status = requested
        elif isinstance(requested, str):
            try:
                status = CommentStatus(requested)
            except ValueError:
                logger.warning(
                    "comment_moderate_hook_bad_status",
                    comment_id=str(comment_id),
                    value=str(requested)[:60],
                )

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

        # The moderator's decision is the only ground truth this system has, so
        # it goes back to Akismet when the site is configured. After the commit
        # and outside the try blocks below: it must never be able to fail or
        # delay a moderation action that has already been recorded.
        try:
            from app.modules.blog.application import akismet_feedback

            await akismet_feedback.report_moderation(
                self.db, comment, status=status
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "akismet_feedback_skipped", comment_id=str(comment_id), error=str(exc)
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
                # wp_notify_comment: the "your comment is live" mail. Only to
                # an address the commenter gave — the service returns early
                # otherwise, so a comment from an account with no email on file
                # sends nothing rather than a guessed one.
                await CommentEmailService(self.db).notify_commenter_approved(
                    comment_author_name=comment.author_name,
                    comment_author_email=comment.author_email,
                    post_title=post.title if post else "",
                    post_slug=post.slug if post else "",
                    comment_content=comment.content,
                    site_url=await self._site_url(),
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "comment_approved_notify_failed",
                    comment_id=str(comment_id),
                    error=str(exc),
                )

        return self._build_response(comment, moderation_fields=True)

    async def get_comment(self, comment_id: uuid.UUID) -> BlogCommentResponse:
        """Fetch a single comment by ID."""
        comment = await self.db.get(BlogComment, comment_id)
        if not comment:
            raise NotFoundError("BlogComment", f"Comment {comment_id} not found")
        response = self._build_response(comment, moderation_fields=False)
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
        comment_type: str | None = None,
        search: str | None = None,
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

        ``search`` matches the text a moderator would search a comment by —
        body, author name, email or website — because a spammer's tells are
        usually in one of those rather than in the comment itself. Applied
        here rather than in the route so the storefront and the moderation
        table cannot disagree about what "search" means.
        """
        stmt = select(BlogComment)

        # Notes never leave the moderation surface. Every public read goes
        # through this method, so the type filter sits at the top of the query
        # rather than being left to each route to remember. The admin table is
        # the one caller that passes include_moderation_fields, and it shows
        # notes too — so it only narrows when it asks to.
        if comment_type is not None:
            stmt = stmt.where(BlogComment.comment_type == comment_type)
        elif not include_moderation_fields:
            stmt = stmt.where(BlogComment.comment_type == COMMENT_TYPE_COMMENT)

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

        if search:
            needle = f"%{search.strip()}%"
            stmt = stmt.where(
                or_(
                    BlogComment.content.ilike(needle),
                    BlogComment.author_name.ilike(needle),
                    BlogComment.author_email.ilike(needle),
                    BlogComment.author_url.ilike(needle),
                )
            )

        # Only fetch top-level comments (no parent) when threading
        if include_replies:
            stmt = stmt.where(BlogComment.parent_id.is_(None))

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.db.execute(count_stmt)).scalar_one()

        if page_size is None:
            page_size = await self._comments_per_page_setting()
        stmt = (
            stmt.order_by(*(await self._comment_order()))
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
            response = self._build_response(comment, moderation_fields=include_moderation_fields)
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

        ``BlogCommentResponse`` deliberately omits ``author_email`` — a public
        reader has no business receiving it — so the guest fallback reads the
        email from the ``_email_by_comment`` side table, not off the response.
        Reading it off the response raised AttributeError and 500'd every
        guest comment, which is most of them on a storefront.
        """
        from app.shared.content.gravatar import (
            avatar_options,
            avatars_for_users,
            resolve_avatar_url,
        )

        # Site-wide avatar settings (WordPress show_avatars/avatar_default/
        # avatar_rating), read once for the whole batch. Off means the operator
        # hid avatars site-wide: both the uploaded-image branch and the Gravatar
        # branch must honour it, or the toggle would only hide half of them.
        options = await avatar_options(self.db)

        author_ids = [c.author_id for c in comments if c.author_id]
        resolved = await avatars_for_users(self.db, author_ids, options=options)

        for comment in comments:
            if comment.author_id and comment.author_id in resolved:
                comment.author_avatar_url = resolved[comment.author_id]
            else:
                # A guest, or an author with neither a profile image nor a
                # row in the users table this batch: Gravatar by email only.
                # The email never leaves the server: only the derived URL does.
                email = self._email_by_comment.get(str(comment.id))
                comment.author_avatar_url = resolve_avatar_url(
                    local_url=None, email=email, options=options
                )
            if comment.replies:
                await self._attach_avatars(comment.replies)

    def _build_response(
        self,
        comment: BlogComment, *, moderation_fields: bool
    ) -> BlogCommentResponse:
        """Project a row onto the public or the moderation schema.

        Not a staticmethod any more: staging the author email for the avatar
        pass needs the instance's map.

        Splitting this out keeps the "which schema" decision in one place, so a
        new call site cannot accidentally expose ``author_email`` by forgetting
        to think about it.

        The author email is also staged here for the guest-Gravatar fallback.
        Doing it in this one method means every path that builds a response —
        list, thread, create, update — has it, rather than each call site
        remembering to.
        """
        self._email_by_comment[str(comment.id)] = comment.author_email
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

        stmt = select(BlogComment).where(
            BlogComment.parent_id == parent_id,
            # A note is threaded like a comment but is not one. Reading replies
            # is the path a public comment view takes, so the filter belongs on
            # the query rather than on the caller.
            BlogComment.comment_type == COMMENT_TYPE_COMMENT,
        )
        if status is not None:
            stmt = stmt.where(BlogComment.status == status)
        # Same setting as the top-level list. Reading replies is the path a
        # public comment view takes, so leaving this ascending would make
        # `comment_order` reverse the thread and then re-sort its replies the
        # other way — the setting would appear to work on the first screen and
        # not on the second.
        stmt = stmt.order_by(*(await self._comment_order()))
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
            # The count renders as a public badge under every post, so a note
            # in it leaks the note's existence even though its text stays
            # private.
            BlogComment.comment_type == COMMENT_TYPE_COMMENT,
        )
        return (await self.db.execute(stmt)).scalar_one()

    async def count_pending_comments(self) -> dict[str, int]:
        """How many comments are waiting, and how many went to spam.

        WordPress's `awaiting-mod` bubble. The moderator who does not know a
        comment is sitting unanswered does not answer it, so this number is the
        difference between a store that answers reviews in an hour and one that
        finds them a week later.

        Pending and spam are counted together but reported apart, because they
        are different work: pending wants a decision, spam wants a sweep. A
        single number would let a spam wave look like a moderation backlog.

        Notes are excluded — they are the moderator's own private annotations
        on the moderation table, and counting them would inflate the number
        with rows the same person wrote.
        """
        stmt = (
            select(BlogComment.status, func.count(BlogComment.id))
            .where(
                BlogComment.status.in_([CommentStatus.PENDING, CommentStatus.SPAM]),
                BlogComment.comment_type == COMMENT_TYPE_COMMENT,
            )
            .group_by(BlogComment.status)
        )
        rows = (await self.db.execute(stmt)).all()
        counts = {status: n for status, n in rows}
        return {
            "pending": int(counts.get(CommentStatus.PENDING, 0)),
            "spam": int(counts.get(CommentStatus.SPAM, 0)),
        }

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
            BlogComment.comment_type == COMMENT_TYPE_COMMENT,
        )
        return (await self.db.execute(stmt)).scalar_one()
