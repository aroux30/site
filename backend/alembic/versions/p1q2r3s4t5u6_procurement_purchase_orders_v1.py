"""Procurement v1: suppliers, purchase orders, lines, sequences, PO-receipt links.

ERP benchmark gap analysis (feature #21 Purchase orders, P1):

- ``suppliers``: purchasing counterparties (deliberately separate from the
  marketplace ``vendors`` table — vendors require a user account and a
  storefront; suppliers only need contact info and payment terms).
- ``supplier_products``: preferred-supplier links per variant with the last
  negotiated integer-Rial unit price, feeding PO suggestions.
- ``purchase_orders``: draft -> sent -> partially_received -> received ->
  closed / cancelled lifecycle, integer-Rial totals, per-supplier-per-year
  numbering (PO-1404-0001), idempotency key.
- ``purchase_order_lines``: ordered vs. progressively received integer
  quantities (received never exceeds ordered), unit price + tax basis points.
- ``purchase_order_sequences``: gapless per (supplier, Jalali year) counter,
  locked FOR UPDATE at allocation (same protocol as invoice_sequences).
- ``purchase_order_receipts``: additive link to inventory ``Receipt`` rows so
  PO receiving reuses the existing blind-receipt machinery without touching
  the inventory tables.

Revision ID: p1q2r3s4t5u6
Revises: z8a9b0c1d2e3
Create Date: 2026-09-24 23:45:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "p1q2r3s4t5u6"
down_revision = "z8a9b0c1d2e3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "suppliers",
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("contact_info", postgresql.JSONB(), nullable=False),
        sa.Column("payment_terms_days", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
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
        sa.UniqueConstraint("code", name="uq_suppliers_code"),
    )
    op.create_index("ix_suppliers_is_active", "suppliers", ["is_active"])
    op.create_index("ix_suppliers_name", "suppliers", ["name"])

    op.create_table(
        "supplier_products",
        sa.Column(
            "supplier_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("suppliers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "variant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("product_variants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("supplier_sku", sa.String(length=100), nullable=True),
        sa.Column("last_unit_price_rial", sa.BigInteger(), nullable=False),
        sa.Column("is_preferred", sa.Boolean(), nullable=False),
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
        sa.UniqueConstraint("supplier_id", "variant_id", name="uq_supplier_products_pair"),
        sa.CheckConstraint(
            "last_unit_price_rial >= 0", name="ck_supplier_products_price_nonneg"
        ),
    )
    op.create_index("ix_supplier_products_variant_id", "supplier_products", ["variant_id"])

    op.create_table(
        "purchase_orders",
        sa.Column(
            "supplier_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("suppliers.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("number", sa.String(length=40), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "DRAFT",
                "SENT",
                "PARTIALLY_RECEIVED",
                "RECEIVED",
                "CLOSED",
                "CANCELLED",
                name="purchase_order_status_enum",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("warehouse_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("expected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("subtotal_rial", sa.BigInteger(), nullable=False),
        sa.Column("tax_rial", sa.BigInteger(), nullable=False),
        sa.Column("total_rial", sa.BigInteger(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=True),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
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
        sa.UniqueConstraint("number", name="uq_purchase_orders_number"),
        sa.UniqueConstraint("idempotency_key", name="uq_purchase_orders_idempotency_key"),
        sa.CheckConstraint("subtotal_rial >= 0", name="ck_po_subtotal_nonneg"),
        sa.CheckConstraint("tax_rial >= 0", name="ck_po_tax_nonneg"),
        sa.CheckConstraint("total_rial >= 0", name="ck_po_total_nonneg"),
    )
    op.create_index("ix_purchase_orders_supplier_id", "purchase_orders", ["supplier_id"])
    op.create_index("ix_purchase_orders_status", "purchase_orders", ["status"])
    op.create_index("ix_purchase_orders_created_at", "purchase_orders", ["created_at"])
    op.create_index(
        "ix_purchase_orders_idempotency_key", "purchase_orders", ["idempotency_key"]
    )

    op.create_table(
        "purchase_order_lines",
        sa.Column(
            "purchase_order_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("purchase_orders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "product_variant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("product_variants.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("qty_ordered", sa.Integer(), nullable=False),
        sa.Column("qty_received", sa.Integer(), nullable=False),
        sa.Column("unit_price_rial", sa.BigInteger(), nullable=False),
        sa.Column("tax_basis_points", sa.Integer(), nullable=False),
        sa.Column("note", sa.String(length=500), nullable=True),
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
        sa.CheckConstraint("qty_ordered > 0", name="ck_po_lines_qty_ordered_positive"),
        sa.CheckConstraint("qty_received >= 0", name="ck_po_lines_qty_received_nonneg"),
        sa.CheckConstraint(
            "qty_received <= qty_ordered", name="ck_po_lines_received_within_ordered"
        ),
        sa.CheckConstraint("unit_price_rial >= 0", name="ck_po_lines_unit_price_nonneg"),
        sa.CheckConstraint(
            "tax_basis_points >= 0 AND tax_basis_points <= 10000",
            name="ck_po_lines_tax_bps_range",
        ),
    )
    op.create_index(
        "ix_purchase_order_lines_po_id", "purchase_order_lines", ["purchase_order_id"]
    )
    op.create_index(
        "ix_purchase_order_lines_variant_id",
        "purchase_order_lines",
        ["product_variant_id"],
    )

    op.create_table(
        "purchase_order_sequences",
        sa.Column(
            "supplier_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("suppliers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("year", sa.String(length=8), nullable=False),
        sa.Column("last_value", sa.BigInteger(), nullable=False),
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
        sa.UniqueConstraint("supplier_id", "year", name="uq_po_sequences_supplier_year"),
    )

    op.create_table(
        "purchase_order_receipts",
        sa.Column(
            "purchase_order_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("purchase_orders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "receipt_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("inventory_receipts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
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
        sa.UniqueConstraint("receipt_id", name="uq_po_receipts_receipt"),
    )
    op.create_index(
        "ix_po_receipts_po_id", "purchase_order_receipts", ["purchase_order_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_po_receipts_po_id", table_name="purchase_order_receipts")
    op.drop_table("purchase_order_receipts")
    op.drop_table("purchase_order_sequences")
    op.drop_index("ix_purchase_order_lines_variant_id", table_name="purchase_order_lines")
    op.drop_index("ix_purchase_order_lines_po_id", table_name="purchase_order_lines")
    op.drop_table("purchase_order_lines")
    op.drop_index("ix_purchase_orders_idempotency_key", table_name="purchase_orders")
    op.drop_index("ix_purchase_orders_created_at", table_name="purchase_orders")
    op.drop_index("ix_purchase_orders_status", table_name="purchase_orders")
    op.drop_index("ix_purchase_orders_supplier_id", table_name="purchase_orders")
    op.drop_table("purchase_orders")
    op.drop_index("ix_supplier_products_variant_id", table_name="supplier_products")
    op.drop_table("supplier_products")
    op.drop_index("ix_suppliers_name", table_name="suppliers")
    op.drop_index("ix_suppliers_is_active", table_name="suppliers")
    op.drop_table("suppliers")
