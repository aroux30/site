"""Inventory physical operations v1: cycle counts, transfers, and receipts.

Revision ID: y7z8a9b0c1d2
Revises: x6y7z8a9b0c1d
Create Date: 2026-09-24 23:59:00

Adds workflow records only. Posting remains application-service driven and
creates typed ``inventory_transactions``; this migration never changes stock.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "y7z8a9b0c1d2"
down_revision = "x6y7z8a9b0c1d"
branch_labels = None
depends_on = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
    ]


def upgrade() -> None:
    # ── Cycle-count headers and frozen SKU snapshots ──────────────────────
    op.create_table(
        "stock_counts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("warehouse_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "DRAFT", "COUNTING", "REVIEW", "POSTED", "CANCELLED",
                name="stock_count_status_enum", native_enum=False,
            ),
            nullable=False,
            server_default="DRAFT",
        ),
        sa.Column(
            "scope",
            sa.Enum(
                "FULL", "CATEGORY", "PRODUCT_LIST",
                name="stock_count_scope_enum", native_enum=False,
            ),
            nullable=False,
            server_default="FULL",
        ),
        sa.Column(
            "scope_filter", postgresql.JSONB(astext_type=sa.Text()), nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("line_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("counted_line_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("variance_line_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("variance_quantity", sa.Integer(), nullable=False, server_default="0"),
        *_timestamps(),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_stock_counts_warehouse_id", "stock_counts", ["warehouse_id"])
    op.create_index("ix_stock_counts_status", "stock_counts", ["status"])
    op.create_index("ix_stock_counts_created_by", "stock_counts", ["created_by"])
    op.create_index("ix_stock_counts_created_at", "stock_counts", ["created_at"])

    op.create_table(
        "stock_count_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("count_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_variant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("system_qty", sa.Integer(), nullable=False),
        sa.Column("counted_qty", sa.Integer(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("system_qty >= 0", name="ck_stock_count_system_qty_non_negative"),
        sa.CheckConstraint(
            "counted_qty IS NULL OR counted_qty >= 0",
            name="ck_stock_count_counted_qty_non_negative",
        ),
        sa.ForeignKeyConstraint(["count_id"], ["stock_counts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["product_variant_id"], ["product_variants.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("count_id", "product_variant_id", name="uq_stock_count_lines_count_variant"),
    )
    op.create_index("ix_stock_count_lines_count_id", "stock_count_lines", ["count_id"])
    op.create_index(
        "ix_stock_count_lines_product_variant_id", "stock_count_lines", ["product_variant_id"]
    )

    # ── Two-step warehouse transfer headers and lines ─────────────────────
    op.create_table(
        "warehouse_transfers",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("from_warehouse_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("to_warehouse_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "DRAFT", "SHIPPED", "RECEIVED", "CANCELLED",
                name="warehouse_transfer_status_enum", native_enum=False,
            ),
            nullable=False,
            server_default="DRAFT",
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=255), nullable=True),
        sa.Column("shipped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(
            "from_warehouse_id <> to_warehouse_id", name="ck_warehouse_transfer_distinct_warehouses"
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", name="uq_warehouse_transfers_idempotency_key"),
    )
    op.create_index(
        "ix_warehouse_transfers_from_warehouse_id", "warehouse_transfers", ["from_warehouse_id"]
    )
    op.create_index(
        "ix_warehouse_transfers_to_warehouse_id", "warehouse_transfers", ["to_warehouse_id"]
    )
    op.create_index("ix_warehouse_transfers_status", "warehouse_transfers", ["status"])
    op.create_index(
        "ix_warehouse_transfers_idempotency_key", "warehouse_transfers", ["idempotency_key"]
    )

    op.create_table(
        "warehouse_transfer_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("transfer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_variant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("quantity > 0", name="ck_warehouse_transfer_line_quantity_positive"),
        sa.ForeignKeyConstraint(
            ["transfer_id"], ["warehouse_transfers.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["product_variant_id"], ["product_variants.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "transfer_id", "product_variant_id", name="uq_transfer_lines_transfer_variant"
        ),
    )
    op.create_index(
        "ix_warehouse_transfer_lines_transfer_id", "warehouse_transfer_lines", ["transfer_id"]
    )

    # ── Blind receiving headers and lines ─────────────────────────────────
    op.create_table(
        "inventory_receipts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("warehouse_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "DRAFT", "RECEIVED", "CANCELLED",
                name="inventory_receipt_status_enum", native_enum=False,
            ),
            nullable=False,
            server_default="DRAFT",
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_inventory_receipts_warehouse_id", "inventory_receipts", ["warehouse_id"])
    op.create_index("ix_inventory_receipts_status", "inventory_receipts", ["status"])
    op.create_index("ix_inventory_receipts_created_at", "inventory_receipts", ["created_at"])

    op.create_table(
        "inventory_receipt_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("receipt_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_variant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("quantity > 0", name="ck_inventory_receipt_line_quantity_positive"),
        sa.ForeignKeyConstraint(["receipt_id"], ["inventory_receipts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["product_variant_id"], ["product_variants.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "receipt_id", "product_variant_id", name="uq_receipt_lines_receipt_variant"
        ),
    )
    op.create_index(
        "ix_inventory_receipt_lines_receipt_id", "inventory_receipt_lines", ["receipt_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_inventory_receipt_lines_receipt_id", table_name="inventory_receipt_lines")
    op.drop_table("inventory_receipt_lines")
    op.drop_index("ix_inventory_receipts_created_at", table_name="inventory_receipts")
    op.drop_index("ix_inventory_receipts_status", table_name="inventory_receipts")
    op.drop_index("ix_inventory_receipts_warehouse_id", table_name="inventory_receipts")
    op.drop_table("inventory_receipts")

    op.drop_index("ix_warehouse_transfer_lines_transfer_id", table_name="warehouse_transfer_lines")
    op.drop_table("warehouse_transfer_lines")
    op.drop_index("ix_warehouse_transfers_idempotency_key", table_name="warehouse_transfers")
    op.drop_index("ix_warehouse_transfers_status", table_name="warehouse_transfers")
    op.drop_index("ix_warehouse_transfers_to_warehouse_id", table_name="warehouse_transfers")
    op.drop_index("ix_warehouse_transfers_from_warehouse_id", table_name="warehouse_transfers")
    op.drop_table("warehouse_transfers")

    op.drop_index("ix_stock_count_lines_product_variant_id", table_name="stock_count_lines")
    op.drop_index("ix_stock_count_lines_count_id", table_name="stock_count_lines")
    op.drop_table("stock_count_lines")
    op.drop_index("ix_stock_counts_created_at", table_name="stock_counts")
    op.drop_index("ix_stock_counts_created_by", table_name="stock_counts")
    op.drop_index("ix_stock_counts_status", table_name="stock_counts")
    op.drop_index("ix_stock_counts_warehouse_id", table_name="stock_counts")
    op.drop_table("stock_counts")
