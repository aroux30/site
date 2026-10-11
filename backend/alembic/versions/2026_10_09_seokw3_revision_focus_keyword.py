"""Add `focus_keyword` to cms_page_revisions (SEO completion, 2026-10-09).

Third and last of the seokw chain: `seokw1` gave blog posts the column (in
`seo_metadata`), `seokw2` gave CMS pages theirs, and this one carries the
value through the revision snapshots — without it, restoring a page
revision would silently drop the focus keyword while restoring every other
SEO field.

Chain: ``seokw2 -> seokw3``.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "seokw3"
down_revision: str | None = "seokw2"

branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "cms_page_revisions",
        sa.Column("focus_keyword", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("cms_page_revisions", "focus_keyword")
