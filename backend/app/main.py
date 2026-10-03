"""FastAPI application factory.

The ``create_app`` function assembles middleware, exception handlers, routers,
and the lifespan context manager.  Import it from your ASGI server entry-point
or tests::

    from app.main import create_app
    app = create_app()
"""

from __future__ import annotations

import asyncio
import time
import secrets
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import sentry_sdk
import structlog
from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from slowapi.middleware import SlowAPIMiddleware

from app.core.exceptions.recovery_middleware import RecoveryModeMiddleware
from app.core.middleware.maintenance_middleware import MaintenanceMiddleware

from app.core.cache.redis import close_redis, init_redis
from app.core.config.settings import get_settings
from app.core.exceptions.handlers import register_exception_handlers
from app.core.http_cache import ETagMiddleware, PageCacheMiddleware
from app.core.logging import setup_logging, shutdown_logging
from app.core.observability.metrics import APP_INFO
from app.core.observability.middleware import RequestIDMiddleware, TimingMiddleware
from app.core.observability.tracer import setup_opentelemetry
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

    # Logging & Tracing
    setup_logging(
        log_level=settings.LOG_LEVEL,
        json_output=settings.ENVIRONMENT != "development",
        service_name=settings.OTEL_SERVICE_NAME,
        environment=settings.ENVIRONMENT,
    )
    setup_opentelemetry(app)
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

    # RBAC permission seed (bootstrap): upserts the permission catalog and
    # grants it to the system "admin" role. Idempotent and insert-only, so a
    # failure must never block startup — log and continue.
    try:
        from app.core.database.session import async_session_factory
        from app.modules.rbac.application.permission_seed import seed_permissions

        async with async_session_factory() as db:
            stats = await seed_permissions(db)
            await db.commit()
        await logger.ainfo(
            "permission_seed_done",
            created=len(stats.permissions_created),
            skipped=len(stats.permissions_skipped),
            granted=len(stats.permissions_granted_to_admin),
            admin_role_created=stats.admin_role_created,
        )
    except Exception:
        await logger.aexception("permission_seed_failed")

    # Warehouse catalogue bootstrap: pre-multi-warehouse installs hold stock
    # under DEFAULT_WAREHOUSE_ID with no catalogue row, which would make the
    # admin warehouse list look empty while the ledger is not. Register that
    # sentinel once; insert-only and never steals an existing default, so a
    # failure must never block startup — log and continue.
    try:
        from app.core.database.session import async_session_factory
        from app.modules.inventory.application import warehouse_service

        async with async_session_factory() as db:
            await warehouse_service.ensure_default_warehouse(db)
            await db.commit()
    except Exception:
        await logger.aexception("warehouse_bootstrap_failed")

    # Approval-policy bootstrap: seed the default money-flow chains (refund,
    # wallet withdrawal, vendor settlement) once. Idempotent by
    # (resource, min_amount) and insert-only, so a failure must never block
    # startup — log and continue.
    try:
        from app.core.database.session import async_session_factory
        from app.modules.approvals.application.policy_service import (
            seed_default_policies,
        )

        async with async_session_factory() as db:
            created = await seed_default_policies(db)
            await db.commit()
        if created:
            await logger.ainfo("approval_policy_seed_done", created=created)
    except Exception:
        await logger.aexception("approval_policy_seed_failed")

    # Plugin toggles: apply the persisted disable list before any request
    # runs. Missing row = nothing disabled; a read failure is logged and
    # swallowed so a settings-table problem never blocks a boot.
    try:
        from app.core.database.session import async_session_factory
        from app.shared.plugins.registry import load_disabled_plugins

        async with async_session_factory() as db:
            disabled = await load_disabled_plugins(db)
        if disabled:
            await logger.ainfo("plugin_toggles_loaded", disabled=disabled)
    except Exception:
        await logger.aexception("plugin_toggle_load_failed")

    # Prometheus app info
    APP_INFO.info(
        {
            "version": "1.0.0",
            "environment": settings.ENVIRONMENT,
        }
    )

    # Stale reservation cleanup (QA B27): releases PENDING holds of
    # abandoned carts and CONFIRMED holds of unpaid orders once their TTL
    # passes — otherwise abandoned checkouts lock stock forever.  Runs
    # once at startup, then every RESERVATION_CLEANUP_INTERVAL_SECONDS.
    cleanup_task = asyncio.create_task(_reservation_cleanup_loop())
    await logger.ainfo("reservation_cleanup_started")

    yield  # ── Application is running ──

    # Shutdown
    cleanup_task.cancel()
    await close_redis()
    await logger.ainfo("shutdown_complete")
    shutdown_logging()


