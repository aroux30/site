"""Async SQLAlchemy engine, session factory, and observability hooks.

Instruments query duration, slow query detection, connection pool metrics,
and distributed tracing via OpenTelemetry.
"""

from __future__ import annotations

import contextlib
import time
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config.settings import get_settings
from app.core.observability.metrics import (
    DB_POOL_CHECKED_IN,
    DB_POOL_CHECKED_OUT,
    DB_POOL_SIZE,
    DB_QUERY_DURATION,
)
from app.core.observability.tracer import instrument_sqlalchemy

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


def _build_engine() -> Any:
    settings = get_settings()
    engine_instance = create_async_engine(
        settings.database_url_str,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_timeout=settings.DB_POOL_TIMEOUT,
        pool_pre_ping=True,
        echo=settings.DB_ECHO,
    )

    # Instrument with OpenTelemetry
    instrument_sqlalchemy(engine_instance)

    # Attach performance and connection pool event listeners
    _setup_db_event_listeners(engine_instance.sync_engine)

    return engine_instance


def _setup_db_event_listeners(sync_engine: Any) -> None:
    """Register SQLAlchemy event hooks for metrics, pool tracking, and slow query logging."""
    settings = get_settings()

    @event.listens_for(sync_engine, "before_cursor_execute")
    def before_cursor_execute(
        conn: Any,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        context._query_start_time = time.perf_counter()

    @event.listens_for(sync_engine, "after_cursor_execute")
    def after_cursor_execute(
        conn: Any,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        start_time = getattr(context, "_query_start_time", None)
        if start_time is None:
            return

        duration = time.perf_counter() - start_time
        duration_ms = round(duration * 1000, 2)

        # Extract normalized operation name (SELECT, INSERT, UPDATE, DELETE, etc.)
        op = statement.strip().split()[0].upper() if statement else "QUERY"
        DB_QUERY_DURATION.labels(operation=op).observe(duration)

        # Detect slow query
        threshold = settings.DATABASE_SLOW_QUERY_THRESHOLD_MS
        if duration_ms >= threshold:
            logger.warning(
                "slow_query",
                operation=op,
                duration_ms=duration_ms,
                threshold_ms=threshold,
                statement_sample=statement[:250].replace("\n", " ").strip(),
            )

    @event.listens_for(sync_engine, "handle_error")
    def handle_error(exception_context: Any) -> None:
        exec_ctx = getattr(exception_context, "execution_context", None)
        start_time = getattr(exec_ctx, "_query_start_time", None) if exec_ctx else None
        if start_time is not None:
            duration = time.perf_counter() - start_time
            statement = getattr(exception_context, "statement", "") or ""
            op = statement.strip().split()[0].upper() if statement else "QUERY"
            DB_QUERY_DURATION.labels(operation=op).observe(duration)

    @event.listens_for(sync_engine.pool, "checkout")
    def pool_checkout(
        dbapi_connection: Any,
        connection_record: Any,
        connection_proxy: Any,
    ) -> None:
        with contextlib.suppress(Exception):
            DB_POOL_CHECKED_OUT.inc()
            if hasattr(sync_engine.pool, "checkedin"):
                DB_POOL_CHECKED_IN.set(sync_engine.pool.checkedin())
            if hasattr(sync_engine.pool, "size"):
                DB_POOL_SIZE.set(sync_engine.pool.size())

    @event.listens_for(sync_engine.pool, "checkin")
    def pool_checkin(dbapi_connection: Any, connection_record: Any) -> None:
        with contextlib.suppress(Exception):
            DB_POOL_CHECKED_OUT.dec()
            if hasattr(sync_engine.pool, "checkedin"):
                DB_POOL_CHECKED_IN.set(sync_engine.pool.checkedin())
            if hasattr(sync_engine.pool, "size"):
                DB_POOL_SIZE.set(sync_engine.pool.size())

    @event.listens_for(sync_engine.pool, "connect")
    def pool_connect(dbapi_connection: Any, connection_record: Any) -> None:
        with contextlib.suppress(Exception):
            if hasattr(sync_engine.pool, "size"):
                DB_POOL_SIZE.set(sync_engine.pool.size())
            else:
                DB_POOL_SIZE.inc()


engine = _build_engine()

async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields a database session and closes it after use."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
