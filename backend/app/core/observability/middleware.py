"""Middleware for request-level observability.

- **Request ID**: injects a unique ``X-Request-ID`` header into every
  response (and into structlog context vars) for distributed tracing.
- **Timing**: records request duration in Prometheus histograms and logs
  a structured access log entry on completion.
"""

from __future__ import annotations

import time
import uuid
from typing import TYPE_CHECKING, Any

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.core.observability.metrics import (
    REQUEST_COUNT,
    REQUEST_DURATION,
    REQUESTS_IN_PROGRESS,
)

if TYPE_CHECKING:
    from starlette.requests import Request
    from starlette.responses import Response

logger: structlog.stdlib.BoundLogger = structlog.get_logger()

# Paths that should not be logged / metered (liveness probes, metrics scrape)
_SKIP_PATHS: set[str] = {"/healthz", "/readyz", "/metrics"}


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Ensure every request has a unique correlation ID."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        # Bind to structlog context for the duration of the request
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class TimingMiddleware(BaseHTTPMiddleware):
    """Record request latency and emit structured access logs."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path
        method = request.method

        if path in _SKIP_PATHS:
            return await call_next(request)

        # Use a simplified path label to avoid high-cardinality in Prometheus
        route_path = self._route_path(request) or path

        REQUESTS_IN_PROGRESS.labels(method=method, endpoint=route_path).inc()
        start = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            REQUEST_COUNT.labels(method=method, endpoint=route_path, status_code=500).inc()
            raise
        finally:
            duration = time.perf_counter() - start
            REQUESTS_IN_PROGRESS.labels(method=method, endpoint=route_path).dec()

        REQUEST_DURATION.labels(method=method, endpoint=route_path).observe(duration)
        REQUEST_COUNT.labels(
            method=method,
            endpoint=route_path,
            status_code=response.status_code,
        ).inc()

        await logger.ainfo(
            "http_request",
            method=method,
            path=path,
            route=route_path,
            status_code=response.status_code,
            duration_ms=round(duration * 1000, 2),
            client=request.client.host if request.client else None,
        )

        response.headers["X-Process-Time"] = f"{duration:.4f}"
        return response

    @staticmethod
    def _route_path(request: Request) -> str | None:
        """Extract the *template* path from the matched route, if available."""
        route: Any = request.scope.get("route")
        if route and hasattr(route, "path"):
            return route.path  # type: ignore[no-any-return]
        return None
