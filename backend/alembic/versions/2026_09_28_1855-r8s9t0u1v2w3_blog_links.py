"""Blog links (wp_links) with OPML import/export

Revision ID: r8s9t0u1v2w3
Revises: q7r8s9t0u1v2
Create Date: 2026-09-28 18:55:00.000000+03:30

OPML is the interchange format for a reader's subscriptions. WordPress treats
a link as a first-class post type, so a site that exports OPML is expected to
round-trip links, not just posts and categories — without this table an OPML
export silently drops every curated link the operator had set up.

``category`` maps to an OPML outline group, which readers render as a folder.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "r8s9t0u1v2w3"
down_revision: str = "q7r8s9t0u1v2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "blog_links",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("url", sa.String(length=2000), nullable=False),
        sa.Column("slug", sa.String(length=320), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(length=200), nullable=True),
        sa.Column("position", sa.Integer(), server_default="0", nullable=False),
        sa.Column("is_visible", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("link_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("clicks", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name="fk_blog_links_created_by", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_blog_links"),
    )
    op.create_index("ix_blog_links_slug", "blog_links", ["slug"], unique=True)
    op.create_index("ix_blog_links_visible", "blog_links", ["is_visible"])
    op.create_index("ix_blog_links_position", "blog_links", ["position"])
    op.create_index("ix_blog_links_category", "blog_links", ["category"])


def downgrade() -> None:
    op.drop_index("ix_blog_links_category", table_name="blog_links")
    op.drop_index("ix_blog_links_position", table_name="blog_links")
    op.drop_index("ix_blog_links_visible", table_name="blog_links")
    op.drop_index("ix_blog_links_slug", table_name="blog_links")
    op.drop_table("blog_links")
