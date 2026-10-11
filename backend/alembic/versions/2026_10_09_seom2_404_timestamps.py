"""Add created_at/updated_at to seo_404_logs (seom1 follow-up).

`Seo404Log` inherits `BaseModel`, which declares `created_at`/`updated_at`
(`TimestampMixin`) — every ORM SELECT includes those columns, so the table
without them answered the first query with
``UndefinedColumnError: column seo_404_logs.created_at does not exist`` and
the whole 404 panel 500'd. `seom1` created the table from raw columns and
missed what the mixin adds; this is the schema half of that fix.

Chain: ``seom1 -> seom2``.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "seom2"
down_revision: str | None = "seom1"

branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "seo_404_logs",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.add_column(
        "seo_404_logs",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )


def downgrade() -> None:
    op.drop_column("seo_404_logs", "updated_at")
    op.drop_column("seo_404_logs", "created_at")
