"""Post locking: prevent concurrent editing (WordPress heartbeat parity).

When a user opens a post for editing, a lock is acquired in Redis with a TTL.
Other users see a warning that the post is being edited. The lock auto-expires
if the editor closes the page or stops sending heartbeats.

Usage:
    lock = PostLockService(redis)
    acquired = await lock.acquire(post_id, user_id)
    holder = await lock.get_lock_holder(post_id)
    await lock.release(post_id, user_id)
    await lock.heartbeat(post_id, user_id)  # extend TTL
"""

from __future__ import annotations

import uuid

import structlog

from app.core.cache.redis import get_redis

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

LOCK_TTL_SECONDS = 120  # 2 minutes; heartbeat extends it
LOCK_KEY_PREFIX = "blog:post_lock:"


class PostLockService:
    """Redis-based post editing lock."""

    @staticmethod
    def _key(post_id: uuid.UUID) -> str:
        return f"{LOCK_KEY_PREFIX}{post_id}"

    @staticmethod
    async def acquire(post_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """Try to acquire the editing lock. Returns True if acquired or already held."""
        try:
            client = await get_redis()
            key = PostLockService._key(post_id)
            current = await client.get(key)
            if current is not None:
                if current == str(user_id):
                    # Already held by this user — extend
                    await client.expire(key, LOCK_TTL_SECONDS)
                    return True
                return False  # held by someone else
            await client.set(key, str(user_id), ex=LOCK_TTL_SECONDS)
            logger.info("post_lock_acquired", post_id=str(post_id), user_id=str(user_id))
            return True
        except Exception:
            logger.warning("post_lock_acquire_failed", post_id=str(post_id))
            return True  # fail open: don't block editing if Redis is down

    @staticmethod
    async def release(post_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """Release the lock only if held by the given user."""
        try:
            client = await get_redis()
            key = PostLockService._key(post_id)
            current = await client.get(key)
            if current == str(user_id):
                await client.delete(key)
                logger.info("post_lock_released", post_id=str(post_id))
                return True
            return False
        except Exception:
            logger.warning("post_lock_release_failed", post_id=str(post_id))
            return False

    @staticmethod
    async def heartbeat(post_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """Extend the lock TTL (called periodically by the editor frontend)."""
        try:
            client = await get_redis()
            key = PostLockService._key(post_id)
            current = await client.get(key)
            if current == str(user_id):
                await client.expire(key, LOCK_TTL_SECONDS)
                return True
            return False
        except Exception:
            return False

    @staticmethod
    async def get_lock_holder(post_id: uuid.UUID) -> uuid.UUID | None:
        """Return the user ID holding the lock, or None."""
        try:
            client = await get_redis()
            key = PostLockService._key(post_id)
            current = await client.get(key)
            if current:
                return uuid.UUID(current)
            return None
        except Exception:
            return None

    @staticmethod
    async def force_release(post_id: uuid.UUID) -> None:
        """Admin override: release lock regardless of holder."""
        try:
            client = await get_redis()
            await client.delete(PostLockService._key(post_id))
            logger.info("post_lock_force_released", post_id=str(post_id))
        except Exception:
            pass
