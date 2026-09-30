"""Add digital cards, pricing tiers, and category custom fields (Karta Phase 1/2).

Revision ID: d5e8f2a1b9c3
Revises: c4d9e1a5f7b2
Create Date: 2026-09-12 18:00:00

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "d5e8f2a1b9c3"
down_revision = "c4d9e1a5f7b2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. digital_cards table
    op.create_table(
        "digital_cards",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("product_id", sa.UUID(), nullable=False),
        sa.Column("delivery_type", sa.String(length=32), nullable=False, server_default="unique"),
        sa.Column("serial_number", sa.String(length=128), nullable=True),
        sa.Column("pin_ciphertext", sa.Text(), nullable=False),
        sa.Column("card_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="available"),
        sa.Column("max_uses", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("used_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("assigned_order_id", sa.UUID(), nullable=True),
        sa.Column("file_path", sa.String(length=500), nullable=True),
        sa.Column("expire_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reading_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], name=op.f("fk_digital_cards_product_id_products"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["assigned_order_id"], ["orders.id"], name=op.f("fk_digital_cards_assigned_order_id_orders"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_digital_cards")),
        sa.UniqueConstraint("card_hash", name=op.f("uq_digital_cards_card_hash")),
    )
    op.create_index("ix_digital_cards_product_id", "digital_cards", ["product_id"], unique=False)
    op.create_index("ix_digital_cards_status", "digital_cards", ["status"], unique=False)
    op.create_index("ix_digital_cards_card_hash", "digital_cards", ["card_hash"], unique=False)
    op.create_index("ix_digital_cards_order_id", "digital_cards", ["assigned_order_id"], unique=False)
    op.create_index("ix_digital_cards_product_status", "digital_cards", ["product_id", "status"], unique=False)

    # 2. price_tiers table
    op.create_table(
        "price_tiers",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("product_id", sa.UUID(), nullable=False),
        sa.Column("from_qty", sa.Integer(), nullable=False),
        sa.Column("to_qty", sa.Integer(), nullable=True),
        sa.Column("unit_price", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], name=op.f("fk_price_tiers_product_id_products"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_price_tiers")),
    )
    op.create_index("ix_price_tiers_product_id", "price_tiers", ["product_id"], unique=False)

    # 3. category_custom_fields table
    op.create_table(
        "category_custom_fields",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("category_id", sa.UUID(), nullable=False),
        sa.Column("field_key", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=200), nullable=False),
        sa.Column("field_type", sa.String(length=32), nullable=False, server_default="text"),
        sa.Column("is_required", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], name=op.f("fk_category_custom_fields_category_id_categories"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_category_custom_fields")),
    )
    op.create_index("ix_category_custom_fields_category_id", "category_custom_fields", ["category_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_category_custom_fields_category_id", table_name="category_custom_fields")
    op.drop_table("category_custom_fields")
    op.drop_index("ix_price_tiers_product_id", table_name="price_tiers")
    op.drop_table("price_tiers")
    op.drop_index("ix_digital_cards_product_status", table_name="digital_cards")
    op.drop_index("ix_digital_cards_order_id", table_name="digital_cards")
    op.drop_index("ix_digital_cards_card_hash", table_name="digital_cards")
    op.drop_index("ix_digital_cards_status", table_name="digital_cards")
    op.drop_index("ix_digital_cards_product_id", table_name="digital_cards")
    op.drop_table("digital_cards")
