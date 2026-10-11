"""Link Genius: internal-link index + keyword maps (Rank Math Pro parity).

Self-hosted internal-linking toolkit. Three tables:

* ``seo_internal_links`` — one row per managed anchor (internal/external) in a
  post body, with ``target_post_id`` resolved when the URL points at a post on
  this site. Answers "which posts link here?" without re-parsing bodies.
* ``seo_link_maps`` — a keyword→URL auto-linking rule.
* ``seo_link_map_variations`` — the keyword phrases of a map.

The suggestion engine stores nothing: suggestions are computed on demand from
the posts, so an edited body can never leave a stale suggestion behind.

Revision ID: seolg1
Revises: rmstatus2
Create Date: 2026-10-11
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "seolg1"
down_revision: str | None = "rmstatus2"

branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "seo_internal_links",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "post_id",
            UUID(as_uuid=True),
            sa.ForeignKey("blog_posts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "target_post_id",
            UUID(as_uuid=True),
            sa.ForeignKey("blog_posts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("url", sa.String(length=500), nullable=False),
        sa.Column("url_hash", sa.String(length=32), nullable=False),
        sa.Column("anchor_text", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("link_type", sa.String(length=20), nullable=False, server_default="internal"),
        sa.Column("is_nofollow", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("target_blank", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint(
            "post_id", "url_hash", "anchor_text", name="uq_seo_internal_links_post_url_anchor"
        ),
    )
    op.create_index("ix_seo_internal_links_post_id", "seo_internal_links", ["post_id"])
    op.create_index(
        "ix_seo_internal_links_target_post_id", "seo_internal_links", ["target_post_id"]
    )
    op.create_index("ix_seo_internal_links_url_hash", "seo_internal_links", ["url_hash"])

    op.create_table(
        "seo_link_maps",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("target_url", sa.String(length=500), nullable=False),
        sa.Column(
            "target_post_id",
            UUID(as_uuid=True),
            sa.ForeignKey("blog_posts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "max_links_per_post", sa.Integer(), nullable=False, server_default=sa.text("3")
        ),
        sa.Column(
            "auto_link_on_publish",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "case_sensitive", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_seo_link_maps_is_active", "seo_link_maps", ["is_active"])

    op.create_table(
        "seo_link_map_variations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "map_id",
            UUID(as_uuid=True),
            sa.ForeignKey("seo_link_maps.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("keyword", sa.String(length=200), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False, server_default="manual"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint(
            "map_id", "keyword", name="uq_seo_link_map_variations_map_keyword"
        ),
    )
    op.create_index(
        "ix_seo_link_map_variations_map_id", "seo_link_map_variations", ["map_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_seo_link_map_variations_map_id", table_name="seo_link_map_variations")
    op.drop_table("seo_link_map_variations")
    op.drop_index("ix_seo_link_maps_is_active", table_name="seo_link_maps")
    op.drop_table("seo_link_maps")
    op.drop_index("ix_seo_internal_links_url_hash", table_name="seo_internal_links")
    op.drop_index("ix_seo_internal_links_target_post_id", table_name="seo_internal_links")
    op.drop_index("ix_seo_internal_links_post_id", table_name="seo_internal_links")
    op.drop_table("seo_internal_links")
