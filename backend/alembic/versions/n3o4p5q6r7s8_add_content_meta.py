"""add content_meta (page custom fields)

Revision ID: n3o4p5q6r7s8
Revises: v2w3x4y5z6a7
Create Date: 2026-09-28

Pages had no custom-field store — the blog had ``blog_post_meta`` but pages
could not carry a key at all. This is a generic ``(resource_type,
resource_id, meta_key)`` table so pages, reusable blocks and any future
content type share one access path instead of each growing its own table.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "n3o4p5q6r7s8"
down_revision = "v2w3x4y5z6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "content_meta",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("resource_type", sa.String(length=50), nullable=False),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("meta_key", sa.String(length=255), nullable=False),
        sa.Column("meta_value", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "resource_type", "resource_id", "meta_key",
            name="uq_content_meta_resource_key",
        ),
    )
    op.create_index("ix_content_meta_resource", "content_meta", ["resource_type", "resource_id"])
    op.create_index("ix_content_meta_meta_key", "content_meta", ["meta_key"])


def downgrade() -> None:
    op.drop_index("ix_content_meta_meta_key", table_name="content_meta")
    op.drop_index("ix_content_meta_resource", table_name="content_meta")
    op.drop_table("content_meta")
