"""Remove the warehouse catalogue and warehouse dimension (rmwarehouse1).

Owner order 2026-10-09: the store sells subscriptions, redeem codes and
vouchers — purely digital goods — so the physical-warehouse feature (and the
multi-warehouse dimension it carried) is removed completely. The admin
«انبارها» page, its eight endpoints, its service and this catalogue table were
a leftover from the ERP-parity build; the ledger only ever used the single
sentinel warehouse anyway (verified live: 1 distinct ``warehouse_id`` across
all 1,369 / 1,253 / 2,201 ledger rows).

This migration removes the schema half:

- drops the ``warehouses`` table (1 row: the sentinel) and its three indexes;
- drops ``warehouse_id`` from ``inventory_items``,
  ``inventory_reservations`` and ``inventory_transactions``;
- drops ``warehouse_id`` and its unique constraint + index from
  ``inventory_reorder_rules``, replacing ``uq_reorder_variant_warehouse``
  with a single-column ``uq_reorder_variant``;
- restores the pre-multi-warehouse single-column unique
  ``uq_inventory_items_variant_id`` on ``inventory_items``.

Data safety: every ledger row sits in the sentinel warehouse (verified), so
dropping the column loses no information — the variant rows survive intact.
The downgrade recreates the table, columns, indexes and constraint names
exactly as ``wa1r2e3h4o5u6`` / ``b3c4d5e6f7a8`` / ``k3l4m5n6o7p8`` defined
them, including the sentinel row.

Revision ID: rmwarehouse1
Revises: seom1
Create Date: 2026-10-09
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "rmwarehouse1"
down_revision = "seom1"
branch_labels = None
depends_on = None

DEFAULT_WAREHOUSE_ID = "00000000-0000-0000-0000-000000000101"
DEFAULT_WAREHOUSE_NAME = "انبار مرکزی"
DEFAULT_WAREHOUSE_CODE = "CENTRAL"

_LEDGER_TABLES = (
    "inventory_items",
    "inventory_reservations",
    "inventory_transactions",
)


def upgrade() -> None:
    # 1. Reorder rules: composite unique → variant-only unique.
    op.drop_constraint(
        "uq_reorder_variant_warehouse",
        "inventory_reorder_rules",
        type_="unique",
    )
    op.drop_index("ix_reorder_rules_warehouse_id", table_name="inventory_reorder_rules")
    op.drop_column("inventory_reorder_rules", "warehouse_id")
    op.create_unique_constraint(
        "uq_reorder_variant",
        "inventory_reorder_rules",
        ["variant_id"],
    )

    # 2. inventory_items: restore the pre-multi-warehouse unique constraint,
    #    drop the composite index + warehouse column.
    op.drop_index("ix_inventory_items_variant_warehouse", table_name="inventory_items")
    op.drop_index("ix_inventory_items_warehouse_id", table_name="inventory_items")
    op.drop_column("inventory_items", "warehouse_id")
    op.create_unique_constraint(
        "uq_inventory_items_variant_id",
        "inventory_items",
        ["variant_id"],
    )

    # 3. Reservations + transactions: drop index + column.
    for table in ("inventory_reservations", "inventory_transactions"):
        op.drop_index(f"ix_{table}_warehouse_id", table_name=table)
        op.drop_column(table, "warehouse_id")

    # 4. The catalogue itself.
    op.drop_index("uq_warehouses_single_default", table_name="warehouses")
    op.drop_index("ix_warehouses_is_active", table_name="warehouses")
    op.drop_table("warehouses")


def downgrade() -> None:
    # 1. Recreate the catalogue exactly as wa1r2e3h4o5u6 defined it.
    op.create_table(
        "warehouses",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
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
        sa.CheckConstraint("length(trim(name)) > 0", name="ck_warehouses_name_not_blank"),
        sa.CheckConstraint("length(trim(code)) > 0", name="ck_warehouses_code_not_blank"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_warehouses")),
        sa.UniqueConstraint("code", name="uq_warehouses_code"),
    )
    op.create_index("ix_warehouses_is_active", "warehouses", ["is_active"], unique=False)
    op.create_index(
        "uq_warehouses_single_default",
        "warehouses",
        ["is_default"],
        unique=True,
        postgresql_where=sa.text("is_default"),
    )
    op.execute(
        sa.text(
            """
            INSERT INTO warehouses (id, name, code, address, is_default, is_active,
                                    created_at, updated_at)
            SELECT CAST(:warehouse_id AS uuid), :name, :code, NULL,
                   NOT EXISTS (SELECT 1 FROM warehouses WHERE is_default),
                   true, now(), now()
            WHERE NOT EXISTS (
                SELECT 1 FROM warehouses WHERE id = CAST(:warehouse_id AS uuid)
            )
            """
        ).bindparams(
            warehouse_id=DEFAULT_WAREHOUSE_ID,
            name=DEFAULT_WAREHOUSE_NAME,
            code=DEFAULT_WAREHOUSE_CODE,
        )
    )

    # 2. inventory_items: composite unique + warehouse column.
    op.drop_constraint(
        "uq_inventory_items_variant_id",
        "inventory_items",
        type_="unique",
    )
    op.add_column(
        "inventory_items",
        sa.Column(
            "warehouse_id",
            sa.UUID(),
            nullable=False,
            server_default=DEFAULT_WAREHOUSE_ID,
        ),
    )
    op.create_index(
        "ix_inventory_items_warehouse_id",
        "inventory_items",
        ["warehouse_id"],
        unique=False,
    )
    op.create_index(
        "ix_inventory_items_variant_warehouse",
        "inventory_items",
        ["variant_id", "warehouse_id"],
        unique=True,
    )

    # 3. Reservations + transactions: column + index.
    for table in ("inventory_reservations", "inventory_transactions"):
        op.add_column(
            table,
            sa.Column(
                "warehouse_id",
                sa.UUID(),
                nullable=False,
                server_default=DEFAULT_WAREHOUSE_ID,
            ),
        )
        op.create_index(
            f"ix_{table}_warehouse_id",
            table,
            ["warehouse_id"],
            unique=False,
        )

    # 4. Reorder rules: drop variant-only unique, restore composite.
    op.drop_constraint(
        "uq_reorder_variant",
        "inventory_reorder_rules",
        type_="unique",
    )
    op.add_column(
        "inventory_reorder_rules",
        sa.Column(
            "warehouse_id",
            sa.UUID(),
            nullable=False,
            server_default=sa.text(f"'{DEFAULT_WAREHOUSE_ID}'::uuid"),
        ),
    )
    op.create_index(
        "ix_reorder_rules_warehouse_id",
        "inventory_reorder_rules",
        ["warehouse_id"],
        unique=False,
    )
    op.create_unique_constraint(
        "uq_reorder_variant_warehouse",
        "inventory_reorder_rules",
        ["variant_id", "warehouse_id"],
    )
