"""Add `focus_keyword` to cms_pages (SEO completion, 2026-10-09).

Companion to `seokw1` (which added the same column to `seo_metadata` for
blog posts). CMS pages keep their own SEO columns (`seo_title`,
`seo_description`) rather than rows in `seo_metadata`, so the focus keyword
for a page belongs beside them — mixed storage would mean two places to look
for one page's SEO state.

TEXT for the same reason as `seokw1`: free text, possibly several
comma-separated keyphrases.

Chain: ``seokw1 -> seokw2`` (seokw1 was the head when this landed).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "seokw2"
down_revision: str | None = "seokw1"

branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "cms_pages",
        sa.Column("focus_keyword", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("cms_pages", "focus_keyword")
