"""Add blog tags, post-tag links, and post revisions tables.

Revision ID: j2k3l4m5n6p7
Revises: h1i2j3k4l5m6
Create Date: 2026-09-24 11:00:00

The blog module gained ``BlogTag`` / ``BlogPostTag`` / ``BlogPostRevision``
models (flat taxonomy + draft/publish snapshots, mirroring the CMS pages
workflow). Their tables were missing from the migration graph.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "j2k3l4m5n6p7"
down_revision = "h1i2j3k4l5m6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "blog_tags",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_blog_tags")),
        sa.UniqueConstraint("slug", name=op.f("uq_blog_tags_slug")),
    )
    op.create_index("ix_blog_tags_slug", "blog_tags", ["slug"], unique=False)

    op.create_table(
        "blog_post_tags",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("post_id", sa.UUID(), nullable=False),
        sa.Column("tag_id", sa.UUID(), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["post_id"],
            ["blog_posts.id"],
            name=op.f("fk_blog_post_tags_post_id_blog_posts"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tag_id"],
            ["blog_tags.id"],
            name=op.f("fk_blog_post_tags_tag_id_blog_tags"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_blog_post_tags")),
        sa.UniqueConstraint("post_id", "tag_id", name="uq_blog_post_tags_post_tag"),
    )

    op.create_table(
        "blog_post_revisions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("post_id", sa.UUID(), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("slug", sa.String(length=550), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("excerpt", sa.String(length=1000), nullable=True),
        sa.Column("cover_image_url", sa.String(length=500), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["post_id"],
            ["blog_posts.id"],
            name=op.f("fk_blog_post_revisions_post_id_blog_posts"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_blog_post_revisions_created_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_blog_post_revisions")),
        sa.UniqueConstraint("post_id", "revision_number", name="uq_blog_post_revisions_post_rev"),
    )
    op.create_index(
        "ix_blog_post_revisions_post_id",
        "blog_post_revisions",
        ["post_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_blog_post_revisions_post_id", table_name="blog_post_revisions")
    op.drop_table("blog_post_revisions")
    op.drop_table("blog_post_tags")
    op.drop_index("ix_blog_tags_slug", table_name="blog_tags")
    op.drop_table("blog_tags")
