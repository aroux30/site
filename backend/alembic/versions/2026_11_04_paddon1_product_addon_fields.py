"""Product add-on fields — WooCommerce Product Add-ons parity.

Revision ID: paddon1
Revises: invthr1
Create Date: 2026-11-04

Additive-only: one new table (``product_addon_fields``) for per-product
buyer-input fields (WooCommerce Product Add-ons). No existing table or
column is touched. Prices are integer Rials like the rest of the catalog.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "paddon1"
down_revision = "invthr1"
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
    op.create_table(
        "product_addon_fields",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "product_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("field_key", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=200), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column(
            "field_type",
            sa.String(length=32),
            server_default=sa.text("'custom_text'::character varying"),
            nullable=False,
        ),
        sa.Column("display", sa.String(length=20), nullable=True),
        sa.Column("options_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "is_required", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("min_val", sa.Integer(), nullable=True),
        sa.Column("max_val", sa.Integer(), nullable=True),
        sa.Column("price", sa.BigInteger(), nullable=True),
        sa.Column("price_type", sa.String(length=20), nullable=True),
        sa.Column(
            "position", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_product_addon_fields_product_id",
        "product_addon_fields",
        ["product_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_product_addon_fields_product_id", table_name="product_addon_fields")
    op.drop_table("product_addon_fields")
