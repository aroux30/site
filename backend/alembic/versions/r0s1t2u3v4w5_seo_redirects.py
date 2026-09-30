"""SEO redirect rules table (CMS parity pass 1, batch 9).

Revision ID: r0s1t2u3v4w5
Revises: q9r0s1t2u3v4
Create Date: 2026-09-24 14:30:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "r0s1t2u3v4w5"
down_revision = "q9r0s1t2u3v4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "seo_redirects",
        sa.Column("from_path", sa.String(length=500), nullable=False),
        sa.Column("to_path", sa.String(length=500), nullable=False),
        sa.Column("status_code", sa.Integer(), server_default=sa.text("301"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("hit_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("from_path", name="uq_seo_redirects_from_path"),
    )
    op.create_index("ix_seo_redirects_is_active", "seo_redirects", ["is_active"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_seo_redirects_is_active", table_name="seo_redirects")
    op.drop_table("seo_redirects")
