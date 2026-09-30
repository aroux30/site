"""CMS page locale column (i18n parity, pass 1 batch 7).

Revision ID: p8q9r0s1t2u3
Revises: o7p8q9r0s1t2
Create Date: 2026-09-24 13:30:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "p8q9r0s1t2u3"
down_revision = "o7p8q9r0s1t2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "cms_pages",
        sa.Column(
            "locale",
            sa.String(length=10),
            server_default=sa.text("'fa'::character varying"),
            nullable=False,
        ),
    )
    op.create_index("ix_cms_pages_locale", "cms_pages", ["locale"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_cms_pages_locale", table_name="cms_pages")
    op.drop_column("cms_pages", "locale")
