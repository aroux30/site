"""Redis client setup and caching utilities.

Provides an async Redis connection pool, low-level ``get`` / ``set`` helpers,
and a :func:`cached` decorator for automatic function-result caching.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any, ParamSpec, TypeVar

import redis.asyncio as aioredis
from redis.asyncio import ConnectionPool, Redis

from app.core.config.settings import get_settings

_P = ParamSpec("_P")
_T = TypeVar("_T")

_pool: ConnectionPool | None = None
_client: Redis | None = None  # type: ignore[type-arg]


async def init_redis() -> Redis:  # type: ignore[type-arg]
    """Create (or return) the module-level async Redis client."""
    global _pool, _client  # noqa: PLW0603
    settings = get_settings()
    if _client is None:
        _pool = ConnectionPool.from_url(
            settings.redis_url_str,
            max_connections=50,
            decode_responses=True,
        )
        _client = Redis(connection_pool=_pool)
    return _client


async def close_redis() -> None:
    """Gracefully close the Redis connection pool."""
    global _client, _pool  # noqa: PLW0603
    if _client is not None:
        await _client.aclose()
        _client = None
    if _pool is not None:
        await _pool.disconnect()
        _pool = None


async def get_redis() -> Redis:  # type: ignore[type-arg]
    """FastAPI dependency – returns the Redis client."""
    if _client is None:
        return await init_redis()
    return _client


# ── Low-level helpers ─────────────────────────────────────────────────────

_PREFIX = get_settings().REDIS_KEY_PREFIX


def _key(name: str) -> str:
    return f"{_PREFIX}{name}"


async def cache_get(key: str) -> str | None:
    """Get a value from cache by key (prefix is prepended automatically)."""
    client = await get_redis()
    return await client.get(_key(key))


async def cache_set(key: str, value: str, ttl: int | None = None) -> None:
    """Set a value in cache (prefix is prepended automatically)."""
    client = await get_redis()
    settings = get_settings()
    ex = ttl if ttl is not None else settings.REDIS_DEFAULT_TTL
    await client.set(_key(key), value, ex=ex)


async def cache_delete(key: str) -> None:
    """Delete a key from cache."""
    client = await get_redis()
    await client.delete(_key(key))


async def cache_delete_pattern(pattern: str) -> int:
    """Delete all keys matching *pattern* (glob-style)."""
    client = await get_redis()
    deleted = 0
    async for key in client.scan_iter(match=_key(pattern)):
        await client.delete(key)
        deleted += 1
    return deleted


# ── Decorator ─────────────────────────────────────────────────────────────


def cached(
    key_template: str,
    ttl: int | None = None,
) -> Callable[[Callable[_P, Awaitable[Any]]], Callable[_P, Awaitable[Any]]]:
    """Cache the JSON-serialisable return value of an async function.

    ``key_template`` may contain ``{arg_name}`` placeholders that are filled
    from the decorated function's arguments::

        @cached("product:{product_id}", ttl=600)
        async def get_product(product_id: uuid.UUID) -> dict: ...
    """

    def decorator(fn: Callable[_P, Awaitable[Any]]) -> Callable[_P, Awaitable[Any]]:
        @wraps(fn)
        async def wrapper(*args: _P.args, **kwargs: _P.kwargs) -> Any:
            import inspect

            sig = inspect.signature(fn)
            bound = sig.bind(*args, **kwargs)
            bound.apply_defaults()
            cache_key = key_template.format(**{k: str(v) for k, v in bound.arguments.items()})

            hit = await cache_get(cache_key)
            if hit is not None:
                return json.loads(hit)

            result = await fn(*args, **kwargs)
            await cache_set(cache_key, json.dumps(result, default=str), ttl=ttl)
            return result

        return wrapper

    return decorator
