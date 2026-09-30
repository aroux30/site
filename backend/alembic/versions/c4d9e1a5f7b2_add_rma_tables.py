"""Add RMA persistence tables (TASK BE-20).

Creates ``order_returns`` + ``order_return_items`` so the customer return
lifecycle is durable and admin-processable.  The transition rules themselves
live in ``orders/domain/returns.py`` (RETURN_TRANSITIONS) and remain the
single source of truth.

Revision ID: c4d9e1a5f7b2
Revises: b3e7a9c2d154
Create Date: 2026-09-12 00:10:00

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "c4d9e1a5f7b2"
down_revision = "b3e7a9c2d154"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "order_returns",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("rma_number", sa.String(length=32), nullable=False),
        sa.Column("order_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("admin_notes", sa.Text(), nullable=True),
        sa.Column("refund_amount", sa.BigInteger(), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("inspected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("refunded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], name=op.f("fk_order_returns_order_id_orders"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_order_returns_user_id_users"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_order_returns")),
        sa.UniqueConstraint("rma_number", name=op.f("uq_order_returns_rma_number")),
    )
    op.create_index("ix_order_returns_order_id", "order_returns", ["order_id"], unique=False)
    op.create_index("ix_order_returns_user_id", "order_returns", ["user_id"], unique=False)
    op.create_index("ix_order_returns_status", "order_returns", ["status"], unique=False)

    op.create_table(
        "order_return_items",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("return_id", sa.UUID(), nullable=False),
        sa.Column("order_item_id", sa.UUID(), nullable=False),
        sa.Column("variant_id", sa.UUID(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=50), nullable=False),
        sa.Column("inspection_outcome", sa.String(length=50), nullable=True),
        sa.Column("customer_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["return_id"], ["order_returns.id"], name=op.f("fk_order_return_items_return_id_order_returns"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["order_item_id"], ["order_items.id"], name=op.f("fk_order_return_items_order_item_id_order_items"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["variant_id"], ["product_variants.id"], name=op.f("fk_order_return_items_variant_id_product_variants"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_order_return_items")),
        sa.CheckConstraint("quantity > 0", name=op.f("ck_order_return_items_quantity_positive")),
    )
    op.create_index("ix_order_return_items_return_id", "order_return_items", ["return_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_order_return_items_return_id", table_name="order_return_items")
    op.drop_table("order_return_items")
    op.drop_index("ix_order_returns_status", table_name="order_returns")
    op.drop_index("ix_order_returns_user_id", table_name="order_returns")
    op.drop_index("ix_order_returns_order_id", table_name="order_returns")
    op.drop_table("order_returns")
