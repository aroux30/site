"""Add notification channel v1 tables: preferences, telegram logs, push subscriptions.

ERP benchmark feature #10 (Notifications, P0) — channel completion v1:

- ``notification_preferences``: per-user channel/category opt-in matrix
  (JSONB, missing key = default ON) plus Telegram link state (chat_id and
  the single-use verification code with expiry).
- ``telegram_delivery_logs``: per-message delivery audit for the real
  Telegram Bot API provider (mirror of email_delivery_logs).
- ``push_subscriptions``: browser Web Push subscriptions (endpoint +
  VAPID keys), deduped by endpoint.

Revision ID: v4w5x6y7z8a9
Revises: u3v4w5x6y7z8
Create Date: 2026-09-24 22:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "v4w5x6y7z8a9"
down_revision = "u3v4w5x6y7z8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notification_preferences",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("channels", postgresql.JSONB(), nullable=True),
        sa.Column("categories", postgresql.JSONB(), nullable=True),
        sa.Column("telegram_chat_id", sa.String(length=64), nullable=True),
        sa.Column("telegram_link_code", sa.String(length=16), nullable=True),
        sa.Column("telegram_link_code_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index(
        "ix_notification_preferences_user_id",
        "notification_preferences",
        ["user_id"],
        unique=True,
    )

    op.create_table(
        "telegram_delivery_logs",
        sa.Column(
            "notification_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("notifications.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("recipient", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "QUEUED", "SENT", "FAILED",
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
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
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
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_telegram_delivery_logs_recipient",
        "telegram_delivery_logs",
        ["recipient"],
        unique=False,
    )
    op.create_index(
        "ix_telegram_delivery_logs_status", "telegram_delivery_logs", ["status"], unique=False
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
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("endpoint", sa.Text(), nullable=False),
        sa.Column("keys", postgresql.JSONB(), nullable=False),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("endpoint"),
    )
    op.create_index(
        "ix_push_subscriptions_user_id", "push_subscriptions", ["user_id"], unique=False
    )
    op.create_index(
        "ix_push_subscriptions_endpoint", "push_subscriptions", ["endpoint"], unique=True
    )


def downgrade() -> None:
    op.drop_index("ix_push_subscriptions_endpoint", table_name="push_subscriptions")
    op.drop_index("ix_push_subscriptions_user_id", table_name="push_subscriptions")
    op.drop_table("push_subscriptions")
    op.drop_index("ix_telegram_delivery_logs_created_at", table_name="telegram_delivery_logs")
    op.drop_index(
        "ix_telegram_delivery_logs_notification_id", table_name="telegram_delivery_logs"
    )
    op.drop_index("ix_telegram_delivery_logs_status", table_name="telegram_delivery_logs")
    op.drop_index("ix_telegram_delivery_logs_recipient", table_name="telegram_delivery_logs")
    op.drop_table("telegram_delivery_logs")
    op.drop_index(
        "ix_notification_preferences_user_id", table_name="notification_preferences"
    )
    op.drop_table("notification_preferences")
