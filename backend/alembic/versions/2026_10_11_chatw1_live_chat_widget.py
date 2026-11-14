"""Live-chat widget: sessions, messages, and presence.

Ports the WordPress "N8n Custom Chat Widget" plugin (v6.5.5) into the modular
monolith. Three additive tables, no existing table touched:

* ``chat_sessions``  — one conversation thread (guest or customer) + pre-chat
  form values + hand-off deadline + Telegram topic id.
* ``chat_messages``  — the message log (user / ai / admin / system).
* ``chat_presence``  — the 5s heartbeat / online-monitor rows.

Enums are stored as NAMES (``native_enum=False``), the repo-wide contract.

Revision ID: chatw1
Revises: seolg2
Create Date: 2026-10-11
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import UUID

revision: str = "chatw1"
down_revision: str | None = "seolg2"

branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> list[sa.Column]:
    return [
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
    ]


def upgrade() -> None:
    op.create_table(
        "chat_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_key", sa.String(length=120), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("user_name", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("user_email", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("user_phone", sa.String(length=50), nullable=False, server_default=""),
        sa.Column("user_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("tg_topic_id", sa.BigInteger(), nullable=True),
        sa.Column("handoff_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "last_activity_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        *_timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_key", name="uq_chat_sessions_session_key"),
    )
    op.create_index("ix_chat_sessions_session_key", "chat_sessions", ["session_key"])
    op.create_index("ix_chat_sessions_user_id", "chat_sessions", ["user_id"])
    op.create_index("ix_chat_sessions_last_activity_at", "chat_sessions", ["last_activity_at"])

    op.create_table(
        "chat_messages",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "role",
            sa.Enum(
                "USER",
                "AI",
                "ADMIN",
                "SYSTEM",
                name="chat_role_enum",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("sender_name", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        *_timestamps(),
        sa.ForeignKeyConstraint(["session_id"], ["chat_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_chat_messages_session_id", "chat_messages", ["session_id"])
    op.create_index("ix_chat_messages_role", "chat_messages", ["role"])
    op.create_index("ix_chat_messages_is_read", "chat_messages", ["is_read"])
    op.create_index("ix_chat_messages_created_at", "chat_messages", ["created_at"])

    op.create_table(
        "chat_presence",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_key", sa.String(length=140), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("user_name", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("user_ip", sa.String(length=60), nullable=False, server_default=""),
        sa.Column("user_agent", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("page_url", sa.Text(), nullable=False, server_default=""),
        sa.Column("page_title", sa.String(length=500), nullable=False, server_default=""),
        sa.Column(
            "last_seen",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        *_timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_key", name="uq_chat_presence_session_key"),
    )
    op.create_index("ix_chat_presence_session_key", "chat_presence", ["session_key"])
    op.create_index("ix_chat_presence_last_seen", "chat_presence", ["last_seen"])


def downgrade() -> None:
    op.drop_index("ix_chat_presence_last_seen", table_name="chat_presence")
    op.drop_index("ix_chat_presence_session_key", table_name="chat_presence")
    op.drop_table("chat_presence")
    op.drop_index("ix_chat_messages_created_at", table_name="chat_messages")
    op.drop_index("ix_chat_messages_is_read", table_name="chat_messages")
    op.drop_index("ix_chat_messages_role", table_name="chat_messages")
    op.drop_index("ix_chat_messages_session_id", table_name="chat_messages")
    op.drop_table("chat_messages")
    op.drop_index("ix_chat_sessions_last_activity_at", table_name="chat_sessions")
    op.drop_index("ix_chat_sessions_user_id", table_name="chat_sessions")
    op.drop_index("ix_chat_sessions_session_key", table_name="chat_sessions")
    op.drop_table("chat_sessions")
