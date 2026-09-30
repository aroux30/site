"""Blog post autosave service (WordPress parity).

Stores periodic draft snapshots in Redis so editors don't lose work.
The frontend sends autosave requests every 30-60 seconds while editing.
Each post has exactly one autosave slot per user (latest wins).

Flow:
1. Frontend calls POST /admin/blog/posts/{id}/autosave with partial content
2. Backend stores in Redis with TTL (24h)
3. On page load, frontend checks GET /admin/blog/posts/{id}/autosave
4. If autosave is newer than saved version, offer to restore
5. On explicit save, autosave is cleared
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

import structlog

from app.core.cache.redis import get_redis

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

AUTOSAVE_TTL = 86400  # 24 hours
AUTOSAVE_KEY_PREFIX = "blog:autosave:"


class AutosaveService:
    """Redis-backed autosave for blog post editing."""

    @staticmethod
    def _key(post_id: uuid.UUID, user_id: uuid.UUID) -> str:
        return f"{AUTOSAVE_KEY_PREFIX}{post_id}:{user_id}"

    @staticmethod
    async def save(
        post_id: uuid.UUID,
        user_id: uuid.UUID,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """Store an autosave snapshot. Returns the stored data with timestamp."""
        try:
            client = await get_redis()
            key = AutosaveService._key(post_id, user_id)
            payload = {
                "post_id": str(post_id),
                "user_id": str(user_id),
                "data": data,
                "saved_at": datetime.now(UTC).isoformat(),
            }
            await client.set(key, json.dumps(payload, ensure_ascii=False), ex=AUTOSAVE_TTL)
            logger.debug("autosave_stored", post_id=str(post_id), user_id=str(user_id))
            return payload
        except Exception:
            logger.warning("autosave_store_failed", post_id=str(post_id))
            return {}

    @staticmethod
    async def get(
        post_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> dict[str, Any] | None:
        """Retrieve the latest autosave for a post+user, or None."""
        try:
            client = await get_redis()
            key = AutosaveService._key(post_id, user_id)
            raw = await client.get(key)
            if raw:
                return json.loads(raw)
            return None
        except Exception:
            logger.warning("autosave_get_failed", post_id=str(post_id))
            return None

    @staticmethod
    async def clear(
        post_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> bool:
        """Clear autosave after an explicit save."""
        try:
            client = await get_redis()
            key = AutosaveService._key(post_id, user_id)
            deleted = await client.delete(key)
            if deleted:
                logger.debug("autosave_cleared", post_id=str(post_id))
            return bool(deleted)
        except Exception:
            return False

    @staticmethod
    async def has_autosave(
        post_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> bool:
        """Check if an autosave exists without fetching the full payload."""
        try:
            client = await get_redis()
            key = AutosaveService._key(post_id, user_id)
            return bool(await client.exists(key))
        except Exception:
            return False
