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
    from collections.abc import Callable

    from fastapi import Request, Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Enforces essential security headers on all outgoing HTTP responses."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Response]
    ) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("X-XSS-Protection", "1; mode=block")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        return response
