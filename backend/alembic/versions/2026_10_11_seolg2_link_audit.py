"""Broken-link crawler: the audit table (Link Genius, Rank Math Pro parity).

One row per distinct URL the crawler has checked. The same dead URL linked
from ten posts is checked once (`url_hash` unique) and reported once.
`last_checked_at` gates the 24h re-check skip; `is_marked_safe` is the
operator's override for a URL that blocks bots but works in a browser.

Revision ID: seolg2
Revises: seolg1
Create Date: 2026-10-11
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "seolg2"
down_revision: str | None = "seolg1"

branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "seo_link_audit",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("url", sa.String(length=2000), nullable=False),
        sa.Column("url_hash", sa.String(length=32), nullable=False),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("category", sa.String(length=20), nullable=False, server_default="ok"),
        sa.Column("detail", sa.String(length=500), nullable=True),
        sa.Column(
            "is_marked_safe", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("url_hash", name="uq_seo_link_audit_url_hash"),
    )
    op.create_index("ix_seo_link_audit_category", "seo_link_audit", ["category"])
    op.create_index("ix_seo_link_audit_last_checked", "seo_link_audit", ["last_checked_at"])


def downgrade() -> None:
    op.drop_index("ix_seo_link_audit_last_checked", table_name="seo_link_audit")
    op.drop_index("ix_seo_link_audit_category", table_name="seo_link_audit")
    op.drop_table("seo_link_audit")
