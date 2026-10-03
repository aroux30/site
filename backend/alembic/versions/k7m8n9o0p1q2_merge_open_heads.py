"""Merge every open head into one, so `alembic upgrade head` is unambiguous.

The tree had two heads from concurrent work in this repository. A multi-head
tree makes `alembic upgrade head` fail outright, which is worse than an extra
branch — nothing can be applied until it is resolved, so one half-finished
feature blocks every other migration.

This merge has no schema change of its own; it only names its parents.

Revision IDs here are short on purpose: PostgreSQL truncates identifiers at 63
characters, and this project's `fk_` naming convention interpolates two table
names, so a long revision id silently blocks an unrelated migration later.

Revision ID: k7m8n9o0p1q2
Revises: n8o9p0q1r2s3, f0a1b2c3d4e5, m7n8o9p0q1r2
Create Date: 2026-10-01
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import text

revision = "k7m8n9o0p1q2"
# `f0a1b2c3d4e5` was listed here as a third parent, but it is an ancestor of
# `m7n8o9p0q1r2`, which is listed too — so by the time this merge ran it was
# never a head. Alembic tried to delete an `alembic_version` row that a earlier
# merge had already consumed, and a from-empty `upgrade head` aborted with
# `KeyError: 'f0a1b2c3d4e5'`. A parent reachable from another parent is not a
# second branch; drop it.
down_revision = (
    "n8o9p0q1r2s3",
    "m7n8o9p0q1r2",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Nothing to do: a merge revision exists only to join the branches.

    Touching the connection is deliberate rather than decorative — it makes
    `alembic upgrade head` fail loudly here if the merge is inconsistent,
    instead of silently succeeding because upgrade() was empty.
    """
    op.execute(text("SELECT 1"))


def downgrade() -> None:
    """A merge cannot be undone; downgrade just moves the marker back."""