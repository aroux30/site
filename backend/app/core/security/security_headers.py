"""HTTP Security Headers Middleware for FastAPI.

Applies Defense-in-Depth HTTP security headers across all responses:
- X-Content-Type-Options: nosniff
- X-Frame-Options: SAMEORIGIN (clickjacking defense)
- X-XSS-Protection: 1; mode=block
- Referrer-Policy: strict-origin-when-cross-origin
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from fastapi import Request, Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Enforces essential security headers on all outgoing HTTP responses."""

    # API responses carrying account/order/payment data must never be stored
    # by shared caches or the browser back/forward cache.
    _NO_STORE_PREFIXES = ("/api/v1/auth", "/api/v1/users", "/api/v1/orders",
                          "/api/v1/payments", "/api/v1/wallet", "/api/v1/admin")

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("X-XSS-Protection", "1; mode=block")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")

        path = request.url.path
        if any(path.startswith(p) for p in self._NO_STORE_PREFIXES):
            response.headers.setdefault("Cache-Control", "no-store")
        return response
