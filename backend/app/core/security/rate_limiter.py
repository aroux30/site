"""Multi-layered Rate Limiting and Brute Force Protection.

Combines SlowAPI (token-bucket / moving-window) with Redis-backed multi-key
failed-attempt tracking, progressive lockouts, and IP resolution.
Follows OWASP authentication guidelines.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import HTTPException, Request, status
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.core.cache.redis import get_redis
from app.core.config.settings import get_settings
from app.core.logging.security_audit import log_security_event

logger = logging.getLogger("security.ratelimit")
settings = get_settings()


def get_real_client_ip(request: Request) -> str:
    """Safely extract client IP, prioritizing trusted reverse proxy headers."""
    # 1. X-Forwarded-For (client, proxy1, proxy2, ...)
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()
        if client_ip:
            return client_ip

    # 2. X-Real-IP
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()

    # 3. Direct socket client host
    if request.client and request.client.host:
        return request.client.host

    return "127.0.0.1"


# Initialize SlowAPI limiter
limiter = Limiter(
    key_func=get_real_client_ip,
    storage_uri=settings.redis_url_str,
    strategy="moving-window",
    default_limits=[],  # explicitly configured per route
)


class BruteForceProtector:
    """Tracks failed authentication attempts per identifier (phone/email/IP)

    and applies progressive lockouts to defeat credential stuffing and brute force.
    """

    def __init__(
        self,
        max_attempts: int = 5,
        lockout_seconds: int = 900,  # 15 minutes
        window_seconds: int = 900,
    ) -> None:
        self.max_attempts = max_attempts
        self.lockout_seconds = lockout_seconds
        self.window_seconds = window_seconds

    @staticmethod
    def _normalize_key(identifier: str) -> str:
        return identifier.strip().lower().replace("+", "")

    def _attempts_key(self, identifier: str) -> str:
        return f"bf:attempts:{self._normalize_key(identifier)}"

    def _lockout_key(self, identifier: str) -> str:
        return f"bf:locked:{self._normalize_key(identifier)}"

    async def check_lockout(self, identifier: str) -> None:
        """Check if the given identifier or IP is currently locked out."""
        try:
            client = await get_redis()
            lock_key = self._lockout_key(identifier)
            is_locked = await client.get(lock_key)
            if is_locked:
                ttl = await client.ttl(lock_key)
                remaining = max(ttl, 1)
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=(
                        f"به دلیل تلاش‌های ناموفق متعدد، حساب شما موقتاً مسدود شده است. "
                        f"لطفاً {remaining} ثانیه دیگر تلاش کنید."
                    ),
                    headers={"Retry-After": str(remaining)},
                )
        except HTTPException:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to check lockout in Redis: %s", exc)

    async def record_failure(self, identifier: str, ip: str | None = None) -> int:
        """Record a failed login/OTP attempt.

        Locks account if max attempts exceeded.
        """
        try:
            client = await get_redis()
            att_key = self._attempts_key(identifier)
            attempts = await client.incr(att_key)

            if attempts == 1:
                await client.expire(att_key, self.window_seconds)

            if attempts >= self.max_attempts:
                lock_key = self._lockout_key(identifier)
                await client.set(lock_key, "1", ex=self.lockout_seconds)
                await client.delete(att_key)
                log_security_event(
                    event="brute_force_lockout",
                    ip_address=ip,
                    identifier=identifier,
                    success=False,
                    reason=f"Exceeded max failed attempts ({attempts})",
                )
                logger.warning(
                    "Account locked due to brute force: identifier=%s ip=%s attempts=%d",
                    identifier,
                    ip,
                    attempts,
                )
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=(
                        f"به دلیل تلاش‌های ناموفق بیش از حد، دسترسی شما به مدت "
                        f"{self.lockout_seconds // 60} دقیقه مسدود گردید."
                    ),
                    headers={"Retry-After": str(self.lockout_seconds)},
                )
            log_security_event(
                event="auth_failed_attempt",
                ip_address=ip,
                identifier=identifier,
                success=False,
                reason=f"Attempt {attempts} of {self.max_attempts}",
            )
            # OWASP Progressive Delay: Throttles multi-threaded password guessing bots
            if attempts > 1:
                delay = min((attempts - 1) * 0.5, 2.5)
                await asyncio.sleep(delay)

            return attempts
        except HTTPException:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to record failure in Redis: %s", exc)
            return 1

    async def record_success(self, identifier: str) -> None:
        """Clear failed attempt counters upon successful authentication."""
        try:
            client = await get_redis()
            att_key = self._attempts_key(identifier)
            await client.delete(att_key)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to reset failure counter in Redis: %s", exc)


# Global default protector instance
brute_force_protector = BruteForceProtector(
    max_attempts=5,
    lockout_seconds=900,  # 15 minutes lockout
    window_seconds=900,
)

# Strict protector for OTP verification (fewer attempts allowed)
otp_brute_force_protector = BruteForceProtector(
    max_attempts=3,
    lockout_seconds=600,  # 10 minutes lockout
    window_seconds=600,
)
