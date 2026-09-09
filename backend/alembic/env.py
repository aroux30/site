"""Alembic environment configuration with async PostgreSQL support.

This module is executed by Alembic during ``alembic revision``,
``alembic upgrade``, and ``alembic downgrade`` commands.
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.config.settings import get_settings
from app.core.database.base import Base

# ---------------------------------------------------------------------------
# Import ALL model modules so their tables are registered on Base.metadata.
# Without these imports Alembic autogenerate cannot detect any tables.
# ---------------------------------------------------------------------------
import app.modules.analytics.domain.models  # noqa: F401
import app.modules.approvals.domain.models  # noqa: F401
import app.modules.audit.domain.models  # noqa: F401
import app.modules.blog.domain.models  # noqa: F401
import app.modules.cart.domain.models  # noqa: F401
import app.modules.cashback.domain.models  # noqa: F401
import app.modules.catalog.domain.models  # noqa: F401
import app.modules.discounts.domain.models  # noqa: F401
import app.modules.gamification.domain.models  # noqa: F401
import app.modules.inventory.domain.models  # noqa: F401
import app.modules.loyalty.domain.models  # noqa: F401
import app.modules.media.domain.models  # noqa: F401
import app.modules.messaging.domain.models  # noqa: F401
import app.modules.notifications.domain.models  # noqa: F401
import app.modules.orders.domain.models  # noqa: F401
import app.modules.payments.domain.models  # noqa: F401
import app.modules.rbac.domain.models  # noqa: F401
import app.modules.referrals.domain.models  # noqa: F401
import app.modules.reviews.domain.models  # noqa: F401
import app.modules.seo.domain.models  # noqa: F401
import app.modules.settings.domain.models  # noqa: F401
import app.modules.shipping.domain.models  # noqa: F401
import app.modules.support.domain.models  # noqa: F401
import app.modules.users.domain.models  # noqa: F401
import app.modules.vendors.domain.models  # noqa: F401
import app.modules.wallet.domain.models  # noqa: F401
import app.modules.wishlist.domain.models  # noqa: F401

# ── Alembic Config object ────────────────────────────────────────────────
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set the SQLAlchemy URL from application settings
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url_str)

# MetaData object for 'autogenerate' support
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    Generates SQL scripts without requiring a live database connection.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Configure context and run migrations within the given connection."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        include_schemas=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode with an async engine."""
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = settings.database_url_str

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
