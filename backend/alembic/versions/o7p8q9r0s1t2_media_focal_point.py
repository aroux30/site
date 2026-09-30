"""Media focal point columns (CMS parity pass 1, batch 6).

Revision ID: o7p8q9r0s1t2
Revises: n6o7p8q9r0s1
Create Date: 2026-09-24 13:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "o7p8q9r0s1t2"
down_revision = "n6o7p8q9r0s1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("media_assets", sa.Column("focal_x", sa.Float(), nullable=True))
    op.add_column("media_assets", sa.Column("focal_y", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("media_assets", "focal_y")
    op.drop_column("media_assets", "focal_x")
