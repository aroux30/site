"""Titles & Meta wave: per-resource robots/OG/Twitter/score columns.

Rank Math's editor has an Advanced tab (per-resource robots directives), a
Social tab (OG type + Twitter overrides), and a score badge fed from a stored
score. The `seo_metadata` table carried only title/description/canonical/og_*/
schema_markup/focus_keyword, so none of those could be expressed.

All columns are NULLable with no server default: NULL means "no explicit
operator choice", which is different from False ("explicitly indexable") and
lets a page override a broader rule. A non-null default would have made every
existing row claim an explicit choice it never had.

Revision ID: seotm1
Revises: rmcpt1
Create Date: 2026-10-09
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "seotm1"
down_revision: str | None = "rmcpt1"

branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("seo_metadata", sa.Column("robots_noindex", sa.Boolean(), nullable=True))
    op.add_column("seo_metadata", sa.Column("robots_nofollow", sa.Boolean(), nullable=True))
    op.add_column("seo_metadata", sa.Column("og_type", sa.String(length=50), nullable=True))
    op.add_column(
        "seo_metadata", sa.Column("twitter_title", sa.String(length=200), nullable=True)
    )
    op.add_column(
        "seo_metadata", sa.Column("twitter_description", sa.String(length=500), nullable=True)
    )
    op.add_column(
        "seo_metadata", sa.Column("twitter_image", sa.String(length=500), nullable=True)
    )
    op.add_column(
        "seo_metadata", sa.Column("secondary_focus_keywords", sa.Text(), nullable=True)
    )
    op.add_column("seo_metadata", sa.Column("seo_score", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("seo_metadata", "seo_score")
    op.drop_column("seo_metadata", "secondary_focus_keywords")
    op.drop_column("seo_metadata", "twitter_image")
    op.drop_column("seo_metadata", "twitter_description")
    op.drop_column("seo_metadata", "twitter_title")
    op.drop_column("seo_metadata", "og_type")
    op.drop_column("seo_metadata", "robots_nofollow")
    op.drop_column("seo_metadata", "robots_noindex")
