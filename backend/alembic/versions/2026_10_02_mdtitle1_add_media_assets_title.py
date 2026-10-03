"""media_assets.title: WordPress's Title field for an attachment

P1 "مدیا: فیلد Title رسانه". WordPress's attachment editor has four text
fields — Title, Alt Text, Caption, Description — and the library only had
three. The title is the one a gallery shortcode or a lightbox shows, and it is
the field an operator naturally fills when they name a photo "Red running
shoe, side view".

Nullable with no default, so existing rows read NULL and every surface falls
back to ``file_name`` exactly as it does today. Nothing is backfilled from the
file name: an auto-filled title is indistinguishable from a typed one, and the
operator could no longer tell which rows they had curated.

Revision ID: mdtitle1
Revises: cmtres1
Create Date: 2026-10-02
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "mdtitle1"
down_revision = "cmtres1"

branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "media_assets",
        sa.Column("title", sa.String(length=300), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("media_assets", "title")
