"""Add warehouse_id to inventory tables (multi-warehouse support).

Revision ID: b3c4d5e6f7a8
Revises: f8a2b4c6d9e1
Create Date: 2026-09-23 04:07:00

Multi-warehouse (ERPNext/OFBiz pattern): every inventory row belongs to a
warehouse. Existing rows are assigned the default central warehouse via
``server_default`` so the migration is non-destructive; the composite unique
index (variant_id, warehouse_id) replaces the old single-column unique on
variant_id, which forbade the same variant from existing in two warehouses.

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "b3c4d5e6f7a8"
down_revision = "f8a2b4c6d9e1"
branch_labels = None
depends_on = None

# Central Tehran warehouse — the destination of every pre-existing row.
DEFAULT_WAREHOUSE_ID = "00000000-0000-0000-0000-000000000101"

_TABLES = ("inventory_items", "inventory_reservations", "inventory_transactions")


def upgrade() -> None:
    for table in _TABLES:
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

    # The old constraint forbade a variant from having stock in two warehouses.
    op.drop_constraint(
        "uq_inventory_items_variant_id",
        "inventory_items",
        type_="unique",
    )
    op.create_index(
        "ix_inventory_items_variant_warehouse",
        "inventory_items",
        ["variant_id", "warehouse_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_inventory_items_variant_warehouse", table_name="inventory_items")
    op.create_unique_constraint(
        "uq_inventory_items_variant_id",
        "inventory_items",
        ["variant_id"],
    )

    for table in _TABLES:
        op.drop_index(f"ix_{table}_warehouse_id", table_name=table)
        op.drop_column(table, "warehouse_id")
