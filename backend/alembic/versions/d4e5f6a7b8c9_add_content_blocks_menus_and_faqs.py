"""Add homepage blocks, site menus, and FAQ items (Karta Phase 7/9).

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-09-12 21:00:00

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. homepage_blocks table
    op.create_table(
        "homepage_blocks",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=150), nullable=False),
        sa.Column("block_type", sa.String(length=32), nullable=False),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_homepage_blocks")),
    )
    op.create_index("ix_homepage_blocks_is_active", "homepage_blocks", ["is_active"], unique=False)
    op.create_index("ix_homepage_blocks_position", "homepage_blocks", ["position"], unique=False)

    # 2. site_menus table
    op.create_table(
        "site_menus",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("location", sa.String(length=32), nullable=False, server_default="header_main"),
        sa.Column("title", sa.String(length=100), nullable=False),
        sa.Column("url", sa.String(length=500), nullable=False),
        sa.Column("parent_id", sa.UUID(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("icon", sa.String(length=50), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["parent_id"], ["site_menus.id"], name=op.f("fk_site_menus_parent_id_site_menus"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_site_menus")),
    )
    op.create_index("ix_site_menus_location", "site_menus", ["location"], unique=False)
    op.create_index("ix_site_menus_parent_id", "site_menus", ["parent_id"], unique=False)
    op.create_index("ix_site_menus_position", "site_menus", ["position"], unique=False)

    # 3. faq_items table
    op.create_table(
        "faq_items",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("question", sa.String(length=300), nullable=False),
        sa.Column("answer_html", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False, server_default="عمومی"),
        sa.Column("position", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_faq_items")),
    )
    op.create_index("ix_faq_items_category", "faq_items", ["category"], unique=False)
    op.create_index("ix_faq_items_is_active", "faq_items", ["is_active"], unique=False)
    op.create_index("ix_faq_items_position", "faq_items", ["position"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_faq_items_position", table_name="faq_items")
    op.drop_index("ix_faq_items_is_active", table_name="faq_items")
    op.drop_index("ix_faq_items_category", table_name="faq_items")
    op.drop_table("faq_items")
    op.drop_index("ix_site_menus_position", table_name="site_menus")
    op.drop_index("ix_site_menus_parent_id", table_name="site_menus")
    op.drop_index("ix_site_menus_location", table_name="site_menus")
    op.drop_table("site_menus")
    op.drop_index("ix_homepage_blocks_position", table_name="homepage_blocks")
    op.drop_index("ix_homepage_blocks_is_active", table_name="homepage_blocks")
    op.drop_table("homepage_blocks")
