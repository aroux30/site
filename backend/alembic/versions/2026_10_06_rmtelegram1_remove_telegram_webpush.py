"""Remove the Telegram bot and Web Push (VAPID) notification channels
(owner decision 2026-10-06).

The owner asked for «تلگرام» و «Web push» to be deleted outright — they have
no use in a retail storefront. The code is archived under
``_archived/telegram-webpush-removal-2026-10-06/``.

What goes with this migration:

- **``telegram_delivery_logs``** — the per-message Telegram audit table.
  Verified at removal time (live probe 2026-10-06): 0 rows.
- **``push_subscriptions``** — browser Web Push subscriptions (endpoint +
  VAPID keys). Verified at removal time: 0 rows.
- **Three Telegram link columns on ``notification_preferences``**
  (``telegram_chat_id``, ``telegram_link_code``,
  ``telegram_link_code_expires_at``). The single live preference row had all
  three NULL, so no link state is lost.

Not touched on purpose:

- ``notification_preferences`` itself — the channel/category opt-in matrix
  stays (email/sms/in_app remain).
- ``notification_templates.channel`` and ``broadcast_campaigns.channel`` —
  enum-typed columns stored as VARCHAR (``native_enum=False``) with no CHECK
  constraint; removing the TELEGRAM/PUSH enum members needs no schema change
  and no row rewrite (0 rows used either value at removal time).

``downgrade()`` recreates both tables exactly as the live database had them
at removal time (indexes and FK names included, from
``db_snapshot_before.json``) and re-adds the three nullable columns. The 0
rows are not restored — the removed channels were the only writers.

Revision ID: rmtelegram1
Revises: rmprivacy1
Create Date: 2026-10-06
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "rmtelegram1"
down_revision = "rmprivacy1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Telegram link state on the preference matrix. Children first: the
    # table, then its indexes go with it automatically.
    op.drop_column("notification_preferences", "telegram_link_code_expires_at")
    op.drop_column("notification_preferences", "telegram_link_code")
    op.drop_column("notification_preferences", "telegram_chat_id")

    # Explicit index drops keep the downgrade symmetrical; dropping the table
    # would cascade, but naming the indexes documents what existed.
    op.drop_index("ix_telegram_delivery_logs_created_at", table_name="telegram_delivery_logs")
    op.drop_index("ix_telegram_delivery_logs_notification_id", table_name="telegram_delivery_logs")
    op.drop_index("ix_telegram_delivery_logs_status", table_name="telegram_delivery_logs")
    op.drop_index("ix_telegram_delivery_logs_recipient", table_name="telegram_delivery_logs")
    op.drop_table("telegram_delivery_logs")

    op.drop_index("ix_push_subscriptions_endpoint", table_name="push_subscriptions")
    op.drop_index("ix_push_subscriptions_user_id", table_name="push_subscriptions")
    op.drop_table("push_subscriptions")


def downgrade() -> None:
    """Recreate both tables and the three preference columns as of removal.

    Column set, index names and FK names come from the live schema captured
    in ``db_snapshot_before.json``. Enum columns are VARCHAR
    (``native_enum=False``); stored values are the member NAMES, per this
    schema's enum-storage contract.
    """
    op.create_table(
        "telegram_delivery_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("notification_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("recipient", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "QUEUED",
                "SENT",
                "FAILED",
                name="telegram_delivery_status_enum",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("provider_response", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["notification_id"],
            ["notifications.id"],
            name="fk_telegram_delivery_logs_notification_id_notifications",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_telegram_delivery_logs"),
    )
    op.create_index(
        "ix_telegram_delivery_logs_recipient",
        "telegram_delivery_logs",
        ["recipient"],
        unique=False,
    )
    op.create_index(
        "ix_telegram_delivery_logs_status",
        "telegram_delivery_logs",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_telegram_delivery_logs_notification_id",
        "telegram_delivery_logs",
        ["notification_id"],
        unique=False,
    )
    op.create_index(
        "ix_telegram_delivery_logs_created_at",
        "telegram_delivery_logs",
        ["created_at"],
        unique=False,
    )

    op.create_table(
        "push_subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("endpoint", sa.Text(), nullable=False),
        sa.Column("keys", postgresql.JSONB(), nullable=False),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_push_subscriptions_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_push_subscriptions"),
        sa.UniqueConstraint("endpoint", name="uq_push_subscriptions_endpoint"),
    )
    op.create_index(
        "ix_push_subscriptions_user_id",
        "push_subscriptions",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_push_subscriptions_endpoint",
        "push_subscriptions",
        ["endpoint"],
        unique=True,
    )

    # Telegram link state back on the preference matrix (all nullable, all
    # NULL on the single live row at removal time).
    op.add_column(
        "notification_preferences",
        sa.Column("telegram_chat_id", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "notification_preferences",
        sa.Column("telegram_link_code", sa.String(length=16), nullable=True),
    )
    op.add_column(
        "notification_preferences",
        sa.Column(
            "telegram_link_code_expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
