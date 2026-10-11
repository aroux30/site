"""OpenTelemetry distributed tracing initialization and helpers.

Provides official OTel TracerProvider setup, OTLP exporter, and automatic
instrumentation for FastAPI, SQLAlchemy, Redis, and HTTPX.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.celery import CeleryInstrumentor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased
from opentelemetry.trace import Tracer

from app.core.config.settings import get_settings

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger(__name__)

_tracer: Tracer | None = None
_instrumented: bool = False


def _otlp_http_session(endpoint: str) -> Any:
    """A requests session for the OTLP exporter.

    A collector on loopback must not be routed through an ambient proxy:
    with HTTP_PROXY set (and NO_PROXY absent) the exporter posts to the
    proxy instead of the collector and every batch dies as a ReadTimeout
    on the proxy port — measured: delivered=False in 5.0s with the request
    going to 127.0.0.1:10809, while the same export with ``trust_env=False``
    reached the collector in 0.02s. The same hazard exists on Windows via
    the registry proxy. An external collector (SaaS, another host) keeps
    the default session so a corporate egress proxy still applies.
    """
    import requests

    host = urlparse(endpoint).hostname or ""
    is_loopback = host in {"localhost", "127.0.0.1", "::1"} or host.endswith(".localhost")
    session = requests.Session()
    if is_loopback:
        session.trust_env = False
    return session


def setup_opentelemetry(app: FastAPI | None = None) -> TracerProvider:
    """Initialize OpenTelemetry SDK, processors, exporters, and automatic instrumentors."""
    global _tracer, _instrumented
    settings = get_settings()

    if not settings.OTEL_ENABLED:
        provider = TracerProvider()
        trace.set_tracer_provider(provider)
        _tracer = trace.get_tracer("iranian-ecommerce-backend")
        return provider

    resource = Resource.create(
        {
            "service.name": settings.OTEL_SERVICE_NAME,
            "service.version": "1.0.0",
            "deployment.environment": settings.ENVIRONMENT,
        }
    )

    sampler = ParentBased(TraceIdRatioBased(settings.OTEL_TRACES_SAMPLER_RATIO))
    provider = TracerProvider(resource=resource, sampler=sampler)

    # Configure OTLP HTTP span exporter
    try:
        otlp_endpoint = f"{settings.OTEL_EXPORTER_OTLP_ENDPOINT.rstrip('/')}/v1/traces"
        otlp_exporter = OTLPSpanExporter(
            endpoint=otlp_endpoint,
            timeout=5,
            session=_otlp_http_session(otlp_endpoint),
        )
        provider.add_span_processor(BatchSpanProcessor(otlp_exporter))

        # The collector is optional infrastructure: when it is unreachable the
        # exporter retries every batch and each failure would otherwise be
        # written into the unified debug.log, drowning real signal. Spans are
        # still produced and exported whenever the collector is present.
        for noisy in (
            "opentelemetry.exporter.otlp.proto.http.trace_exporter",
            "opentelemetry.sdk.trace.export",
        ):
            logging.getLogger(noisy).setLevel(logging.CRITICAL)
    except Exception as exc:
        logger.warning("Failed to initialize OTLP Span Exporter: %s", exc)

    if settings.OBSERVABILITY_DEBUG:
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

    trace.set_tracer_provider(provider)
    _tracer = trace.get_tracer("iranian-ecommerce-backend")

    # Auto-instrument external libraries only once
    if not _instrumented:
        try:
            HTTPXClientInstrumentor().instrument()
        except Exception as exc:
            logger.warning("HTTPX instrumentation warning: %s", exc)

        try:
            RedisInstrumentor().instrument()
        except Exception as exc:
            logger.warning("Redis instrumentation warning: %s", exc)

        try:
            CeleryInstrumentor().instrument()  # type: ignore[no-untyped-call]  # otel-celery pkg is untyped
        except Exception as exc:
            logger.warning("Celery instrumentation warning: %s", exc)

        _instrumented = True

    # Instrument FastAPI app if provided
    if app is not None:
        try:
            FastAPIInstrumentor().instrument_app(
                app,
                tracer_provider=provider,
                excluded_urls="healthz,readyz,metrics",
            )
        except Exception as exc:
            logger.warning("FastAPI instrumentation warning: %s", exc)

    return provider


def instrument_sqlalchemy(engine: Any) -> None:
    """Instrument SQLAlchemy async engine with OpenTelemetry."""
    try:
        sync_engine = getattr(engine, "sync_engine", engine)
        SQLAlchemyInstrumentor().instrument(
            engine=sync_engine,
            enable_commenter=True,
        )
    except Exception as exc:
        logger.warning("SQLAlchemy instrumentation warning: %s", exc)


def get_tracer() -> Tracer:
    """Get the application OpenTelemetry tracer instance."""
    global _tracer
    if _tracer is None:
        _tracer = trace.get_tracer("iranian-ecommerce-backend")
    return _tracer


def get_current_trace_id() -> str | None:
    """Retrieve the current active Trace ID in hex format."""
    span = trace.get_current_span()
    if span and span.get_span_context().is_valid:
        return f"{span.get_span_context().trace_id:032x}"
    return None


def get_current_span_id() -> str | None:
    """Retrieve the current active Span ID in hex format."""
    span = trace.get_current_span()
    if span and span.get_span_context().is_valid:
        return f"{span.get_span_context().span_id:016x}"
    return None
