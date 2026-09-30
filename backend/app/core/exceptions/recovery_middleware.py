"""Serves the recovery page while the site is paused.

Starlette middleware, because recovery mode must short-circuit *before* the
request reaches a route: a paused site's handlers may themselves be what is
broken. Health checks and the resume endpoint stay reachable — otherwise there
would be no way back without a shell.

Exempt paths are matched by prefix, because the app also serves the admin.
"""

from __future__ import annotations

import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import HTMLResponse, Response

from app.core.exceptions.recovery_mode import RecoveryMode

logger = logging.getLogger(__name__)

#: Never intercepted: the operator must be able to check the app and clear
#: the pause without a shell.
EXEMPT_PREFIXES = (
    "/healthz",
    "/api/health",
    "/deep-health",
    "/api/v1/settings/admin/recovery-mode",
    "/docs",
    "/openapi.json",
)


class RecoveryModeMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, exempt_prefixes: tuple[str, ...] = EXEMPT_PREFIXES) -> None:
        super().__init__(app)
        self._exempt = exempt_prefixes

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        if path.startswith(self._exempt) or not RecoveryMode.is_paused():
            return await call_next(request)

        state = RecoveryMode.state() or {}
        logger.warning(
            "recovery_mode_serving_page path=%s until=%s reference=%s",
            path,
            state.get("until"),
            state.get("reference"),
        )
        return HTMLResponse(
            content=RecoveryMode.response(),
            status_code=503,
            headers={
                # A crawler must not index the outage as site content, and a
                # CDN must not cache it past the pause window.
                "Cache-Control": "no-store, no-cache, must-revalidate",
                "Retry-After": "3600",
            },
        )
