"""Add email_delivery_logs table for per-email delivery auditing.

Real SMTP email integration (ERP benchmark feature #24): every outbound
email attempt persists one row here with status queued/sent/failed, the
provider response line, and a sanitized error so ops can audit delivery
without reading worker logs.

Revision ID: u3v4w5x6y7z8
Revises: t2u3v4w5x6y7
Create Date: 2026-09-24 20:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "u3v4w5x6y7z8"
down_revision = "t2u3v4w5x6y7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "email_delivery_logs",
        sa.Column(
            "notification_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("notifications.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("recipient", sa.String(length=320), nullable=False),
        sa.Column("subject", sa.String(length=500), nullable=False),
        sa.Column("template", sa.String(length=100), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "QUEUED", "SENT", "FAILED",
                name="email_delivery_status_enum",
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
        "ix_email_delivery_logs_recipient", "email_delivery_logs", ["recipient"], unique=False
    )
    op.create_index(
        "ix_email_delivery_logs_status", "email_delivery_logs", ["status"], unique=False
    )
    op.create_index(
        "ix_email_delivery_logs_notification_id",
        "email_delivery_logs",
        ["notification_id"],
        unique=False,
    )
    op.create_index(
        "ix_email_delivery_logs_created_at", "email_delivery_logs", ["created_at"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_email_delivery_logs_created_at", table_name="email_delivery_logs")
    op.drop_index("ix_email_delivery_logs_notification_id", table_name="email_delivery_logs")
    op.drop_index("ix_email_delivery_logs_status", table_name="email_delivery_logs")
    op.drop_index("ix_email_delivery_logs_recipient", table_name="email_delivery_logs")
    op.drop_table("email_delivery_logs")
