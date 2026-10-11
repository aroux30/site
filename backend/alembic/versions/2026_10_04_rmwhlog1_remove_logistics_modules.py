"""Remove the logistics modules: transfers, stock counts, receipts, and procurement.

The owner asked for all five logistics screens to be deleted outright — none
has a use in a retail storefront («هیچ اثری نمیخواهم ازشون»). The code is
archived under ``_archived/logistics-modules-2026-10-04/`` and this migration
drops their tables.

Removed:
- ``stock_counts`` / ``stock_count_lines`` — physical cycle-count sessions.
- ``warehouse_transfers`` / ``warehouse_transfer_lines`` — two-step movements.
- ``inventory_receipts`` / ``inventory_receipt_lines`` — blind receiving.
- ``suppliers`` / ``supplier_products`` — procurement master data.
- ``purchase_orders`` / ``purchase_order_lines`` /
  ``purchase_order_receipts`` / ``purchase_order_sequences`` — procurement.

Deliberately kept (live storefront features):
- ``warehouses`` + the ledger's ``DEFAULT_WAREHOUSE_ID`` sentinel —
  ``inventory_items.warehouse_id`` points at it and stock math depends on it.
- ``inventory_items`` / ``inventory_reservations`` / ``inventory_transactions``
  — the ledger the storefront sells from.

Verified at removal time (live probe 2026-10-04): every one of the twelve
tables held 0 rows. The three permission rows leave with the features they
guarded (``role_permissions`` cascades on ``permission_id``).

``downgrade()`` recreates the twelve tables with the same columns, indexes,
checks and foreign keys the creation migrations (``y7z8a9b0c1d2`` for the
physical operations, ``p1q2r3s4t5u6`` for procurement) defined, and
re-inserts the three permission rows with their observed ids, so the schema
change is reversible.

Revision ID: rmwhlog1
Revises: rmplugins1
Create Date: 2026-10-04
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "rmwhlog1"
down_revision = "rmplugins1"
branch_labels = None
depends_on = None

#: The permission rows as they existed at removal (verified against the live
#: database before dropping). The ids are pinned so a downgrade restores the
#: exact rows the removed code referenced.
_PERMISSIONS = (
    {
        "id": "10ef33a9-56ac-4c75-87da-a11808cb03f9",
        "slug": "inventory:counts",
        "resource": "inventory",
        "action": "counts",
        "name": "شمارش انبار",
        "description": "انجام عملیات شمارش فیزیکی موجودی، ثبت شمارش و تطبیق اختلاف‌ها",
    },
    {
        "id": "105690ea-be1b-46ce-a966-acffe879bdc2",
        "slug": "procurement:read",
        "resource": "procurement",
        "action": "read",
        "name": "مشاهده تدارکات",
        "description": "مشاهده سفارش‌های خرید، تامین‌کنندگان و درخواست‌های تدارکات",
    },
    {
        "id": "275a3412-181b-47f8-92fa-76738d469a67",
        "slug": "procurement:write",
        "resource": "procurement",
        "action": "write",
        "name": "مدیریت تدارکات",
        "description": "ایجاد و ویرایش سفارش‌های خرید و درخواست‌های تدارکات از تامین‌کنندگان",
    },
)


def upgrade() -> None:
    # Children before parents, deepest first. purchase_order_receipts holds
    # FKs into both purchase_orders and inventory_receipts.
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

    # The permission rows leave with the features they guarded.
    # role_permissions has ON DELETE CASCADE on permission_id, so the admin
    # grants go with them.
    op.execute(
        sa.text(
            "DELETE FROM permissions WHERE slug IN ('inventory:counts',"
            " 'procurement:read', 'procurement:write')"
        )
    )


def downgrade() -> None:
    """Recreate the twelve tables as ``y7z8a9b0c1d2`` / ``p1q2r3s4t5u6`` defined them."""
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
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
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
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
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
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
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
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
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
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
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
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
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

    # ── procurement (p1q2r3s4t5u6) ─────────────────────────────────────────
    op.create_table(
        "suppliers",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column(
            "contact_info", postgresql.JSONB(astext_type=sa.Text()), nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("payment_terms_days", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_suppliers_code"),
    )
    op.create_index("ix_suppliers_is_active", "suppliers", ["is_active"])
    op.create_index("ix_suppliers_name", "suppliers", ["name"])

    op.create_table(
        "supplier_products",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
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
        sa.Column("last_unit_price_rial", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("is_preferred", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
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
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "supplier_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("suppliers.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("number", sa.String(length=40), nullable=True),
        sa.Column("status", sa.String(length=18), nullable=False),
        sa.Column("warehouse_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("expected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("subtotal_rial", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("tax_rial", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("total_rial", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("idempotency_key", sa.String(length=255), nullable=True),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
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
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
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
        sa.Column("qty_received", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unit_price_rial", sa.BigInteger(), nullable=False),
        sa.Column("tax_basis_points", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("note", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
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
        "ix_purchase_order_lines_variant_id", "purchase_order_lines", ["product_variant_id"]
    )

    op.create_table(
        "purchase_order_sequences",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "supplier_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("suppliers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("year", sa.String(length=8), nullable=False),
        sa.Column("last_value", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("supplier_id", "year", name="uq_po_sequences_supplier_year"),
    )

    op.create_table(
        "purchase_order_receipts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
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
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("receipt_id", name="uq_po_receipts_receipt"),
    )
    op.create_index(
        "ix_po_receipts_po_id", "purchase_order_receipts", ["purchase_order_id"]
    )

    # ── the permission rows and their admin grants ─────────────────────────
    for perm in _PERMISSIONS:
        op.execute(
            sa.text(
                "INSERT INTO permissions (id, slug, resource, action, name, description,"
                " created_at, updated_at)"
                " VALUES (CAST(:id AS uuid), :slug, :resource, :action, :name, :description,"
                " now(), now())"
                " ON CONFLICT (slug) DO NOTHING"
            ).bindparams(**perm)
        )
        # Re-grant to the seeded admin role, matching permission_seed.py's
        # blanket grant to ADMIN_ROLE_SLUG. A missing role (a database that
        # never seeded) is fine: the row is granted by the next startup seed.
        op.execute(
            sa.text(
                "INSERT INTO role_permissions (id, role_id, permission_id, created_at, updated_at)"
                " SELECT gen_random_uuid(), r.id, p.id, now(), now()"
                " FROM roles r, permissions p"
                " WHERE r.slug = 'admin' AND p.slug = :slug"
                " ON CONFLICT DO NOTHING"
            ).bindparams(slug=perm["slug"])
        )
