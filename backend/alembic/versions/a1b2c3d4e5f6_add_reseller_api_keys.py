"""Add reseller API keys table for B2B wholesale purchasing (Karta Phase 4).

Revision ID: a1b2c3d4e5f6
Revises: f8a2b4c6d9e1
Create Date: 2026-09-12 19:30:00

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "a1b2c3d4e5f6"
down_revision = "f8a2b4c6d9e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reseller_api_keys",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("key_prefix", sa.String(length=16), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("ip_whitelist", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("credit_balance", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("rate_limit_per_minute", sa.Integer(), nullable=False, server_default=sa.text("60")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_reseller_api_keys_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reseller_api_keys")),
        sa.UniqueConstraint("key_hash", name=op.f("uq_reseller_api_keys_key_hash")),
    )
    op.create_index("ix_reseller_api_keys_user_id", "reseller_api_keys", ["user_id"], unique=False)
    op.create_index("ix_reseller_api_keys_key_hash", "reseller_api_keys", ["key_hash"], unique=False)
    op.create_index("ix_reseller_api_keys_is_active", "reseller_api_keys", ["is_active"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_reseller_api_keys_is_active", table_name="reseller_api_keys")
    op.drop_index("ix_reseller_api_keys_key_hash", table_name="reseller_api_keys")
    op.drop_index("ix_reseller_api_keys_user_id", table_name="reseller_api_keys")
    op.drop_table("reseller_api_keys")
