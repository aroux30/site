"""Redis client setup, caching utilities, and observability hooks.

Provides an async Redis connection pool, low-level ``get`` / ``set`` helpers,
cache hit/miss tracking, and operation latency monitoring.
"""

from __future__ import annotations

import contextlib
import json
import time
from functools import wraps
from typing import TYPE_CHECKING, ParamSpec, TypeVar, cast

import structlog
from redis.asyncio import ConnectionPool, Redis

from app.core.config.settings import get_settings
from app.core.observability.metrics import (
    CACHE_HIT,
    CACHE_MISS,
    REDIS_ERRORS,
    REDIS_OPERATION_DURATION,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_P = ParamSpec("_P")
_T = TypeVar("_T")

_pool: ConnectionPool | None = None
_client: Redis | None = None


async def init_redis() -> Redis:
    """Create (or return) the module-level async Redis client."""
    global _pool, _client
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
    global _client, _pool
    try:
        if _client is not None:
            with contextlib.suppress(Exception):
                await _client.aclose()
    finally:
        _client = None
    try:
        if _pool is not None:
            with contextlib.suppress(Exception):
                await _pool.disconnect()
    finally:
        _pool = None


async def get_redis() -> Redis:
    """FastAPI dependency – returns the Redis client."""
    if _client is None:
        return await init_redis()
    return _client


# ── Low-level helpers ─────────────────────────────────────────────────────

_PREFIX = get_settings().REDIS_KEY_PREFIX


def _key(name: str) -> str:
    return f"{_PREFIX}{name}"


async def cache_get(key: str) -> str | None:
    """Get a value from cache by key and record hit/miss metrics."""
    client = await get_redis()
    settings = get_settings()
    t0 = time.perf_counter()
    full_key = _key(key)

    try:
        val = await client.get(full_key)
        duration = time.perf_counter() - t0
        duration_ms = round(duration * 1000, 2)
        REDIS_OPERATION_DURATION.labels(operation="get").observe(duration)

        if val is not None:
            CACHE_HIT.labels(cache_name="redis").inc()
        else:
            CACHE_MISS.labels(cache_name="redis").inc()

        if duration_ms >= settings.REDIS_SLOW_OPERATION_THRESHOLD_MS:
            await logger.awarning(
                "slow_redis_operation",
                operation="GET",
                key=key,
                duration_ms=duration_ms,
                threshold_ms=settings.REDIS_SLOW_OPERATION_THRESHOLD_MS,
            )
        # decode_responses=True on the pool means the value is a str at runtime.
        return cast("str | None", val)
    except Exception as exc:
        duration = time.perf_counter() - t0
        REDIS_OPERATION_DURATION.labels(operation="get").observe(duration)
        REDIS_ERRORS.labels(operation="get", error_type=type(exc).__name__).inc()
        CACHE_MISS.labels(cache_name="redis").inc()
        await logger.aerror(
            "redis_get_error",
            operation="GET",
            key=key,
            error=str(exc),
        )
        return None


async def cache_set(key: str, value: str, ttl: int | None = None) -> None:
    """Set a value in cache with latency tracking."""
    client = await get_redis()
    settings = get_settings()
    ex = ttl if ttl is not None else settings.REDIS_DEFAULT_TTL
    t0 = time.perf_counter()
    full_key = _key(key)

    try:
        await client.set(full_key, value, ex=ex)
        duration = time.perf_counter() - t0
        duration_ms = round(duration * 1000, 2)
        REDIS_OPERATION_DURATION.labels(operation="set").observe(duration)

        if duration_ms >= settings.REDIS_SLOW_OPERATION_THRESHOLD_MS:
            await logger.awarning(
                "slow_redis_operation",
                operation="SET",
                key=key,
                duration_ms=duration_ms,
                threshold_ms=settings.REDIS_SLOW_OPERATION_THRESHOLD_MS,
            )
    except Exception as exc:
        duration = time.perf_counter() - t0
        REDIS_OPERATION_DURATION.labels(operation="set").observe(duration)
        REDIS_ERRORS.labels(operation="set", error_type=type(exc).__name__).inc()
        await logger.aerror(
            "redis_set_error",
            operation="SET",
            key=key,
            error=str(exc),
        )


async def cache_delete(key: str) -> None:
    """Delete a key from cache."""
    client = await get_redis()
    t0 = time.perf_counter()
    try:
        await client.delete(_key(key))
        duration = time.perf_counter() - t0
        REDIS_OPERATION_DURATION.labels(operation="delete").observe(duration)
    except Exception as exc:
        duration = time.perf_counter() - t0
        REDIS_OPERATION_DURATION.labels(operation="delete").observe(duration)
        REDIS_ERRORS.labels(operation="delete", error_type=type(exc).__name__).inc()
        await logger.aerror(
            "redis_delete_error",
            operation="DELETE",
            key=key,
            error=str(exc),
        )


async def cache_delete_pattern(pattern: str) -> int:
    """Delete all keys matching *pattern* (glob-style)."""
    client = await get_redis()
    deleted = 0
    t0 = time.perf_counter()
    try:
        async for key in client.scan_iter(match=_key(pattern)):
            await client.delete(key)
            deleted += 1
        duration = time.perf_counter() - t0
        REDIS_OPERATION_DURATION.labels(operation="delete_pattern").observe(duration)
    except Exception as exc:
        duration = time.perf_counter() - t0
        REDIS_OPERATION_DURATION.labels(operation="delete_pattern").observe(duration)
        REDIS_ERRORS.labels(operation="delete_pattern", error_type=type(exc).__name__).inc()
        await logger.aerror(
            "redis_delete_pattern_error",
            pattern=pattern,
            error=str(exc),
        )
    return deleted


# ── Decorator ─────────────────────────────────────────────────────────────


def cached(
    key_pattern: str,
    ttl: int | None = None,
) -> Callable[[Callable[_P, Awaitable[_T]]], Callable[_P, Awaitable[_T]]]:
    """Decorator to cache function results in Redis as JSON."""

    def decorator(func: Callable[_P, Awaitable[_T]]) -> Callable[_P, Awaitable[_T]]:
        @wraps(func)
        async def wrapper(*args: _P.args, **kwargs: _P.kwargs) -> _T:
            try:
                cache_key = key_pattern.format(*args, **kwargs)
            except (IndexError, KeyError):
                return await func(*args, **kwargs)

            raw = await cache_get(cache_key)
            if raw is not None:
                try:
                    return json.loads(raw)  # type: ignore[no-any-return]
                except (json.JSONDecodeError, TypeError):
                    pass

            result = await func(*args, **kwargs)
            try:
                serialized = json.dumps(result, default=str)
                await cache_set(cache_key, serialized, ttl=ttl)
            except (TypeError, ValueError):
                pass
            return result

        return wrapper

    return decorator
