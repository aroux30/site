"""Alembic environment configuration with async PostgreSQL support.

This module is executed by Alembic during ``alembic revision``,
``alembic upgrade``, and ``alembic downgrade`` commands.
"""

from __future__ import annotations

import asyncio
import os
import sys
from logging.config import fileConfig

# Ensure backend root is always on sys.path for CLI execution
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config.settings import get_settings
from app.core.database.base import Base

# ---------------------------------------------------------------------------
# Import ALL model modules so their tables are registered on Base.metadata.
# Without these imports Alembic autogenerate cannot detect any tables.
# ---------------------------------------------------------------------------
import app.modules.analytics.domain.models  # noqa: F401
import app.modules.accounting.domain.models  # noqa: F401
import app.modules.approvals.domain.models  # noqa: F401
import app.modules.audit.domain.models  # noqa: F401
import app.modules.audit.domain.reconciliation  # noqa: F401
import app.modules.audit.domain.entity_changelog  # noqa: F401
import app.modules.blog.domain.models  # noqa: F401
import app.modules.cart.domain.models  # noqa: F401
import app.modules.cashback.domain.models  # noqa: F401
import app.modules.catalog.domain.models  # noqa: F401
import app.modules.checkout.domain.models  # noqa: F401
import app.modules.checkout.domain.price_snapshot  # noqa: F401
import app.modules.checkout.domain.tax_models  # noqa: F401
import app.modules.content.domain.models  # noqa: F401
import app.modules.content.domain.meta  # noqa: F401
import app.modules.content.domain.reusable_blocks  # noqa: F401
import app.modules.crm.domain.models  # noqa: F401
import app.modules.dataexchange.domain.models  # noqa: F401
import app.modules.discounts.domain.models  # noqa: F401
import app.modules.dms.domain.models  # noqa: F401
import app.modules.gamification.domain.models  # noqa: F401
import app.modules.gamification.domain.gift_models  # noqa: F401
import app.modules.integrations.domain.webhooks  # noqa: F401
import app.modules.inventory.domain.models  # noqa: F401
import app.modules.inventory.domain.digital_models  # noqa: F401
import app.modules.invoicing.domain.models  # noqa: F401
import app.modules.loyalty.domain.models  # noqa: F401
import app.modules.media.domain.models  # noqa: F401
import app.modules.messaging.domain.models  # noqa: F401
import app.modules.notifications.domain.models  # noqa: F401
import app.modules.notifications.domain.notice_models  # noqa: F401
import app.modules.orders.domain.models  # noqa: F401
import app.modules.orders.domain.return_models  # noqa: F401
import app.modules.orders.domain.reseller_models  # noqa: F401
import app.modules.payments.domain.models  # noqa: F401
import app.modules.payments.domain.allocation_models  # noqa: F401
import app.modules.payments.domain.installment_models  # noqa: F401
import app.modules.payments.domain.saved_method_models  # noqa: F401
import app.modules.pricing.domain.models  # noqa: F401
import app.modules.procurement.domain.models  # noqa: F401
import app.modules.payments.domain.fintech_models  # noqa: F401
import app.modules.rbac.domain.models  # noqa: F401
import app.modules.referrals.domain.models  # noqa: F401
import app.modules.reporting.domain.models  # noqa: F401
import app.modules.reviews.domain.models  # noqa: F401
import app.modules.seo.domain.models  # noqa: F401
import app.modules.settings.domain.models  # noqa: F401
import app.modules.subscriptions.domain.models  # noqa: F401
import app.modules.shipping.domain.models  # noqa: F401
import app.modules.support.domain.models  # noqa: F401
import app.modules.users.domain.models  # noqa: F401
import app.modules.users.domain.kyc_models  # noqa: F401
import app.modules.vendors.domain.models  # noqa: F401
import app.modules.wallet.domain.models  # noqa: F401
import app.modules.wishlist.domain.models  # noqa: F401
import app.shared.events.outbox_models  # noqa: F401

# ── Alembic Config object ────────────────────────────────────────────────
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set the SQLAlchemy URL from application settings
settings = get_settings()
# configparser treats % as interpolation syntax, so a literal % in the URL
# (a password character, or URL-encoded query params) would crash every
# alembic command. Doubling it makes set_main_option round-trip safely.
config.set_main_option("sqlalchemy.url", settings.database_url_str.replace("%", "%%"))

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
        # compare_type disabled: the project deliberately uses Enum(...,
        # native_enum=False) (VARCHAR + CHECK) while several migrations
        # declared plain VARCHAR columns — autogenerate reports a false
        # type diff for every such column. Server defaults ARE compared.
        compare_type=False,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Configure context and run migrations within the given connection."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        # See the compare_type note in render_as_batch/offline config above.
        compare_type=False,
        compare_server_default=True,
        include_schemas=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode with an async engine."""
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = settings.database_url_str

    # ALEMBIC_SCHEMA runs the whole chain inside an explicitly-set PostgreSQL
    # schema instead of the default one. This is how a from-empty run is
    # verified without needing CREATEDB: point it at a scratch schema,
    # upgrade head, count tables, drop the schema. Unset in normal operation.
    _schema = os.environ.get("ALEMBIC_SCHEMA")
    connect_args: dict[str, object] = {}
    if _schema:
        connect_args["server_settings"] = {"search_path": _schema}

    connectable = create_async_engine(
        configuration["sqlalchemy.url"],
        poolclass=pool.NullPool,
        connect_args=connect_args,  # type: ignore[arg-type]
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
