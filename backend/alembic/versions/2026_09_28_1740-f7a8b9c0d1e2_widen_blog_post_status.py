"""Widen blog_posts.status for the pending_review workflow state

Revision ID: f7a8b9c0d1e2
Revises: e6f7a8b9c0d1
Create Date: 2026-09-28 17:40:00.000000+03:30

``blog_posts.status`` was created as VARCHAR(9) — long enough for "published",
the longest value the enum had at the time. ``pending_review`` is 14
characters, so the editorial workflow could not actually store the state it
reports: the UPDATE failed with StringDataRightTruncationError. The model
declares a plain Enum (no length), so the column is the only place the cap
lives and widening it is the whole fix.

32 is comfortably above every current and foreseeable member.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f7a8b9c0d1e2"
down_revision: str = "e6f7a8b9c0d1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "blog_posts",
        "status",
        type_=sa.String(length=32),
        existing_type=sa.String(length=9),
        existing_nullable=False,
    )


def downgrade() -> None:
    # Only safe when no pending_review row exists — the value does not fit.
    op.execute("DELETE FROM blog_posts WHERE status = 'pending_review'")
    op.alter_column(
        "blog_posts",
        "status",
        type_=sa.String(length=9),
        existing_type=sa.String(length=32),
        existing_nullable=False,
    )
