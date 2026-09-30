"""Dynamic content-type builder tables (CMS parity pass 1, batch 8).

Revision ID: q9r0s1t2u3v4
Revises: p8q9r0s1t2u3
Create Date: 2026-09-24 14:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "q9r0s1t2u3v4"
down_revision = "p8q9r0s1t2u3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cms_content_types",
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("kind", sa.String(length=32), server_default=sa.text("'collection'::character varying"), nullable=False),
        sa.Column("fields", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_table(
        "cms_content_entries",
        sa.Column("content_type_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=32), server_default=sa.text("'draft'::character varying"), nullable=False),
        sa.Column("locale", sa.String(length=10), server_default=sa.text("'fa'::character varying"), nullable=False),
        sa.Column("position", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["content_type_id"], ["cms_content_types.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_cms_content_entries_type_status",
        "cms_content_entries",
        ["content_type_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_cms_content_entries_locale", "cms_content_entries", ["locale"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_cms_content_entries_locale", table_name="cms_content_entries")
    op.drop_index("ix_cms_content_entries_type_status", table_name="cms_content_entries")
    op.drop_table("cms_content_entries")
    op.drop_table("cms_content_types")
