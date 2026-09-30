"""Content entry lifecycle: revisions + scheduling + trash (pass 2 hardening).

Revision ID: s1t2u3v4w5x6
Revises: r0s1t2u3v4w5
Create Date: 2026-09-24 15:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "s1t2u3v4w5x6"
down_revision = "r0s1t2u3v4w5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "cms_content_entries",
        sa.Column("revision_number", sa.Integer(), server_default=sa.text("1"), nullable=False),
    )
    op.add_column(
        "cms_content_entries",
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "cms_content_entries",
        sa.Column("scheduled_publish_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "cms_content_entries",
        sa.Column("scheduled_unpublish_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "cms_content_entries",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_cms_content_entries_deleted_at", "cms_content_entries", ["deleted_at"], unique=False
    )

    op.create_table(
        "cms_content_entry_revisions",
        sa.Column("entry_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["entry_id"], ["cms_content_entries.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("entry_id", "revision_number", name="uq_entry_revisions_entry_rev"),
    )
    op.create_index(
        "ix_entry_revisions_entry_id", "cms_content_entry_revisions", ["entry_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_entry_revisions_entry_id", table_name="cms_content_entry_revisions")
    op.drop_table("cms_content_entry_revisions")
    op.drop_index("ix_cms_content_entries_deleted_at", table_name="cms_content_entries")
    op.drop_column("cms_content_entries", "deleted_at")
    op.drop_column("cms_content_entries", "scheduled_unpublish_at")
    op.drop_column("cms_content_entries", "scheduled_publish_at")
    op.drop_column("cms_content_entries", "published_at")
    op.drop_column("cms_content_entries", "revision_number")
