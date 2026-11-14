"""add builder_data to cms_pages and cms_page_revisions, add page_templates table (Phase P0).

Visual Page Builder core schema:
- Adds JSONB column `builder_data` to `cms_pages` and `cms_page_revisions`.
- Adds `page_templates` table for reusable section and page designs.

Revision ID: pagebld1
Revises: rmpass1
Create Date: 2026-11-14
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "pagebld1"
down_revision: str | None = "rmpass1"

branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add builder_data to cms_pages
    op.add_column(
        "cms_pages",
        sa.Column("builder_data", JSONB, nullable=True),
    )

    # 2. Add builder_data to cms_page_revisions
    op.add_column(
        "cms_page_revisions",
        sa.Column("builder_data", JSONB, nullable=True),
    )

    # 3. Create page_templates table
    op.create_table(
        "page_templates",
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
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=220), nullable=False),
        sa.Column("template_type", sa.String(length=50), nullable=False),
        sa.Column("builder_data", JSONB, nullable=False),
        sa.Column("thumbnail_url", sa.String(length=500), nullable=True),
        sa.Column(
            "author_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.UniqueConstraint("slug", name="uq_page_templates_slug"),
    )

    # 4. Create indices for page_templates
    op.create_index(
        "ix_page_templates_template_type",
        "page_templates",
        ["template_type"],
    )
    op.create_index(
        "ix_page_templates_created_at",
        "page_templates",
        ["created_at"],
    )
    op.create_index(
        "ix_page_templates_slug",
        "page_templates",
        ["slug"],
    )


def downgrade() -> None:
    # Drop indices and page_templates table
    op.drop_index("ix_page_templates_slug", table_name="page_templates")
    op.drop_index("ix_page_templates_created_at", table_name="page_templates")
    op.drop_index("ix_page_templates_template_type", table_name="page_templates")
    op.drop_table("page_templates")

    # Drop builder_data columns
    op.drop_column("cms_page_revisions", "builder_data")
    op.drop_column("cms_pages", "builder_data")
