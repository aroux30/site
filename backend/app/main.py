"""FastAPI application factory.

The ``create_app`` function assembles middleware, exception handlers, routers,
and the lifespan context manager.  Import it from your ASGI server entry-point
or tests::

    from app.main import create_app
    app = create_app()
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import sentry_sdk
import structlog
from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from slowapi.middleware import SlowAPIMiddleware

from app.core.cache.redis import close_redis, init_redis
from app.core.config.settings import get_settings
from app.core.exceptions.handlers import register_exception_handlers
from app.core.logging.config import setup_logging
from app.core.observability.metrics import APP_INFO
from app.core.observability.middleware import RequestIDMiddleware, TimingMiddleware
from app.core.security.ip_filter import IPFilterMiddleware
from app.core.security.rate_limiter import limiter
from app.core.security.security_headers import SecurityHeadersMiddleware

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger: structlog.stdlib.BoundLogger = structlog.get_logger()


# ── Lifespan ──────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup / shutdown lifecycle hook."""
    settings = get_settings()

    # Logging
    setup_logging(
        log_level=settings.LOG_LEVEL,
        json_output=settings.ENVIRONMENT != "development",
    )
    await logger.ainfo("startup", environment=settings.ENVIRONMENT)

    # Sentry
    if settings.SENTRY_DSN:
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
            environment=settings.ENVIRONMENT,
            send_default_pii=False,
        )

    # Redis
    await init_redis()
    await logger.ainfo("redis_connected")

    # Prometheus app info
    APP_INFO.info(
        {
            "version": "1.0.0",
            "environment": settings.ENVIRONMENT,
        }
    )

    yield  # ── Application is running ──

    # Shutdown
    await close_redis()
    await logger.ainfo("shutdown_complete")


# ── Factory ───────────────────────────────────────────────────────────────


