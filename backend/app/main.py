"""FastAPI application factory.

The ``create_app`` function assembles middleware, exception handlers, routers,
and the lifespan context manager.  Import it from your ASGI server entry-point
or tests::

    from app.main import create_app
    app = create_app()
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from typing import Any

import sentry_sdk
import structlog
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.core.cache.redis import close_redis, init_redis
from app.core.config.settings import get_settings
from app.core.exceptions.handlers import register_exception_handlers
from app.core.logging.config import setup_logging
from app.core.observability.metrics import APP_INFO
from app.core.observability.middleware import RequestIDMiddleware, TimingMiddleware

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
    APP_INFO.info({
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT,
    })

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
        docs_url="/api/docs" if settings.DEBUG else None,
        redoc_url="/api/redoc" if settings.DEBUG else None,
        openapi_url="/api/openapi.json" if settings.DEBUG else None,
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

    # ── Exception handlers ────────────────────────────────────────────
    register_exception_handlers(app)

    # ── Routers ───────────────────────────────────────────────────────
    _include_routers(app, prefix=settings.API_V1_PREFIX)

    # ── Health / metrics endpoints ────────────────────────────────────
    _register_infra_routes(app)

    return app


def _include_routers(app: FastAPI, prefix: str) -> None:
    """Import and include all module routers.

    Each module exposes a ``router`` in its ``api`` package.  Routers that
    don't exist yet are silently skipped so the application can boot even
    while modules are still being developed.
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
        ("app.modules.content.api", "/content", ["content"]),
        ("app.modules.blog.api", "/blog", ["blog"]),
        ("app.modules.seo.api", "/seo", ["seo"]),
        ("app.modules.search.api", "/search", ["search"]),
        ("app.modules.analytics.api", "/analytics", ["analytics"]),
        ("app.modules.recommendations.api", "/recommendations", ["recommendations"]),
        ("app.modules.approvals.api", "/approvals", ["approvals"]),
        ("app.modules.media.api", "/media", ["media"]),
        ("app.modules.settings.api", "/settings", ["settings"]),
        ("app.modules.audit.api", "/audit", ["audit"]),
        ("app.modules.integrations.api", "/integrations", ["integrations"]),
        ("app.modules.automation.api", "/automation", ["automation"]),
    ]

    import importlib

    for module_path, url_prefix, tags in module_router_specs:
        try:
            mod = importlib.import_module(module_path)
            router = getattr(mod, "router", None)
            if router is not None:
                app.include_router(router, prefix=f"{prefix}{url_prefix}", tags=tags)
            # Also pick up admin_router if exposed (e.g. search admin endpoints)
            admin_router = getattr(mod, "admin_router", None)
            if admin_router is not None:
                app.include_router(admin_router, prefix=prefix, tags=[f"admin-{tags[0]}"])
        except (ImportError, AttributeError):
            # Module not yet implemented – skip silently
            pass


def _register_infra_routes(app: FastAPI) -> None:
    """Register infrastructure endpoints that sit outside the API prefix."""

    @app.get("/healthz", include_in_schema=False)
    async def healthz() -> dict[str, str]:
        """Liveness probe – returns 200 if the process is alive."""
        return {"status": "ok"}

    @app.get("/readyz", include_in_schema=False)
    async def readyz() -> JSONResponse:
        """Readiness probe – checks critical dependencies."""
        from app.core.cache.redis import get_redis

        checks: dict[str, str] = {}
        overall_ok = True

        # Redis
        try:
            client = await get_redis()
            await client.ping()
            checks["redis"] = "ok"
        except Exception:
            checks["redis"] = "unavailable"
            overall_ok = False

        # Database
        try:
            from app.core.database.session import engine

            async with engine.connect() as conn:
                await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
            checks["database"] = "ok"
        except Exception:
            checks["database"] = "unavailable"
            overall_ok = False

        return JSONResponse(
            status_code=status.HTTP_200_OK if overall_ok else status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "ok" if overall_ok else "degraded", "checks": checks},
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