async def _reservation_cleanup_loop(interval_seconds: int = 300) -> None:
    """Periodically release expired stock reservations (QA B27)."""
    from app.core.database.session import async_session_factory
    from app.modules.inventory.application.reservation_cleanup import (
        release_stale_reservations,
    )

    while True:
        try:
            async with async_session_factory() as db:
                count = await release_stale_reservations(db)
                if count:
                    await db.commit()
                    await logger.ainfo(
                        "reservation_cleanup_released", count=count
                    )
        except asyncio.CancelledError:
            raise
        except Exception:
            await logger.aexception("reservation_cleanup_failed")
        await asyncio.sleep(interval_seconds)


# ── Factory ───────────────────────────────────────────────────────────────


def create_app() -> FastAPI:
    """Build and return the fully-configured FastAPI application."""
    settings = get_settings()

    # Interactive API documentation is disabled in production. The schema
    # enumerates every endpoint, admin route, and request model — free
    # reconnaissance for an attacker. Operators who genuinely need it in
    # production must opt in explicitly with ENABLE_API_DOCS=true (behind an
    # internal network or an nginx allowlist), never by default.
    _docs_enabled = settings.ENVIRONMENT != "production" or settings.ENABLE_API_DOCS
    app = FastAPI(
        title="Iranian E-Commerce API",
        description="Enterprise-grade Iranian e-commerce platform API",
        version="1.0.0",
        docs_url="/docs" if _docs_enabled else None,
        redoc_url="/redoc" if _docs_enabled else None,
        openapi_url="/openapi.json" if _docs_enabled else None,
        lifespan=lifespan,
    )

    # ── Middleware (order matters – outermost first) ───────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "X-Trace-ID", "X-Correlation-ID", "X-Process-Time"],
    )
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(TimingMiddleware)
    app.add_middleware(IPFilterMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    # HTTP cache layer (app/core/http_cache.py): ETag/304 negotiation for
    # anonymous API GETs, plus the opt-in Redis page cache (off by default
    # via PAGE_CACHE_ENABLED). Added between the security headers and the
    # rate limiter, so:
    #   - responses pass SecurityHeadersMiddleware first — the no-store it
    #     stamps on sensitive prefixes is visible here and always honoured;
    #   - a 304 short-circuit still carries those security headers (they are
    #     applied one layer down and copied onto the 304);
    #   - rate limiting stays the outermost gate.
    app.add_middleware(PageCacheMiddleware)
    app.add_middleware(ETagMiddleware)
    app.add_middleware(SlowAPIMiddleware)

    # Registered last so it becomes the OUTERMOST layer: recovery mode has to
    # short-circuit before routing, because a paused site's own handlers may
    # be what is broken. Health checks and the resume endpoint are exempt
    # inside the middleware, so there is always a way back.
    app.add_middleware(RecoveryModeMiddleware)

    # Maintenance mode, registered *inside* recovery mode and therefore outside
    # everything else. Outside is what matters: it has to short-circuit before
    # routing, because a route whose own code is mid-migration is exactly the
    # route that would fail while the store is supposed to be down. Recovery mode
    # stays outermost because a paused site must beat a maintenance flag — a store
    # being recovered from is not in maintenance, and the flag would otherwise
    # serve a 503 forever with nobody able to turn it off.
    app.add_middleware(MaintenanceMiddleware)

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
        ("app.modules.accounting.api", "/accounting", ["accounting"]),
        ("app.modules.dms.api", "/documents", ["documents"]),
        ("app.modules.crm.api", "/crm", ["crm"]),
        ("app.modules.calendar.api", "/calendar", ["calendar"]),
        ("app.modules.bi.api", "/bi", ["bi"]),
        ("app.modules.auth.api", "/auth", ["auth"]),
        ("app.modules.users.api", "/users", ["users"]),
        ("app.modules.rbac.api", "/rbac", ["rbac"]),
        ("app.modules.catalog.api", "/catalog", ["catalog"]),
        ("app.modules.inventory.api", "/inventory", ["inventory"]),
        ("app.modules.cart.api", "/cart", ["cart"]),
        ("app.modules.checkout.api", "/checkout", ["checkout"]),
        ("app.modules.orders.api", "/orders", ["orders"]),
        ("app.modules.subscriptions.api", "/subscriptions", ["subscriptions"]),
        ("app.modules.payments.api", "/payments", ["payments"]),
        ("app.modules.wallet.api", "/wallet", ["wallet"]),
        ("app.modules.discounts.api", "/discounts", ["discounts"]),
        ("app.modules.pricing.api", "/pricing", ["pricing"]),
        ("app.modules.shipping.api", "/shipping", ["shipping"]),
        ("app.modules.reviews.api", "/reviews", ["reviews"]),
        ("app.modules.wishlist.api", "/wishlist", ["wishlist"]),
        ("app.modules.referrals.api", "/referrals", ["referrals"]),
        ("app.modules.cashback.api", "/cashback", ["cashback"]),
        ("app.modules.loyalty.api", "/loyalty", ["loyalty"]),
        ("app.modules.gamification.api", "/gamification", ["gamification"]),
        ("app.modules.notifications.api", "/notifications", ["notifications"]),
        ("app.modules.messaging.api", "/messaging", ["messaging"]),
        ("app.modules.newsletter.api", "/newsletter", ["newsletter"]),
        ("app.modules.support.api", "/support", ["support"]),
        ("app.modules.blog.api", "/blog", ["blog"]),
        ("app.modules.seo.api", "/seo", ["seo"]),
        ("app.modules.search.api", "/search", ["search"]),
        ("app.modules.analytics.api", "/analytics", ["analytics"]),
        ("app.modules.recommendations.api", "/recommendations", ["recommendations"]),
        ("app.modules.approvals.api", "/approvals", ["approvals"]),
        ("app.modules.media.api", "/media", ["media"]),
        ("app.modules.settings.api", "/settings", ["settings"]),
        ("app.modules.automation.api", "/automation", ["automation"]),
        ("app.modules.integrations.api", "/integrations", ["integrations"]),
        ("app.modules.content.api", "/content", ["content"]),
        ("app.modules.audit.api", "/audit", ["audit"]),
        ("app.modules.vendors.api", "/vendors", ["vendors"]),
        ("app.modules.dataexchange.api", "/dataexchange", ["dataexchange"]),
        ("app.modules.invoicing.api", "/invoicing", ["invoicing"]),
        ("app.modules.reporting.api", "/reporting", ["reporting"]),
        ("app.modules.procurement.api", "/procurement", ["procurement"]),
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
                # Admin-only modules (e.g. procurement) expose no
                # customer-facing ``router`` — only ``admin_router``.
                if getattr(mod, "admin_router", None) is None:
                    raise AttributeError(
                        f"Module '{module_path}' has neither 'router' nor 'admin_router'"
                    )
            else:
                # list[str] is invariant in list[str | Enum]; values are compile-time
                # constants above, so the cast is exact.
                app.include_router(
                    router, prefix=f"{prefix}{url_prefix}", tags=cast("list[Any]", tags)
                )
            # Legacy root-level aliases (hidden from OpenAPI): kept for
            # backward compatibility with pre-/api/v1 consumers. Not
            # duplicates of the /api/v1/* mounts — different public paths.
            if router is not None:
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

    # ── Mount Native Captcha & System Preflight Router ─────────────────
    from app.core.security.captcha_routes import router as captcha_router

    app.include_router(captcha_router, prefix=prefix)


def _register_infra_routes(app: FastAPI) -> None:
    """Register infrastructure endpoints that sit outside the API prefix."""
    import time

    import httpx
    from sqlalchemy import text

    from app.core.cache.redis import get_redis
    from app.core.database.session import engine
    from app.modules.media.application.storage_paths import resolve_served_file

    settings = get_settings()

    # (monotonic timestamp, payload) for the liveness probe's dependency hint.
    # Module-scoped rather than per-request so a burst of scrapes does not open
    # a connection per hit.
    _healthz_cache: dict[str, tuple[float, dict[str, object]]] = {}

    @app.get("/healthz", include_in_schema=False)
    @app.get("/api/health/live", include_in_schema=False)
    async def healthz() -> dict[str, object]:
        """Liveness probe – is the process itself alive?

        Deliberately cheap: it touches no dependency. A liveness probe that
        queries Postgres reports the process dead whenever the *database* is
        down, and the orchestrator then restarts every worker — turning one
        outage into a crash loop.

        The trade-off used to be that a container with the database down
        reported plain "ok", which reads as healthy. So dependency status is
        reported *in the body* while the status code stays 200: Docker's
        `curl -fsS` keeps treating the process as alive (correct for liveness),
        and a human or a metrics scraper reading the body can see `degraded`.

        Readiness — "should traffic be routed here" — is `/api/health/ready`,
        which does probe the dependencies and does gate traffic.
        """
        # A short TTL so a monitoring scraper polling every second does not
        # turn this into a load generator, while a human still sees a change
        # within a few seconds of it happening.
        cached = _healthz_cache.get("payload")
        now = time.monotonic()
        if cached and now - cached[0] < 10.0:
            return cached[1]

        payload: dict[str, object] = {"status": "ok", "app": settings.APP_NAME}

        async def _db_alive() -> bool:
            try:
                async with asyncio.timeout(1.0):
                    async with engine.connect() as conn:
                        await conn.execute(text("SELECT 1"))
                return True
            except Exception:
                return False

        # Never raise out of a health endpoint: an exception here would be
        # caught by the generic handler, which pauses the site.
        try:
            if not await _db_alive():
                payload["status"] = "degraded"
                payload["checks"] = {"database": "unavailable"}
        except Exception:  # noqa: BLE001
            payload["status"] = "degraded"

        _healthz_cache["payload"] = (now, payload)
        return payload

    # Uploaded media is stored under UPLOAD_DIR and referenced by a relative
    # "/uploads/media/<name>" URL. Nothing served that path: the storefront
    # rewrite in next.config.ts proxies /uploads to this origin, and every
    # asset picked from the library rendered a 404 until this route existed.
    #
    # Served read-only, by exact name, through a traversal-guarded resolver
    # (see media.application.storage_paths.resolve_served_file). The directory
    # is not listable and no path outside the uploads root is reachable.
    uploads_root = Path(getattr(settings, "UPLOAD_DIR", "media"))

    @app.get("/uploads/{file_path:path}", include_in_schema=False)
    async def serve_upload(file_path: str) -> FileResponse:
        candidate = resolve_served_file(uploads_root, file_path)
        if candidate is None:
            raise HTTPException(status_code=404, detail="Not found")
        return FileResponse(
            candidate,
            headers={"Cache-Control": "public, max-age=31536000, immutable"},
        )

    # This endpoint is unauthenticated by design (the browser cannot hold a
    # service token) and writes straight into the synchronous debug.log audit
    # stream. Without its own ceiling any anonymous caller could spend the
    # shared global budget and inject arbitrary text into that stream, so it
    # gets a much tighter per-IP limit than the 200/minute global default.
    # NOTE the decorator order: slowapi's @limiter.limit must sit BELOW
    # @app.post (closest to the function) — inverted, it silently never runs.
    # The handler must also accept `response: Response` for slowapi to inject
    # its rate-limit headers.
    @app.post("/api/v1/observability/client-logs", include_in_schema=False)
    @limiter.limit("30/minute")
    async def ingest_client_logs(request: Request, response: Response) -> dict[str, str]:
        """Ingest frontend client-side logs directly into the unified debug.log."""
        def _clip(value: Any, limit: int) -> str:
            """Trim caller-supplied text so an anonymous client cannot inflate
            the audit file with arbitrarily large records."""
            text = "" if value is None else str(value)
            return text[:limit]

        try:
            payload = await request.json()
            level = _clip(payload.get("level", "info"), 16).lower()
            event = _clip(payload.get("event", "frontend_client_log"), 200)
            client_ip = request.client.host if request.client else "unknown"

            log_fn = logger.ainfo
            if level == "error":
                log_fn = logger.aerror
            elif level in ("warn", "warning"):
                log_fn = logger.awarning
            elif level == "debug":
                log_fn = logger.adebug

            await log_fn(
                event,
                client=client_ip,
                route=_clip(payload.get("route", ""), 300),
                duration_ms=payload.get("durationMs"),
                status_code=payload.get("status"),
                error=_clip(payload.get("error"), 2000),
                error_id=_clip(payload.get("errorId"), 100),
            )
            return {"status": "ingested"}
        except Exception:
            return {"status": "ignored"}

    @app.get("/readyz", include_in_schema=False)
    @app.get("/api/health/ready", include_in_schema=False)
    async def readyz() -> JSONResponse:
        """Readiness probe – concurrent check of PostgreSQL, Redis, Elasticsearch, and Storage (PERF-001)."""  # noqa: E501
        checks: dict[str, str] = {}
        overall_ok = True

        async def _check_db() -> tuple[str, str]:
            try:
                async with asyncio.timeout(1.5):
                    async with engine.connect() as conn:
                        await conn.execute(text("SELECT 1"))
                return "database", "ok"
            except Exception:
                return "database", "unavailable"

        async def _check_redis() -> tuple[str, str]:
            try:
                async with asyncio.timeout(1.5):
                    client = await get_redis()
                    await client.ping()
                return "redis", "ok"
            except Exception:
                return "redis", "unavailable"

        async def _check_es() -> tuple[str, str]:
            try:
                es_url = f"{str(settings.ELASTICSEARCH_URL).rstrip('/')}/_cluster/health"
                async with httpx.AsyncClient(timeout=1.5) as http_c:
                    res = await http_c.get(es_url)
                    if res.status_code in (200, 401):  # 401 also indicates cluster is alive
                        return "elasticsearch", "ok"
                    return "elasticsearch", f"status_{res.status_code}"
            except Exception:
                return "elasticsearch", "unavailable"

        async def _check_storage() -> tuple[str, str]:
            """Probe the store media is actually written to.

            This used to probe MinIO. Media is persisted to ``UPLOAD_DIR`` on
            a mounted volume (see ``media_service``); MinIO is not in the write
            path, so probing it reported "unavailable" for an outage that
            breaks nothing, and "ok" for a full or read-only uploads volume
            that breaks every upload. Check the volume the app really uses.
            """
            try:
                # Write-then-read, not exists(): a read-only or full volume
                # still passes an existence check while every upload fails.
                probe = uploads_root / ".readyz-probe"
                probe.parent.mkdir(parents=True, exist_ok=True)
                await asyncio.to_thread(probe.write_text, "ok")
                await asyncio.to_thread(probe.unlink)
                return "storage", "ok"
            except Exception:
                return "storage", "unavailable"

        results = await asyncio.gather(
            _check_db(), _check_redis(), _check_es(), _check_storage()
        )
        for key, val in results:
            checks[key] = val
            if val != "ok":
                overall_ok = False

        return JSONResponse(
            status_code=status.HTTP_200_OK if overall_ok else status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "ok" if overall_ok else "degraded", "checks": checks},
        )

    @app.get("/deep-health", include_in_schema=False)
    async def deep_health() -> JSONResponse:
        """Deep health check providing concurrent latency breakdown under 2s (PERF-001)."""
        diag: dict[str, Any] = {}
        all_ok = True

        async def _diag_db() -> tuple[str, dict[str, Any], bool]:
            t0 = time.perf_counter()
            try:
                async with asyncio.timeout(1.5):
                    async with engine.connect() as conn:
                        await conn.execute(text("SELECT 1"))
                return "database", {
                    "status": "healthy",
                    "latency_ms": round((time.perf_counter() - t0) * 1000, 2),
                }, True
            except Exception as e:
                return "database", {"status": "unhealthy", "error": str(e)}, False

        async def _diag_redis() -> tuple[str, dict[str, Any], bool]:
            t0 = time.perf_counter()
            try:
                async with asyncio.timeout(1.5):
                    client = await get_redis()
                    await client.ping()
                return "redis", {
                    "status": "healthy",
                    "latency_ms": round((time.perf_counter() - t0) * 1000, 2),
                }, True
            except Exception as e:
                return "redis", {"status": "unhealthy", "error": str(e)}, False

        async def _diag_es() -> tuple[str, dict[str, Any], bool]:
            t0 = time.perf_counter()
            try:
                es_url = f"{str(settings.ELASTICSEARCH_URL).rstrip('/')}/_cluster/health"
                async with httpx.AsyncClient(timeout=1.5) as http_c:
                    res = await http_c.get(es_url)
                    cluster_info = res.json() if res.status_code == 200 else {}
                    return "elasticsearch", {
                        "status": "healthy" if res.status_code == 200 else "degraded",
                        "cluster_status": cluster_info.get("status", "unknown"),
                        "latency_ms": round((time.perf_counter() - t0) * 1000, 2),
                    }, (res.status_code in (200, 401))
            except Exception as e:
                return "elasticsearch", {"status": "unhealthy", "error": str(e)}, False

        async def _diag_storage() -> tuple[str, dict[str, Any], bool]:
            """Measure the uploads volume the app writes to (not MinIO)."""
            t0 = time.perf_counter()
            try:
                probe = uploads_root / ".deep-health-probe"
                probe.parent.mkdir(parents=True, exist_ok=True)
                await asyncio.to_thread(probe.write_text, "ok")
                await asyncio.to_thread(probe.unlink)
                return "storage", {
                    "status": "healthy",
                    "root": str(uploads_root),
                    "latency_ms": round((time.perf_counter() - t0) * 1000, 2),
                }, True
            except Exception as e:
                return "storage", {"status": "unhealthy", "error": str(e)}, False

        results = await asyncio.gather(
            _diag_db(), _diag_redis(), _diag_es(), _diag_storage()
        )
        for key, info, ok in results:
            diag[key] = info
            if not ok:
                all_ok = False

        # In production, dependency details (endpoints, error strings) are
        # stripped — anonymous callers learn only healthy/degraded. Full
        # diagnostics stay available in development/staging.
        if settings.ENVIRONMENT == "production":
            diag = {
                name: {"status": info["status"]}
                for name, info in diag.items()
            }

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
    @app.get("/api/v1/metrics", include_in_schema=False)
    async def metrics(request: Request) -> Any:
        """Prometheus metrics scrape endpoint.

        Guarded in production. The path sits under the nginx-proxied ``/api/``
        prefix, and the ``endpoint`` label on ``http_requests_total`` (and
        friends) enumerates every route the process has served — including
        ``/admin/*``. An open scrape therefore hands out a map of the admin
        surface without authenticating. Outside production the endpoint stays
        open so local scraping needs no setup.
        """
        from starlette.responses import Response

        if settings.ENVIRONMENT == "production":
            expected = settings.METRICS_TOKEN
            header = request.headers.get("authorization", "")
            scheme, _, presented = header.partition(" ")
            # compare_digest: a plain == leaks the token prefix through timing.
            ok = (
                bool(expected)
                and scheme.lower() == "bearer"
                and secrets.compare_digest(presented, expected)
            )
            if not ok:
                # 404, not 401: a 401 confirms the endpoint exists, which is
                # the reconnaissance this guard is meant to deny.
                raise HTTPException(status_code=404, detail="Not found")

        return Response(
            content=generate_latest(),
            media_type=CONTENT_TYPE_LATEST,
        )

    @app.api_route(
        "/api/v1/observability/synthetic-delay",
        methods=["GET", "POST"],
        include_in_schema=False,
    )
    async def synthetic_delay(
        delay_ms: float = 1000.0,
        component: str = "api",
    ) -> JSONResponse:
        """Inject artificial latency for testing SLO alerts and slow-query loggers.

        Guarded strictly by DEBUG=True. In production environments where DEBUG=False,
        this endpoint fails closed with HTTP 403 Forbidden.
        """
        if not settings.DEBUG:
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={
                    "error": "Synthetic delay injection is only permitted when DEBUG=True",
                    "status": "forbidden",
                },
            )

        clamped_delay = max(0.0, min(delay_ms, 15000.0))
        delay_sec = clamped_delay / 1000.0
        comp = component.lower()

        if comp == "database":
            t0 = time.perf_counter()
            async with engine.connect() as conn:
                await conn.execute(
                    text("SELECT pg_sleep(:delay_sec)"), {"delay_sec": delay_sec}
                )
            actual_delay_ms = round((time.perf_counter() - t0) * 1000, 2)
        elif comp == "redis":
            t0 = time.perf_counter()
            await asyncio.sleep(delay_sec)
            client = await get_redis()
            await client.ping()
            actual_delay_ms = round((time.perf_counter() - t0) * 1000, 2)
        else:
            t0 = time.perf_counter()
            await asyncio.sleep(delay_sec)
            actual_delay_ms = round((time.perf_counter() - t0) * 1000, 2)

        await logger.awarning(
            "synthetic_delay_injected",
            component=comp,
            requested_delay_ms=clamped_delay,
            actual_delay_ms=actual_delay_ms,
        )

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "status": "success",
                "injected": True,
                "component": comp,
                "delay_ms": actual_delay_ms,
            },
        )


# ── Module-level application instance (used by uvicorn) ──────────────────
app = create_app()
