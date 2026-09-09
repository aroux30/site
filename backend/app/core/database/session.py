"""Async SQLAlchemy engine, session factory, and dependency.

The single ``Base`` declarative model lives in ``base.py``.  This module
builds the async engine and session factory on top of it and exposes the
``get_db`` FastAPI dependency.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config.settings import get_settings
from app.core.database.base import Base  # noqa: F401 – re-export so legacy imports work


# ── Engine & session factory ──────────────────────────────────────────────


def _build_engine() -> Any:
    settings = get_settings()
    return create_async_engine(
        settings.database_url_str,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_timeout=settings.DB_POOL_TIMEOUT,
        pool_pre_ping=True,
        echo=settings.DB_ECHO,
    )


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
