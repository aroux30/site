"""Add cms_pages.allow_comments, opt-in and default false.

Gap: docs/store-relevant-cms-gaps-2026-10-01.md, P0 "کامنت: دیدگاه روی
صفحات CMS". The backend already accepted comments on a page
(`COMMENT_RESOURCE_TYPES` includes `cms_page` and `_ensure_page_accepts_comments`
validates it), but `CmsPage` had no column to say whether a given page wants
them, and no storefront page rendered a comment thread at all.

The column defaults to false: a page is a static document until its editor
opts comments in, which is what makes adding it safe for existing rows — a
legal or policy page must not silently start accumulating threads.

Revision ID: x2y3z4a5b6c7
Revises: w1x2y3z4a5b6
Create Date: 2026-10-01
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "x2y3z4a5b6c7"
down_revision = "w1x2y3z4a5b6"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return column in {c["name"] for c in inspector.get_columns(table)}


def upgrade() -> None:
    # Idempotent: a re-run after a partial failure must not raise, because a
    # failed migration that cannot be re-run is how a database gets stuck.
    if not _has_column("cms_pages", "allow_comments"):
        op.add_column(
            "cms_pages",
            sa.Column(
                "allow_comments",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
        )


def downgrade() -> None:
    if _has_column("cms_pages", "allow_comments"):
        op.drop_column("cms_pages", "allow_comments")