def create_app() -> FastAPI:
    """Build and return the fully-configured FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="Iranian E-Commerce API",
        description="Enterprise-grade Iranian e-commerce platform API",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # ── Middleware (order matters – outermost first) ───────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "X-Process-Time"],
    )
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(TimingMiddleware)
    app.add_middleware(IPFilterMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(SlowAPIMiddleware)

    # ── Rate Limiter State ────────────────────────────────────────────
    app.state.limiter = limiter

    # ── Exception handlers ────────────────────────────────────────────
    register_exception_handlers(app)

    # ── Routers ───────────────────────────────────────────────────────
    _include_routers(app, prefix=settings.API_V1_PREFIX)

    # ── Health / metrics endpoints ────────────────────────────────────
    _register_infra_routes(app)

    return app


def _include_routers(app: FastAPI, prefix: str) -> None:
    """Import and include all module routers.

    Fails fast with a RuntimeError if any specified module router cannot
    be imported or resolved. Never silently skips broken routers in production.
    """
    module_router_specs: list[tuple[str, str, list[str]]] = [
        ("app.modules.auth.api", "/auth", ["auth"]),
        ("app.modules.users.api", "/users", ["users"]),
        ("app.modules.rbac.api", "/rbac", ["rbac"]),
        ("app.modules.catalog.api", "/catalog", ["catalog"]),
        ("app.modules.inventory.api", "/inventory", ["inventory"]),
        ("app.modules.cart.api", "/cart", ["cart"]),
        ("app.modules.checkout.api", "/checkout", ["checkout"]),
        ("app.modules.orders.api", "/orders", ["orders"]),
        ("app.modules.payments.api", "/payments", ["payments"]),
        ("app.modules.wallet.api", "/wallet", ["wallet"]),
        ("app.modules.discounts.api", "/discounts", ["discounts"]),
        ("app.modules.shipping.api", "/shipping", ["shipping"]),
        ("app.modules.reviews.api", "/reviews", ["reviews"]),
        ("app.modules.wishlist.api", "/wishlist", ["wishlist"]),
        ("app.modules.referrals.api", "/referrals", ["referrals"]),
        ("app.modules.cashback.api", "/cashback", ["cashback"]),
        ("app.modules.loyalty.api", "/loyalty", ["loyalty"]),
        ("app.modules.gamification.api", "/gamification", ["gamification"]),
        ("app.modules.notifications.api", "/notifications", ["notifications"]),
        ("app.modules.messaging.api", "/messaging", ["messaging"]),
        ("app.modules.support.api", "/support", ["support"]),
        ("app.modules.blog.api", "/blog", ["blog"]),
        ("app.modules.seo.api", "/seo", ["seo"]),
        ("app.modules.search.api", "/search", ["search"]),
        ("app.modules.analytics.api", "/analytics", ["analytics"]),
        ("app.modules.recommendations.api", "/recommendations", ["recommendations"]),
        ("app.modules.approvals.api", "/approvals", ["approvals"]),
        ("app.modules.media.api", "/media", ["media"]),
        ("app.modules.settings.api", "/settings", ["settings"]),
        ("app.modules.audit.api", "/audit", ["audit"]),
        ("app.modules.vendors.api", "/vendors", ["vendors"]),
    ]

    import importlib

    for module_path, url_prefix, tags in module_router_specs:
        try:
            # module_path values are compile-time constants defined in
            # module_router_specs above (never user input); the indirection is
            # deliberate so a broken router import fails the boot loudly.
            mod = importlib.import_module(module_path)  # nosemgrep (constant paths)
            router = getattr(mod, "router", None)
            if router is None:
                raise AttributeError(f"Module '{module_path}' has no 'router' attribute")
            app.include_router(router, prefix=f"{prefix}{url_prefix}", tags=tags)
            # Legacy root-level aliases (hidden from OpenAPI): kept for
            # backward compatibility with pre-/api/v1 consumers. Not
            # duplicates of the /api/v1/* mounts — different public paths.
            if url_prefix == "/seo":
                app.include_router(router, prefix="/seo", include_in_schema=False)
            elif url_prefix == "/vendors":
                app.include_router(router, prefix="/vendors", include_in_schema=False)
            # Also pick up admin_router if exposed
            admin_router = getattr(mod, "admin_router", None)
            if admin_router is not None:
                app.include_router(admin_router, prefix=prefix, tags=[f"admin-{tags[0]}"])
                if url_prefix == "/vendors":
                    app.include_router(admin_router, prefix="", include_in_schema=False)
        except Exception as exc:
            # FAIL FAST: Never silently hide broken routes in production
            logger.exception("router_load_failed", module=module_path, error=str(exc))
            raise RuntimeError(f"Critical router failed to load: {module_path} -> {exc}") from exc


def _register_infra_routes(app: FastAPI) -> None:
    """Register infrastructure endpoints that sit outside the API prefix."""
    import time

    import httpx
    from sqlalchemy import text

    from app.core.cache.redis import get_redis
    from app.core.database.session import engine

    settings = get_settings()

    @app.get("/healthz", include_in_schema=False)
    @app.get("/api/health/live", include_in_schema=False)
    async def healthz() -> dict[str, str]:
        """Liveness probe – returns 200 if the process is alive."""
        return {"status": "ok", "app": settings.APP_NAME}

    @app.get("/readyz", include_in_schema=False)
    @app.get("/api/health/ready", include_in_schema=False)
    async def readyz() -> JSONResponse:
        """Readiness probe – comprehensive check of PostgreSQL, Redis, Elasticsearch, and Storage."""  # noqa: E501
        checks: dict[str, str] = {}
        overall_ok = True

        # 1. Database (PostgreSQL)
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            checks["database"] = "ok"
        except Exception:
            checks["database"] = "unavailable"
            overall_ok = False

        # 2. Redis
        try:
            client = await get_redis()
            await client.ping()
            checks["redis"] = "ok"
        except Exception:
            checks["redis"] = "unavailable"
            overall_ok = False

        # 3. Elasticsearch
        try:
            es_url = f"{str(settings.ELASTICSEARCH_URL).rstrip('/')}/_cluster/health"
            async with httpx.AsyncClient(timeout=2.0) as http_c:
                res = await http_c.get(es_url)
                if res.status_code in (200, 401):  # 401 also indicates cluster is alive
                    checks["elasticsearch"] = "ok"
                else:
                    checks["elasticsearch"] = f"status_{res.status_code}"
                    overall_ok = False
        except Exception:
            checks["elasticsearch"] = "unavailable"
            overall_ok = False

        # 4. Storage (MinIO / S3)
        try:
            minio_url = f"http://{settings.MINIO_ENDPOINT}/minio/health/live"
            async with httpx.AsyncClient(timeout=2.0) as http_c:
                res = await http_c.get(minio_url)
                if res.status_code == 200:
                    checks["storage"] = "ok"
                else:
                    checks["storage"] = f"status_{res.status_code}"
                    overall_ok = False
        except Exception:
            checks["storage"] = "unavailable"
            overall_ok = False

        return JSONResponse(
            status_code=status.HTTP_200_OK if overall_ok else status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "ok" if overall_ok else "degraded", "checks": checks},
        )

    @app.get("/deep-health", include_in_schema=False)
    async def deep_health() -> JSONResponse:
        """Deep health check providing latency breakdown and dependency diagnostics."""
        diag: dict[str, Any] = {}
        all_ok = True

        # Database latency
        t0 = time.perf_counter()
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            diag["database"] = {
                "status": "healthy",
                "latency_ms": round((time.perf_counter() - t0) * 1000, 2),
            }
        except Exception as e:
            diag["database"] = {"status": "unhealthy", "error": str(e)}
            all_ok = False

        # Redis latency
        t0 = time.perf_counter()
        try:
            client = await get_redis()
            await client.ping()
            diag["redis"] = {
                "status": "healthy",
                "latency_ms": round((time.perf_counter() - t0) * 1000, 2),
            }
        except Exception as e:
            diag["redis"] = {"status": "unhealthy", "error": str(e)}
            all_ok = False

        # Elasticsearch latency & cluster health
        t0 = time.perf_counter()
        try:
            es_url = f"{str(settings.ELASTICSEARCH_URL).rstrip('/')}/_cluster/health"
            async with httpx.AsyncClient(timeout=3.0) as http_c:
                res = await http_c.get(es_url)
                cluster_info = res.json() if res.status_code == 200 else {}
                diag["elasticsearch"] = {
                    "status": "healthy" if res.status_code == 200 else "degraded",
                    "cluster_status": cluster_info.get("status", "unknown"),
                    "latency_ms": round((time.perf_counter() - t0) * 1000, 2),
                }
        except Exception as e:
            diag["elasticsearch"] = {"status": "unhealthy", "error": str(e)}
            all_ok = False

        # MinIO latency
        t0 = time.perf_counter()
        try:
            minio_url = f"http://{settings.MINIO_ENDPOINT}/minio/health/live"
            async with httpx.AsyncClient(timeout=3.0) as http_c:
                res = await http_c.get(minio_url)
                diag["storage"] = {
                    "status": "healthy" if res.status_code == 200 else "degraded",
                    "endpoint": settings.MINIO_ENDPOINT,
                    "latency_ms": round((time.perf_counter() - t0) * 1000, 2),
                }
        except Exception as e:
            diag["storage"] = {"status": "unhealthy", "error": str(e)}
            all_ok = False

        return JSONResponse(
            status_code=status.HTTP_200_OK if all_ok else status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "healthy" if all_ok else "degraded",
                "app": settings.APP_NAME,
                "environment": settings.ENVIRONMENT,
                "timestamp": datetime.now(UTC).isoformat(),
                "dependencies": diag,
            },
        )

    @app.get("/metrics", include_in_schema=False)
    async def metrics() -> Any:
        """Prometheus metrics scrape endpoint."""
        from starlette.responses import Response

        return Response(
            content=generate_latest(),
            media_type=CONTENT_TYPE_LATEST,
        )


# ── Module-level application instance (used by uvicorn) ──────────────────
app = create_app()
