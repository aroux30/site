"""Middleware for enterprise request-level observability.

- **Request & Trace ID**: injects unique ``X-Request-ID`` and ``X-Trace-ID`` headers
  into every response and binds them to structlog contextvars.
- **Timing & Latency Classification**: records request duration in Prometheus histograms,
  classifies latency (normal, warning, slow, critical), and logs structured access events.
- **Slow Request Detection**: automatically emits a ``slow_request`` diagnostic event
  when latency exceeds configured thresholds.
"""

from __future__ import annotations

import re
import time
import uuid
from typing import TYPE_CHECKING, Any

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.core.config.settings import get_settings
from app.core.observability.metrics import (
    REQUEST_COUNT,
    REQUEST_DURATION,
    REQUESTS_IN_PROGRESS,
)
from app.core.observability.tracer import get_current_span_id, get_current_trace_id


def parse_traceparent(header: str | None) -> dict[str, str] | None:
    """Parse a W3C ``traceparent`` header into trace/parent IDs.

    Returns ``None`` for missing or non-compliant values (all-zero IDs,
    wrong lengths, invalid hex, version ``ff``). Follows the W3C Trace
    Context spec so inbound context is honoured when valid and safely
    replaced when not — never crashing the request path.

    Hex is matched case-insensitively and normalised to lowercase so a
    proxy that emits uppercase hex cannot produce a trace ID that fails to
    match this service's own log correlation (see the header contract).
    """
    if not header or len(header) != 55:
        return None
    parts = header.split("-")
    if len(parts) != 4:
        return None
    version, trace_id, parent_id, flags = parts
    if version.lower() == "ff":
        return None
    if not all(
        re.fullmatch(pattern, value)
        for pattern, value in (
            ("[0-9a-fA-F]{32}", trace_id),
            ("[0-9a-fA-F]{16}", parent_id),
            ("[0-9a-fA-F]{2}", flags),
        )
    ):
        return None
    if trace_id == "0" * 32 or parent_id == "0" * 16:
        return None
    return {
        "trace_id": trace_id.lower(),
        "parent_id": parent_id.lower(),
        "flags": flags.lower(),
    }


def parse_or_generate_trace_id(request: Any) -> str:
    """Return the request's trace ID: inbound W3C ``traceparent`` or a fresh one.

    Malformed, all-zero, or adversarial ``traceparent`` values are rejected by
    :func:`parse_traceparent` and replaced with a newly minted W3C-compliant
    lowercase 32-hex trace ID. This never raises: the correlation header
    contract must hold on every response, including hostile input.
    """
    traceparent = None
    try:
        traceparent = request.headers.get("traceparent")
    except Exception:  # pragma: no cover - defensive: headers may be absent/odd
        traceparent = None

    parsed = parse_traceparent(traceparent)
    if parsed and parsed.get("trace_id"):
        return parsed["trace_id"]
    return uuid.uuid4().hex

if TYPE_CHECKING:
    from starlette.requests import Request
    from starlette.responses import Response

logger: structlog.stdlib.BoundLogger = structlog.get_logger()

# Paths that should not be logged / metered (liveness probes, metrics scrape)
_SKIP_PATHS: set[str] = {"/healthz", "/readyz", "/metrics", "/favicon.ico"}


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Ensure every request has a unique correlation ID and OpenTelemetry context."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = (
            request.headers.get("X-Correlation-ID")
            or request.headers.get("X-Request-ID")
            or str(uuid.uuid4())
        )

        # Honour an inbound W3C traceparent when present, otherwise fall back to
        # the active OTel span, otherwise mint a fresh W3C-compliant trace ID so
        # that every response carries a usable correlation identifier — the
        # header contract and log correlation both depend on it being present.
        inbound_traceparent = parse_traceparent(request.headers.get("traceparent"))
        # A client-supplied X-Trace-ID is honoured only when it is a
        # well-formed 32-hex ID: it is echoed back verbatim on every response,
        # so accepting arbitrary bytes would let a caller inject CRLF or
        # unbounded text into response headers and log correlation fields.
        inbound_x_trace = request.headers.get("X-Trace-ID")
        if inbound_x_trace and (
            not re.fullmatch("[0-9a-fA-F]{32}", inbound_x_trace)
            or inbound_x_trace == "0" * 32
        ):
            inbound_x_trace = None
        trace_id = (
            (inbound_traceparent or {}).get("trace_id")
            or (inbound_x_trace.lower() if inbound_x_trace else None)
            or get_current_trace_id()
            or uuid.uuid4().hex
        )
        span_id = (inbound_traceparent or {}).get("parent_id") or get_current_span_id() or ""

        # Bind to structlog context for the duration of the request
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            correlation_id=request_id,
            trace_id=trace_id,
            span_id=span_id,
        )

        request.state.request_id = request_id
        request.state.correlation_id = request_id
        request.state.trace_id = trace_id

        response = await call_next(request)

        # Prefer an active span's trace ID if one was started downstream.
        active_trace_id = get_current_trace_id() or trace_id
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Correlation-ID"] = request_id
        response.headers["X-Trace-ID"] = active_trace_id

        return response


class TimingMiddleware(BaseHTTPMiddleware):
    """Record request latency, classify performance tiers, and detect slow requests."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path
        method = request.method

        if path in _SKIP_PATHS:
            return await call_next(request)

        route_path = self._route_path(request) or path
        settings = get_settings()

        REQUESTS_IN_PROGRESS.labels(method=method, endpoint=route_path).inc()
        start = time.perf_counter()

        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as exc:
            REQUEST_COUNT.labels(method=method, endpoint=route_path, status_code=500).inc()
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            await logger.aerror(
                "http_request_exception",
                method=method,
                path=path,
                route=route_path,
                status_code=500,
                duration_ms=duration_ms,
                error_type=type(exc).__name__,
                error_message=str(exc),
            )
            raise
        finally:
            duration = time.perf_counter() - start
            REQUESTS_IN_PROGRESS.labels(method=method, endpoint=route_path).dec()

        duration_ms = round(duration * 1000, 2)
        REQUEST_DURATION.labels(method=method, endpoint=route_path).observe(duration)
        REQUEST_COUNT.labels(
            method=method,
            endpoint=route_path,
            status_code=status_code,
        ).inc()

        # Performance latency classification
        if duration_ms >= settings.API_CRITICAL_REQUEST_THRESHOLD_MS:
            latency_tier = "critical"
            log_fn = logger.aerror
        elif duration_ms >= settings.API_SLOW_REQUEST_THRESHOLD_MS:
            latency_tier = "slow"
            log_fn = logger.awarning
        else:
            latency_tier = "normal"
            log_fn = logger.ainfo

        # Emit slow request diagnostic event if exceeded threshold
        if duration_ms >= settings.API_SLOW_REQUEST_THRESHOLD_MS:
            await logger.awarning(
                "slow_request",
                method=method,
                path=path,
                route=route_path,
                duration_ms=duration_ms,
                threshold_ms=settings.API_SLOW_REQUEST_THRESHOLD_MS,
                status_code=status_code,
            )

        await log_fn(
            "http_request",
            method=method,
            path=path,
            route=route_path,
            status_code=status_code,
            duration_ms=duration_ms,
            latency_tier=latency_tier,
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
