"""Author archive resolution (WordPress parity: /author/<slug>).

The permalink structure accepts ``%author%`` and the blog has a full post
model, but nothing could answer "which posts did this person write?" — the
user table had no public identifier at all. ``users.author_slug`` supplies one,
backfilled by migration q7r8s9t0u1v2 and stable thereafter: it is read from the
row, never derived from the display name, because a rename must not move a
published URL.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import func, select

from app.core.exceptions.handlers import NotFoundError
from app.modules.blog.domain.models import BlogPost, BlogPostStatus
from app.modules.blog.schemas.blog import (
    BlogAuthorArchiveResponse,
    BlogAuthorResponse,
)
from app.modules.users.domain.models import User, UserProfile

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class AuthorService:
    def __init__(self, db: "AsyncSession") -> None:
        self.db = db

    async def get_archive(
        self,
        *,
        slug: str,
        page: int = 1,
        page_size: int = 10,
        public_only: bool = True,
    ) -> BlogAuthorArchiveResponse:
        """One author plus their published posts, paginated.

        Raises ``NotFoundError`` for an unknown slug so the route returns 404
        rather than an empty archive that looks like a real author with no
        writing yet.
        """
        author = await self._resolve(slug=slug)
        if author is None:
            raise NotFoundError("Author", f"Author with slug '{slug}' not found")

        # Count first, then page: the count must respect the same visibility
        # filter as the page, or a private post inflates the total.
        count_stmt = select(func.count()).select_from(BlogPost).where(
            BlogPost.author_id == author.id,
            BlogPost.status == BlogPostStatus.PUBLISHED,
            BlogPost.deleted_at.is_(None),
        )
        if public_only:
            count_stmt = count_stmt.where(
                BlogPost.visibility == "public",
            )
        total = (await self.db.execute(count_stmt)).scalar_one() or 0

        stmt = (
            select(BlogPost)
            .where(
                BlogPost.author_id == author.id,
                BlogPost.status == BlogPostStatus.PUBLISHED,
                BlogPost.deleted_at.is_(None),
            )
            .order_by(BlogPost.published_at.desc().nullslast(), BlogPost.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        if public_only:
            stmt = stmt.where(BlogPost.visibility == "public")
        posts = (await self.db.execute(stmt)).scalars().all()

        from app.modules.blog.application.blog_service import BlogService

        svc = BlogService(self.db)
        items = []
        for post in posts:
            views = await svc.get_view_count(post.id)
            items.append(
                svc._post_to_response(  # noqa: SLF001 - same module family
                    post,
                    views,
                    await svc.get_author_name(post.author_id),
                    author_slug=slug,
                )
            )

        total_pages = (total + page_size - 1) // page_size if page_size else 0
        archive = BlogAuthorArchiveResponse.model_validate(
            {
                "author": {
                    "slug": slug,
                    "name": _display_name(author),
                    "bio": getattr(author, "bio", None),
                    "avatar_url": getattr(author, "avatar_url", None),
                    "post_count": total,
                },
                "posts": {
                    "items": items,
                    "total": total,
                    "page": page,
                    "page_size": page_size,
                    "total_pages": total_pages,
                    "has_next": page < total_pages,
                    "has_prev": page > 1,
                },
            }
        )
        await logger.ainfo("author_archive_viewed", slug=slug, posts=total)
        return archive

    async def _resolve(self, *, slug: str) -> object | None:
        """The user row behind an author slug, or None.

        Joins the profile so the display name and avatar come back in the same
        query rather than a second round-trip per field.
        """
        stmt = (
            select(User, UserProfile)
            .outerjoin(UserProfile, UserProfile.user_id == User.id)
            .where(User.author_slug == slug, User.deleted_at.is_(None))
        )
        row = (await self.db.execute(stmt)).first()
        if row is None:
            return None
        user, profile = row
        return _AuthorRow(
            id=user.id,
            phone=user.phone,
            first_name=getattr(profile, "first_name", None),
            last_name=getattr(profile, "last_name", None),
            # Without this the field exists on the row and is never filled, and
            # a chosen display name silently loses to first+last everywhere.
            display_name=getattr(profile, "display_name", None),
            bio=getattr(profile, "bio", None),
            avatar_url=getattr(profile, "avatar_url", None),
        )

    async def list_authors(self, *, limit: int = 50) -> list[BlogAuthorResponse]:
        """Authors with at least one published post, for a directory page."""
        from sqlalchemy import desc

        stmt = (
            select(
                User.author_slug,
                func.count(BlogPost.id).label("post_count"),
            )
            .join(BlogPost, BlogPost.author_id == User.id)
            .where(
                User.author_slug.is_not(None),
                User.deleted_at.is_(None),
                BlogPost.status == BlogPostStatus.PUBLISHED,
                BlogPost.deleted_at.is_(None),
            )
            .group_by(User.author_slug)
            .order_by(desc("post_count"))
            .limit(limit)
        )
        rows = (await self.db.execute(stmt)).all()
        if not rows:
            return []
        users = await self._names_for([r[0] for r in rows])
        return [
            BlogAuthorResponse(
                slug=slug,
                name=users.get(slug, slug),
                post_count=count,
            )
            for slug, count in rows
        ]

    async def _names_for(self, slugs: list[str]) -> dict[str, str]:
        stmt = (
            select(
                User.author_slug,
                UserProfile.first_name,
                UserProfile.last_name,
                UserProfile.display_name,
            )
            .outerjoin(UserProfile, UserProfile.user_id == User.id)
            .where(User.author_slug.in_(slugs))
        )
        out: dict[str, str] = {}
        for slug, first, last, display in (await self.db.execute(stmt)).all():
            if slug:
                # `display_name` first: it is the name the person chose to
                # publish, and falling straight to first+last would make it
                # a field nobody can set and see take effect.
                out[slug] = (
                    (display or "").strip()
                    or f"{first or ''} {last or ''}".strip()
                    or slug
                )
        return out


class _AuthorRow:
    """The subset of user+profile an archive needs."""

    __slots__ = (
        "id", "phone", "first_name", "last_name", "display_name",
        "bio", "avatar_url",
    )

    def __init__(
        self,
        *,
        id: uuid.UUID,
        phone: str,
        first_name: str | None,
        last_name: str | None,
        display_name: str | None = None,
        bio: str | None,
        avatar_url: str | None,
    ) -> None:
        self.id = id
        self.phone = phone
        self.first_name = first_name
        self.last_name = last_name
        self.display_name = display_name
        self.bio = bio
        self.avatar_url = avatar_url


def _display_name(author: _AuthorRow) -> str:
    # The published name wins. WordPress calls this the "Display name" and
    # separates it from the account name for exactly this reason: a person
    # writes under a name that is not their legal first and last.
    chosen = (getattr(author, "display_name", None) or "").strip()
    name = chosen or f"{author.first_name or ''} {author.last_name or ''}".strip()
    # Same fallback as the post listing: a profile with no name is shown by
    # the tail of its phone, never as an empty byline.
    return name or f"کاربر {author.phone[-4:]}"
