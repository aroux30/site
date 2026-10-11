"""Remove dynamic content types and custom post types (rmcpt1).

Owner order 2026-10-09: the store is an e-commerce platform, not a news or
publishing CMS. Standard blog posts, categories, tags, and fixed CMS pages
suffice; dynamic content-type builders ("سازنده تایپ محتوا" and custom post
types) have no use for a digital/goods store.

This migration drops all six custom content-type tables:
1. custom_post_entry_revisions (WP-parity custom post entry revisions)
2. custom_post_entries (WP-parity custom post entries)
3. custom_post_types (WP-parity custom post types)
4. cms_content_entry_revisions (Strapi-parity CMS content entry revisions)
5. cms_content_entries (Strapi-parity CMS content entries)
6. cms_content_types (Strapi-parity CMS content types)

Data safety: Pre-drop rows were captured in
_archived/content-types-removal-2026-10-09/db_snapshot_before.json.
The downgrade is 100% reversible and recreates all six tables, foreign keys,
constraints, server defaults, and indexes.

Revision ID: rmcpt1
Revises: seom3
Create Date: 2026-10-09
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "rmcpt1"
down_revision = "seom3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Drop blog custom post type tables in reverse FK order
    op.drop_table("custom_post_entry_revisions")
    op.drop_table("custom_post_entries")
    op.drop_table("custom_post_types")

    # 2. Drop CMS dynamic content type tables in reverse FK order
    op.drop_table("cms_content_entry_revisions")
    op.drop_table("cms_content_entries")
    op.drop_table("cms_content_types")


def downgrade() -> None:
    # 1. Recreate CMS content types
    op.create_table(
        "cms_content_types",
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column(
            "kind",
            sa.String(length=32),
            server_default=sa.text("'COLLECTION'::character varying"),
            nullable=False,
        ),
        sa.Column(
            "fields",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'"),
            nullable=False,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )

    # 2. Recreate CMS content entries
    op.create_table(
        "cms_content_entries",
        sa.Column("content_type_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            server_default=sa.text("'DRAFT'::character varying"),
            nullable=False,
        ),
        sa.Column(
            "position",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "revision_number",
            sa.Integer(),
            server_default=sa.text("1"),
            nullable=False,
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scheduled_publish_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scheduled_unpublish_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
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
            ["content_type_id"], ["cms_content_types.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_cms_content_entries_type_status",
        "cms_content_entries",
        ["content_type_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_cms_content_entries_deleted_at",
        "cms_content_entries",
        ["deleted_at"],
        unique=False,
    )

    # 3. Recreate CMS content entry revisions
    op.create_table(
        "cms_content_entry_revisions",
        sa.Column("entry_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
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
            ["entry_id"], ["cms_content_entries.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "entry_id", "revision_number", name="uq_entry_revisions_entry_rev"
        ),
    )
    op.create_index(
        "ix_entry_revisions_entry_id",
        "cms_content_entry_revisions",
        ["entry_id"],
        unique=False,
    )

    # 4. Recreate custom post types
    op.create_table(
        "custom_post_types",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=220), unique=True, nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("icon", sa.String(length=50), nullable=True),
        sa.Column("field_schema", postgresql.JSONB(), nullable=True),
        sa.Column(
            "supports_categories",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "supports_comments",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
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
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_custom_post_types_slug", "custom_post_types", ["slug"])

    # 5. Recreate custom post entries
    op.create_table(
        "custom_post_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("post_type_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("slug", sa.String(length=550), nullable=False),
        sa.Column("fields", postgresql.JSONB(), nullable=True),
        sa.Column("excerpt", sa.String(length=1000), nullable=True),
        sa.Column("cover_image_url", sa.String(length=500), nullable=True),
        sa.Column(
            "status",
            sa.String(length=32),
            server_default=sa.text("'DRAFT'::character varying"),
            nullable=False,
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scheduled_publish_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "revision_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("author_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "position",
            sa.Integer(),
            server_default=sa.text("0"),
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
        sa.ForeignKeyConstraint(
            ["post_type_id"], ["custom_post_types.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "post_type_id", "slug", name="uq_custom_post_entries_type_slug"
        ),
    )
    op.create_index(
        "ix_custom_post_entries_post_type_id",
        "custom_post_entries",
        ["post_type_id"],
    )
    op.create_index("ix_custom_post_entries_slug", "custom_post_entries", ["slug"])
    op.create_index(
        "ix_custom_post_entries_status", "custom_post_entries", ["status"]
    )
    op.create_index(
        "ix_custom_post_entries_published_at",
        "custom_post_entries",
        ["published_at"],
    )

    # 6. Recreate custom post entry revisions
    op.create_table(
        "custom_post_entry_revisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "entry_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("custom_post_entries.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("fields", postgresql.JSONB(), nullable=True),
        sa.Column("title", sa.String(length=500), nullable=True),
        sa.Column("excerpt", sa.String(length=1000), nullable=True),
        sa.Column(
            "revision_number",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_custom_post_entry_revisions_entry",
        "custom_post_entry_revisions",
        ["entry_id"],
    )
