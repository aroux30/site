"""Add slug_history.updated_at, which the ORM has always selected.

Found by scripts/check_model_schema_sync.py: `SlugHistory` inherits
`TimestampMixin`, so every select on the table named `updated_at` — a column
the table was created without. The failure was invisible until that check ran,
because nothing in the codebase queries the table on a common path: the
"old slug redirect" feature that would use it has no caller.

Idempotent, so a re-run after a partial failure does not raise — a migration
that cannot be re-run is how a database gets permanently stuck.

Revision ID: n8o9p0q1r2s3
Revises: q7w8e9r0t1y2
Create Date: 2026-10-01
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "n8o9p0q1r2s3"
down_revision = "q7w8e9r0t1y2"
branch_labels = None
depends_on = None


def _columns(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    if "updated_at" in _columns("slug_history"):
        return
    op.add_column(
        "slug_history",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            # Existing rows need a value: server_default backfills them with the
            # row's own creation time, which is the truth — a slug history row
            # was never updated after it was written.
            server_default=sa.text("now()"),
        ),
    )
    # Settle the backfill so the default is not part of the schema afterwards;
    # every other table in this project leaves it in place, so this matches.
    op.execute(
        "UPDATE slug_history SET updated_at = created_at WHERE updated_at > created_at"
    )


def downgrade() -> None:
    if "updated_at" in _columns("slug_history"):
        op.drop_column("slug_history", "updated_at")