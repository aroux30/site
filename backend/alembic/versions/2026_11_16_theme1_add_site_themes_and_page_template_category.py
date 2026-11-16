"""add site_themes and theme_revisions, add category to page_templates (Phase P2.0).

Revision ID: themetok1
Revises: pagebld1
Create Date: 2026-11-16
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "theme1"
down_revision: str | None = "pagebld1"

branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Create site_themes table
    op.create_table(
        "site_themes",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
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
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("slug", sa.String(length=180), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("tokens", JSONB, nullable=False),
        sa.Column(
            "author_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.UniqueConstraint("slug", name="uq_site_themes_slug"),
    )

    op.create_index("ix_site_themes_is_active", "site_themes", ["is_active"])
    op.create_index("ix_site_themes_slug", "site_themes", ["slug"])
    op.create_index(
        "uq_site_themes_is_active",
        "site_themes",
        ["is_active"],
        unique=True,
        postgresql_where=sa.text("is_active = true"),
    )

    # 2. Create theme_revisions table
    op.create_table(
        "theme_revisions",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
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
        sa.Column(
            "theme_id",
            UUID(as_uuid=True),
            sa.ForeignKey("site_themes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("tokens", JSONB, nullable=False),
        sa.Column(
            "created_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.UniqueConstraint("theme_id", "revision_number", name="uq_theme_revisions_theme_rev"),
    )

    op.create_index("ix_theme_revisions_theme_id", "theme_revisions", ["theme_id"])

    # 3. Add category column to page_templates table
    op.add_column(
        "page_templates",
        sa.Column("category", sa.String(length=100), nullable=True),
    )
    op.create_index("ix_page_templates_category", "page_templates", ["category"])


def downgrade() -> None:
    # 3. Drop category index and column from page_templates
    op.drop_index("ix_page_templates_category", table_name="page_templates")
    op.drop_column("page_templates", "category")

    # 2. Drop theme_revisions table and indices
    op.drop_index("ix_theme_revisions_theme_id", table_name="theme_revisions")
    op.drop_table("theme_revisions")

    # 1. Drop site_themes table and indices
    op.drop_index("uq_site_themes_is_active", table_name="site_themes")
    op.drop_index("ix_site_themes_slug", table_name="site_themes")
    op.drop_index("ix_site_themes_is_active", table_name="site_themes")
    op.drop_table("site_themes")
