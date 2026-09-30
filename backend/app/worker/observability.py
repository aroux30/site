"""Celery Trace Context Propagation and Observability Hooks.

Ensures:
1. Active OpenTelemetry trace context (W3C traceparent) and structlog correlation IDs
   (request_id) are injected into message headers at task publication.
2. Worker extracts traceparent and correlation IDs upon execution, attaching them to
   the local execution context so async tasks remain connected to the originating request.
3. Queue latency, task execution duration, and failures are monitored via Prometheus.
"""

from __future__ import annotations

import contextlib
import time
from typing import Any

import structlog
from celery.signals import (
    before_task_publish,
    task_failure,
    task_postrun,
    task_prerun,
    task_success,
)
from opentelemetry import context
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

from app.core.observability.metrics import (
    CELERY_QUEUE_LATENCY,
    CELERY_TASK_DURATION,
    CELERY_TASK_FAILURES,
    CELERY_TASK_SUCCESS,
)
from app.core.security.actor_context import clear_actor

logger: structlog.stdlib.BoundLogger = structlog.get_logger("worker.celery")
_propagator = TraceContextTextMapPropagator()


@before_task_publish.connect
def on_before_task_publish(
    sender: str | None = None,
    headers: dict[str, Any] | None = None,
    body: Any = None,
    exchange: str | None = None,
    routing_key: str | None = None,
    **kwargs: Any,
) -> None:
    """Inject OpenTelemetry trace context, request_id, and enqueue timestamp into headers."""
    if headers is None:
        return

    # 1. Inject W3C traceparent and tracestate into message headers
    _propagator.inject(headers)

    # 2. Inject structlog request_id / correlation_id
    ctx = structlog.contextvars.get_contextvars()
    req_id = ctx.get("request_id") or ctx.get("correlation_id")
    if req_id:
        headers["request_id"] = str(req_id)
        headers["correlation_id"] = str(req_id)

    # 3. Enqueue timestamp for queue waiting latency tracking
    headers["enqueued_at"] = time.time()
    headers["routing_key"] = routing_key or "default"


@task_prerun.connect
def on_task_prerun(
    sender: Any = None,
    task_id: str | None = None,
    task: Any = None,
    args: Any = None,
    kwargs: Any = None,
    **extra: Any,
) -> None:
    """Restore trace context, bind structlog variables, and calculate queue latency."""
    task_obj = task or sender
    headers = getattr(getattr(task_obj, "request", None), "headers", None) or {}

    # 1. Extract and attach OpenTelemetry context
    extracted_ctx = _propagator.extract(headers)
    token = context.attach(extracted_ctx)
    if hasattr(task_obj, "request"):
        task_obj.request._otel_context_token = token

    # 2. Extract correlation ID and bind to worker's structlog context
    req_id = headers.get("request_id") or headers.get("correlation_id")
    task_name = getattr(task_obj, "name", "unknown_task")

    # A worker process runs many tasks in one context; any actor bound by a
    # previous task (or by a publish-side call) must not leak into this one.
    # Tasks attribute their changes to `celery` unless they bind explicitly
    # via actor_scope(..., source="seed" | "service").
    clear_actor()

    structlog.contextvars.clear_contextvars()
    bind_kwargs: dict[str, Any] = {
        "task_id": str(task_id),
        "task_name": task_name,
    }
    if req_id:
        bind_kwargs["request_id"] = str(req_id)
        bind_kwargs["correlation_id"] = str(req_id)

    structlog.contextvars.bind_contextvars(**bind_kwargs)

    # 3. Calculate Queue Latency
    enqueued_at = headers.get("enqueued_at")
    if enqueued_at and isinstance(enqueued_at, (int, float)):
        queue_latency = max(0.0, time.time() - float(enqueued_at))
        queue_name = headers.get("routing_key") or "default"
        CELERY_QUEUE_LATENCY.labels(queue=queue_name, task=task_name).observe(queue_latency)

    # 4. Start execution timer
    if hasattr(task_obj, "request"):
        task_obj.request._exec_start_time = time.perf_counter()


@task_postrun.connect
def on_task_postrun(
    sender: Any = None,
    task_id: str | None = None,
    task: Any = None,
    args: Any = None,
    kwargs: Any = None,
    retval: Any = None,
    state: str | None = None,
    **extra: Any,
) -> None:
    """Record task execution duration and detach OpenTelemetry context."""
    task_obj = task or sender
    req = getattr(task_obj, "request", None)
    task_name = getattr(task_obj, "name", "unknown_task")

    if req is not None:
        start_time = getattr(req, "_exec_start_time", None)
        if start_time is not None:
            duration = time.perf_counter() - start_time
            CELERY_TASK_DURATION.labels(task=task_name, state=str(state or "SUCCESS")).observe(
                duration
            )

        token = getattr(req, "_otel_context_token", None)
        if token is not None:
            with contextlib.suppress(Exception):
                context.detach(token)


@task_failure.connect
def on_task_failure(
    sender: Any = None,
    task_id: str | None = None,
    exception: Exception | None = None,
    args: Any = None,
    kwargs: Any = None,
    traceback: Any = None,
    einfo: Any = None,
    **extra: Any,
) -> None:
    """Record task failure metrics and structured error log."""
    task_name = getattr(sender, "name", "unknown_task")
    exc_type = type(exception).__name__ if exception is not None else "UnknownException"

    CELERY_TASK_FAILURES.labels(task=task_name, exception=exc_type).inc()
    logger.error(
        "celery_task_failed",
        task=task_name,
        task_id=str(task_id),
        exception_type=exc_type,
        error=str(exception),
    )


@task_success.connect
def on_task_success(
    sender: Any = None,
    result: Any = None,
    **extra: Any,
) -> None:
    """Record task success metrics."""
    task_name = getattr(sender, "name", "unknown_task")
    CELERY_TASK_SUCCESS.labels(task=task_name).inc()
