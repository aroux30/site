"""Add media_assets.deleted_at / trashed_at so a delete can be undone.

Gap: docs/store-relevant-cms-gaps-2026-10-01.md, P0 "مدیا: سطل زباله". Delete
removed the row and every file on disk in one step, so a mis-click on an image
that 20 products referenced destroyed the store's product imagery with no way
back. The blog module has had a trash since the WordPress-parity work
(``blog_posts.deleted_at``); this brings media to the same contract.

``trashed_at`` is separate from ``deleted_at`` because retention purges by age
of trashing, not by row age — an asset uploaded two years ago and trashed
yesterday must be purgeable on yesterday's schedule.

Revision ID: y3z4a5b6c7d8
Revises: x2y3z4a5b6c7
Create Date: 2026-10-01
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "y3z4a5b6c7d8"
down_revision = "x2y3z4a5b6c7"
branch_labels = None
depends_on = None


def _columns(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    existing = _columns("media_assets")

    if "deleted_at" not in existing:
        op.add_column(
            "media_assets",
            sa.Column(
                "deleted_at",
                sa.DateTime(timezone=True),
                nullable=True,
            ),
        )
        # The library list filters on it, so an index is not optional: without
        # one, every page of the library scans the whole table.
        op.create_index("ix_media_assets_deleted_at", "media_assets", ["deleted_at"])

    if "trashed_at" not in existing:
        op.add_column(
            "media_assets",
            sa.Column(
                "trashed_at",
                sa.DateTime(timezone=True),
                nullable=True,
            ),
        )


def downgrade() -> None:
    existing = _columns("media_assets")
    if "trashed_at" in existing:
        op.drop_column("media_assets", "trashed_at")
    if "deleted_at" in existing:
        op.drop_index("ix_media_assets_deleted_at", table_name="media_assets")
        op.drop_column("media_assets", "deleted_at")