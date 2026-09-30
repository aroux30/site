"""Media folders column (CMS parity pass 1, batch 2).

Revision ID: n6o7p8q9r0s1
Revises: m5n6o7p8q9r0
Create Date: 2026-09-24 12:30:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "n6o7p8q9r0s1"
down_revision = "m5n6o7p8q9r0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("media_assets", sa.Column("folder", sa.String(length=300), nullable=True))
    op.create_index("ix_media_assets_folder", "media_assets", ["folder"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_media_assets_folder", table_name="media_assets")
    op.drop_column("media_assets", "folder")
