"""Widen email_delivery_logs.status, and merge the two revision branches.

Revision ID: q1w2e3r4t5y6
Revises: d6g8b0c2e4f7, p9r1v2w3x4y5
Create Date: 2026-09-29 00:00:00

Two independent heads existed: ``d6g8b0c2e4f7`` (reverse-lookup indexes,
another session) and ``p9r1v2w3x4y5`` (privacy requests). This is their merge
point, so the chain is single-head again.

It also widens ``email_delivery_logs.status``. SQLAlchemy derives the VARCHAR
length of a non-native enum from the longest *member name*, not the longest
value: with QUEUED/SENT/FAILED/SKIPPED that is 6 ("FAILED"), while the value
actually written is "skipped" — seven characters. Every insert on an
unconfigured-SMTP install therefore failed with StringDataRightTruncationError,
which is the common local case, so email delivery was broken everywhere. An
explicit length is the only fix; deriving it again would re-create the bug the
moment a longer member name is added.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "q1w2e3r4t5y6"
# `d6g8b0c2e4f7` is an ancestor of `p9r1v2w3x4y5`, so it was not a head when
# this merge ran. Keeping it made alembic delete an `alembic_version` row twice
# and abort a from-empty `upgrade head` with `KeyError: 'd6g8b0c2e4f7'`.
down_revision = "p9r1v2w3x4y5"
branch_labels = None
depends_on = None

TABLE = "email_delivery_logs"


def upgrade() -> None:
    op.alter_column(
        TABLE,
        "status",
        type_=sa.String(length=20),
        existing_type=sa.String(length=6),
        existing_nullable=False,
    )


def downgrade() -> None:
    # Rows written as SKIPPED do not fit back into 6 characters. Rewriting them
    # to FAILED keeps the constraint satisfiable and is the honest inverse:
    # nothing was ever sent.
    op.execute(
        sa.text(f"UPDATE {TABLE} SET status = 'FAILED' WHERE status = 'SKIPPED'")
    )
    op.alter_column(
        TABLE,
        "status",
        type_=sa.String(length=6),
        existing_type=sa.String(length=20),
        existing_nullable=False,
    )
