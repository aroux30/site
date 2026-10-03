"""add site_health_runs

Site Health only answered "is it broken right now": the checks ran inside a
request and their result vanished on reload, so a disk that filled up at 3am
left no trace and the next visit could not tell "healthy" from "was broken an
hour ago". WordPress keeps a page of what ran; this is the same record.

trigger is 'scheduled' or 'manual' because a reader comparing two rows needs to
know which is which: a manual run is one person's sample of one moment, a
scheduled one is the state nobody was watching.

RevisionLimit:
- Type: added Table
- Table: site_health_runs
- Nullable: not applicable (new table)

ColumnLimit:
- Column: site_health_runs.started_at
- Type: timestamptz
- Nullable: no

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "b3n4o5p6q7r8"
down_revision = "k7m8n9o0p1q2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "site_health_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "trigger",
            sa.String(length=20),
            server_default=sa.text("'scheduled'"),
            nullable=False,
        ),
        sa.Column("report", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("worst_status", sa.String(length=20), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        # server_default now(), matching BaseModel in app/core/database/base.py.
        # Without it the insert fails on the NOT NULL: the model relies on a
        # server default, not on a Python-side value, so a row created by any
        # path other than the ORM would leave these null.
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    # The history screen reads newest-first and the retention prune walks by
    # age, so both want this index; neither is covered by anything else.
    op.create_index(
        "ix_site_health_runs_started_at", "site_health_runs", ["started_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_site_health_runs_started_at", table_name="site_health_runs")
    op.drop_table("site_health_runs")