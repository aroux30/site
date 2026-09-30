"""Add inventory reorder rules and product accessory cross-sell tables.

Revision ID: k3l4m5n6o7p8
Revises: i2j3k4l5m6n7
Create Date: 2026-09-24 12:30:00

Found by scanning Base.metadata against every ``op.create_table`` in the
migration graph: ``inventory_reorder_rules`` (min/max replenishment per
variant+warehouse) and ``product_accessories`` (directional cross-sell links)
existed as models but had no migration.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "k3l4m5n6o7p8"
down_revision = "i2j3k4l5m6n7"
branch_labels = None
depends_on = None

DEFAULT_WAREHOUSE_ID = "00000000-0000-0000-0000-000000000101"


def upgrade() -> None:
    op.create_table(
        "inventory_reorder_rules",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("variant_id", sa.UUID(), nullable=False),
        sa.Column(
            "warehouse_id",
            sa.UUID(),
            nullable=False,
            server_default=sa.text(f"'{DEFAULT_WAREHOUSE_ID}'::uuid"),
        ),
        sa.Column("min_quantity", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("reorder_to", sa.Integer(), nullable=False, server_default=sa.text("0")),
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
        sa.CheckConstraint("min_quantity >= 0", name="ck_reorder_min_non_negative"),
        sa.CheckConstraint("reorder_to >= 0", name="ck_reorder_to_non_negative"),
        sa.ForeignKeyConstraint(
            ["variant_id"],
            ["product_variants.id"],
            name=op.f("fk_inventory_reorder_rules_variant_id_product_variants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_inventory_reorder_rules")),
        sa.UniqueConstraint(
            "variant_id", "warehouse_id", name="uq_reorder_variant_warehouse"
        ),
    )
    op.create_index(
        "ix_reorder_rules_variant_id", "inventory_reorder_rules", ["variant_id"], unique=False
    )
    op.create_index(
        "ix_reorder_rules_warehouse_id",
        "inventory_reorder_rules",
        ["warehouse_id"],
        unique=False,
    )

    op.create_table(
        "product_accessories",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("product_id", sa.UUID(), nullable=False),
        sa.Column("accessory_id", sa.UUID(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default=sa.text("0")),
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
            ["product_id"],
            ["products.id"],
            name=op.f("fk_product_accessories_product_id_products"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["accessory_id"],
            ["products.id"],
            name=op.f("fk_product_accessories_accessory_id_products"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_product_accessories")),
        sa.UniqueConstraint("product_id", "accessory_id", name="uq_product_accessories_pair"),
    )
    op.create_index(
        "ix_product_accessories_product_id",
        "product_accessories",
        ["product_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_product_accessories_product_id", table_name="product_accessories")
    op.drop_table("product_accessories")
    op.drop_index("ix_reorder_rules_warehouse_id", table_name="inventory_reorder_rules")
    op.drop_index("ix_reorder_rules_variant_id", table_name="inventory_reorder_rules")
    op.drop_table("inventory_reorder_rules")
