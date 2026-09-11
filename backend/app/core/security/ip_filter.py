"""Dynamic IP Blacklist and Protection Middleware.

Provides real-time IP banning via Redis without needing proxy reloads.
Compatible with automated responses from CrowdSec or internal anomaly detectors.
"""

from __future__ import annotations

import logging
from typing import Callable

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.cache.redis import get_redis
from app.core.security.rate_limiter import get_real_client_ip

logger = logging.getLogger("security.ip_filter")

_BLACKLIST_PREFIX = "security:ip_blacklist:"


async def ban_ip(ip: str, duration_seconds: int = 86400, reason: str = "abusive_traffic") -> None:
    """Ban an IP address for a given duration (default 24h)."""
    try:
        client = await get_redis()
        key = f"{_BLACKLIST_PREFIX}{ip.strip()}"
        await client.set(key, reason, ex=duration_seconds)
        logger.warning("IP address banned: ip=%s duration=%ds reason=%s", ip, duration_seconds, reason)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to ban IP %s: %s", ip, exc)


async def unban_ip(ip: str) -> None:
    """Remove an IP address from the blacklist."""
    try:
        client = await get_redis()
        key = f"{_BLACKLIST_PREFIX}{ip.strip()}"
        await client.delete(key)
        logger.info("IP address unbanned: ip=%s", ip)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to unban IP %s: %s", ip, exc)


async def is_ip_banned(ip: str) -> bool:
    """Check whether an IP address is currently banned."""
    try:
        client = await get_redis()
        key = f"{_BLACKLIST_PREFIX}{ip.strip()}"
        result = await client.get(key)
        return result is not None
    except Exception:  # noqa: BLE001
        return False


class IPFilterMiddleware(BaseHTTPMiddleware):
    """FastAPI/Starlette middleware that inspects client IP against the Redis blacklist."""

    async def dispatch(self, request: Request, call_next: Callable[[Request], Response]) -> Response:
        client_ip = get_real_client_ip(request)

        # Skip check for internal metrics & health checks
        if request.url.path in ("/healthz", "/readyz", "/metrics"):
            return await call_next(request)

        if await is_ip_banned(client_ip):
            logger.warning("Blocked request from banned IP: %s path=%s", client_ip, request.url.path)
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={
                    "error": "access_denied",
                    "message": "دسترسی این آدرس IP به دلایل امنیتی مسدود شده است.",
                },
            )

        return await call_next(request)
