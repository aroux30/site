"""Gravatar integration: generate avatar URLs from email (WordPress parity).

Usage:
    from app.shared.content.gravatar import gravatar_url, resolve_avatar_url
    url = gravatar_url("user@example.com", size=80)
    url = resolve_avatar_url(local_url=profile.avatar_url, email=user.email)
"""

from __future__ import annotations

import hashlib
import uuid
from typing import TYPE_CHECKING
from urllib.parse import urlencode

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


def gravatar_url(
    email: str | None,
    *,
    size: int = 80,
    default: str = "mp",
    rating: str = "g",
) -> str:
    """Generate a Gravatar URL for the given email.

    Args:
        email: User email address (None returns default avatar)
        size: Image size in pixels (1-2048)
        default: Default image type: "mp" (mystery person), "identicon", "retro", "robohash", "404"
        rating: Maximum rating: "g", "pg", "r", "x"

    Returns:
        Gravatar image URL
    """
    if not email:
        email = "nobody@example.com"

    email_hash = hashlib.md5(email.strip().lower().encode("utf-8")).hexdigest()
    params = urlencode({"s": size, "d": default, "r": rating})
    return f"https://www.gravatar.com/avatar/{email_hash}?{params}"


def gravatar_profile_url(email: str) -> str:
    """Generate a Gravatar profile URL."""
    email_hash = hashlib.md5(email.strip().lower().encode("utf-8")).hexdigest()
    return f"https://www.gravatar.com/{email_hash}"


def resolve_avatar_url(
    *,
    local_url: str | None,
    email: str | None,
    size: int = 80,
) -> str | None:
    """Pick an avatar for a user: an uploaded one first, else Gravatar.

    WordPress's ``get_avatar`` works this way — the locally uploaded image
    wins and Gravatar is the fallback. Returns None when there is neither,
    so a caller can render initials rather than a broken image.
    """
    if local_url:
        return local_url
    if email:
        return gravatar_url(email, size=size)
    return None


async def avatars_for_users(
    db: AsyncSession,
    user_ids: list[uuid.UUID],
    *,
    size: int = 80,
) -> dict[uuid.UUID, str]:
    """Resolve avatars for many users in two queries.

    Comment threads render dozens of authors at once; resolving each with its
    own SELECT would put an N+1 on the storefront's hottest read path.
    """
    if not user_ids:
        return {}

    from sqlalchemy import select

    from app.modules.users.domain.models import User, UserProfile

    unique_ids = list(dict.fromkeys(user_ids))

    email_rows = await db.execute(
        select(User.id, User.email).where(User.id.in_(unique_ids))
    )
    emails = {row.id: row.email for row in email_rows.all()}

    profile_rows = await db.execute(
        select(UserProfile.user_id, UserProfile.avatar_url).where(
            UserProfile.user_id.in_(unique_ids)
        )
    )
    avatars = {row.user_id: row.avatar_url for row in profile_rows.all()}

    resolved: dict[uuid.UUID, str] = {}
    for user_id in unique_ids:
        url = resolve_avatar_url(
            local_url=avatars.get(user_id),
            email=emails.get(user_id),
            size=size,
        )
        if url:
            resolved[user_id] = url
    return resolved
