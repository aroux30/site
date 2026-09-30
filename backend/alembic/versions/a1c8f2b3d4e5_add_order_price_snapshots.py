"""Add order_price_snapshots table.

Revision ID: a1c8f2b3d4e5
Revises: c8e1f4a7b2d6
Create Date: 2026-09-19 12:00:00

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "a1c8f2b3d4e5"
down_revision = "c8e1f4a7b2d6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "order_price_snapshots",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("order_id", sa.UUID(), nullable=False),
        sa.Column("currency", sa.String(length=10), server_default="IRR", nullable=False),
        sa.Column("lines", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("subtotal_rial", sa.BigInteger(), nullable=False),
        sa.Column("total_discount_rial", sa.BigInteger(), nullable=False),
        sa.Column("total_tax_rial", sa.BigInteger(), nullable=False),
        sa.Column("shipping_rial", sa.BigInteger(), nullable=False),
        sa.Column("grand_total_rial", sa.BigInteger(), nullable=False),
        sa.Column("snapshot_hash", sa.String(length=64), nullable=False),
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
            ["order_id"],
            ["orders.id"],
            name=op.f("fk_order_price_snapshots_order_id_orders"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_order_price_snapshots")),
        sa.UniqueConstraint("order_id", name=op.f("uq_order_price_snapshots_order_id")),
    )
    op.create_index(
        "ix_order_price_snapshots_order_id",
        "order_price_snapshots",
        ["order_id"],
        unique=True,
    )
    op.create_index(
        "ix_order_price_snapshots_created_at",
        "order_price_snapshots",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_order_price_snapshots_created_at", table_name="order_price_snapshots")
    op.drop_index("ix_order_price_snapshots_order_id", table_name="order_price_snapshots")
    op.drop_table("order_price_snapshots")
