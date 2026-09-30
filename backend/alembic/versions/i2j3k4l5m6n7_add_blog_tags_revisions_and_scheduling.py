"""Add scheduled publishing column to blog_posts.

Revision ID: i2j3k4l5m6n7
Revises: j2k3l4m5n6p7
Create Date: 2026-09-24 12:00:00

The blog tag / post-tag / post-revision tables are created by the sibling
revision ``j2k3l4m5n6p7``. This revision chains on top of it and adds only the
``scheduled_for`` column: a future timestamp at which a draft post is
auto-published by the ``publish_due_scheduled_posts`` beat task (the
WordPress-style "scheduled" posts feature).

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "i2j3k4l5m6n7"
down_revision = "j2k3l4m5n6p7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "blog_posts",
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("blog_posts", "scheduled_for")
