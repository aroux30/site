"""user verification orders: verified-badge status + verification log table

Ports the owner's WordPress plugin ``user-verification-orders`` (v1.1):

* ``user_verification_logs`` — the plugin's ``wp_uv_verification_logs``: one
  row per admin verify/unverify flip, with the acting admin, IP and timestamp
  (the plugin's "گزارش لاگ‌ها" tab). Telegram notification stays in the
  application layer; credentials live in the ``userverify.config`` setting row.
* ``OrderStatus.DOING_VERIFIED`` ("doing_verified") — the plugin's
  ``wc-doing_verified`` ("در حال انجام (احراز شده)"). The ``orders.status``
  column is a plain VARCHAR (``native_enum=False, length=32``), so the new
  value needs no DDL; it is handled entirely in the application layer.

Additive only: no existing table or row is touched.

Revision ID: uvord1
Revises: curr1
Create Date: 2026-10-16
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "uvord1"
down_revision: str | None = "curr1"

branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_verification_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "admin_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        # True = verified, False = unverified (the plugin's TINYINT status).
        sa.Column("status", sa.Boolean(), nullable=False),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_user_verification_logs_user_id", "user_verification_logs", ["user_id"]
    )
    op.create_index(
        "ix_user_verification_logs_created_at", "user_verification_logs", ["created_at"]
    )


def downgrade() -> None:
    op.drop_index(
        "ix_user_verification_logs_created_at", table_name="user_verification_logs"
    )
    op.drop_index(
        "ix_user_verification_logs_user_id", table_name="user_verification_logs"
    )
    op.drop_table("user_verification_logs")
