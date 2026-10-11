"""Add `focus_keyword` to seo_metadata (SEO completion, 2026-10-09).

The analyzer (`seo_analyzer.py`) has always scored content against a focus
keyword, and the `/seo/analyze` route accepts one — but nothing stored it:
the column did not exist, the create/update schemas did not carry it, and
the blog editor had no field for it. An operator could analyze a keyword and
then had nowhere to keep the choice, so the score could never be recomputed
against the same keyword later.

The column is TEXT (not VARCHAR(n)): WordPress's Rank Math stores the focus
keyword as a free-text meta value, and a post can legitimately carry several
comma-separated keyphrases (`پابجی موبایل, PUBG Mobile` in the arouxshop
export). A length cap here would silently truncate an import.

Chain: ``rmemail1 -> seokw1`` (rmemail1 was the head when this landed).

The downgrade drops the column. No data backup is taken: the column is new,
so it holds nothing at downgrade time that did not exist before the upgrade.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "seokw1"
down_revision: str | None = "rmemail1"

branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "seo_metadata",
        sa.Column("focus_keyword", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("seo_metadata", "focus_keyword")
