"""Add price lists and price list rules (Phase 3 — Odoo product.pricelist).

Multi-level B2B pricing: a price list groups rules for one customer segment
(retail / gold / wholesale / b2b); a rule overrides a product or variant price
by a fixed Rial amount or a percentage in basis points (integer money only,
matching ADR-012).

Revision ID: l4m5n6o7p8q9
Revises: k3l4m5n6o7p8
Create Date: 2026-09-24
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision = "l4m5n6o7p8q9"
down_revision = "k3l4m5n6o7p8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "price_lists",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column(
            "segment",
            sa.Enum("RETAIL", "GOLD", "WHOLESALE", "B2B", name="customer_segment_enum", native_enum=False),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_price_lists_segment", "price_lists", ["segment"], unique=False)
    op.create_index("ix_price_lists_is_active", "price_lists", ["is_active"], unique=False)

    op.create_table(
        "price_list_rules",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "price_list_id",
            UUID(as_uuid=True),
            sa.ForeignKey("price_lists.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "product_id",
            UUID(as_uuid=True),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "variant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("product_variants.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("min_quantity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fixed_price_rial", sa.BigInteger(), nullable=True),
        sa.Column("discount_bp", sa.Integer(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("min_quantity >= 0", name="ck_plr_min_qty_non_negative"),
        sa.CheckConstraint(
            "discount_bp >= 0 AND discount_bp <= 10000", name="ck_plr_discount_bp_range"
        ),
        sa.CheckConstraint(
            "fixed_price_rial IS NULL OR fixed_price_rial >= 0",
            name="ck_plr_fixed_price_non_negative",
        ),
    )
    op.create_index("ix_price_list_rules_price_list_id", "price_list_rules", ["price_list_id"], unique=False)
    op.create_index("ix_price_list_rules_product_id", "price_list_rules", ["product_id"], unique=False)
    op.create_index("ix_price_list_rules_variant_id", "price_list_rules", ["variant_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_price_list_rules_variant_id", table_name="price_list_rules")
    op.drop_index("ix_price_list_rules_product_id", table_name="price_list_rules")
    op.drop_index("ix_price_list_rules_price_list_id", table_name="price_list_rules")
    op.drop_table("price_list_rules")
    op.drop_index("ix_price_lists_is_active", table_name="price_lists")
    op.drop_index("ix_price_lists_segment", table_name="price_lists")
    op.drop_table("price_lists")
