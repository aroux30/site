"""Fast server-side user revocation (audit R4).

The access JWT is self-contained and trusted for its whole TTL (30 min by
default), which meant a *deactivated* account kept full access — including
admin endpoints — until the token expired. A full DB lookup per request is
too expensive; instead a tiny Redis denylist marks users whose access must
end immediately:

* Admin deactivation writes ``<prefix>user-revoked:<user_id>`` with a TTL
  longer than the access-token lifetime, so every request from that user is
  rejected until the denylist entry lapses (after which no valid token
  remains anyway).
* Sessions are also revoked so no refresh can outlive the deactivation.
* The check is one Redis GET per authenticated request and fails OPEN on
  Redis unavailability — the same degradation contract as the rate limiter —
  so a cache outage cannot take the whole API down.
"""

from __future__ import annotations

import uuid

import structlog

from app.core.cache.redis import get_redis
from app.core.config.settings import get_settings

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


def _deny_key(user_id: uuid.UUID) -> str:
    return f"{get_settings().REDIS_KEY_PREFIX}user-revoked:{user_id}"


def _jti_deny_key(jti: str) -> str:
    return f"{get_settings().REDIS_KEY_PREFIX}revoked-jti:{jti}"


def _deny_ttl_seconds() -> int:
    """Outlive the longest access token the denylist must neutralize."""
    return get_settings().ACCESS_TOKEN_EXPIRE_MINUTES * 60 + 60


async def denylist_jti(jti: str, ttl_seconds: int | None = None) -> None:
    """Block a specific JWT token jti until its expiry."""
    client = await get_redis()
    ttl = ttl_seconds or _deny_ttl_seconds()
    await client.set(_jti_deny_key(jti), "1", ex=ttl)
    await logger.ainfo("jti_denylisted", jti=jti, ttl_seconds=ttl)


async def is_jti_denied(jti: str) -> bool:
    """Check whether a specific token jti has been revoked."""
    try:
        client = await get_redis()
        return bool(await client.exists(_jti_deny_key(jti)))
    except Exception as exc:
        await logger.awarning("jti_revocation_check_failed_open", jti=jti, error=str(exc))
        return False


async def denylist_user(user_id: uuid.UUID) -> None:
    """Block every access token of this user until the denylist entry expires.

    Call on account deactivation / security suspension, together with session
    revocation (which kills refresh).
    """
    client = await get_redis()
    await client.set(_deny_key(user_id), "1", ex=_deny_ttl_seconds())
    await logger.ainfo(
        "user_access_denied_listed",
        user_id=str(user_id),
        ttl_seconds=_deny_ttl_seconds(),
    )


async def remove_from_denylist(user_id: uuid.UUID) -> None:
    """Re-activate access for a user (e.g. deactivation reverted)."""
    client = await get_redis()
    await client.delete(_deny_key(user_id))


async def is_user_denied(user_id: uuid.UUID) -> bool:
    """Whether the user's access is revoked.

    Redis is the fast path. On a Redis outage the DB ``is_active`` state is
    consulted instead of failing open: an active user keeps access
    (availability), but a blocked or soft-deleted user stays denied — a
    security block must never silently lapse because the cache is down.
    """
    try:
        client = await get_redis()
        return bool(await client.exists(_deny_key(user_id)))
    except Exception as exc:
        await logger.awarning(
            "user_revocation_redis_unavailable_falling_back_to_db",
            user_id=str(user_id),
            error=str(exc),
        )
        try:
            from app.core.database.session import async_session_factory
            from app.modules.users.domain.models import User

            async with async_session_factory() as db:
                user = await db.get(User, user_id)
            return user is not None and not user.is_active
        except Exception as db_exc:
            await logger.awarning(
                "user_revocation_check_failed_open",
                user_id=str(user_id),
                error=str(db_exc),
            )
            return False
