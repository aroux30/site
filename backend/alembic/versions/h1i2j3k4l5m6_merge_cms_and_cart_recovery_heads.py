"""Merge the CMS-pages and cart-recovery heads, add blog locale.

Revision ID: h1i2j3k4l5m6
Revises: c9d0e1f2a3b4, e2a3f4b5c6d7
Create Date: 2026-09-24 10:30:00

Two parallel CMS workstreams each merged the original head pair
(``a1c8f2b3d4e5`` order snapshots / ``b3c4d5e6f7a8`` multi-warehouse) and left
two new heads: ``c9d0e1f2a3b4`` (cms_pages + revisions) and ``e2a3f4b5c6d7``
(cart recovery). This revision unifies them so ``alembic upgrade head`` is
unambiguous again, and adds the ``blog_posts.locale`` column for i18n.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "h1i2j3k4l5m6"
down_revision = ("c9d0e1f2a3b4", "e2a3f4b5c6d7")
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "blog_posts",
        sa.Column(
            "locale",
            sa.String(length=10),
            nullable=False,
            server_default=sa.text("'fa'::character varying"),
        ),
    )


def downgrade() -> None:
    op.drop_column("blog_posts", "locale")
