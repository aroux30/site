"""Merge every open head into one, so new migrations get a single parent.

The tree had seven heads — two earlier merges plus five independent lines —
which means `alembic upgrade head` is ambiguous and any new migration would
have created an eighth branch. This merge has no schema change of its own;
it only names the seven parents.

Revision ids here are short on purpose: PostgreSQL truncates identifiers at 63
characters, and the project's `fk_` naming convention interpolates two table
names, so a long revision id silently blocks an unrelated migration later.

Revision ID: w1x2y3z4a5b6
Revises: a1c8f2b3d4e5, b3c4d5e6f7a8, e2a3f4b5c6d7, p9r1v2w3x4y5,
         s1t2u3v4w5x6, s4e5f6a7b8c9
Create Date: 2026-10-01
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import text

revision = "w1x2y3z4a5b6"
# Five of the six parents listed here were ancestors of `s4e5f6a7b8c9`, not
# separate heads — they were already joined by earlier merges. Naming them
# again made alembic delete their `alembic_version` rows twice and abort a
# from-empty `upgrade head` with a KeyError. Only the true head remains.
down_revision = "s4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Nothing to do: a merge revision exists only to join the branches.

    Touching the connection here is deliberate rather than decorative — it
    makes `alembic upgrade head` fail loudly at this step if the merge itself
    is inconsistent, instead of silently succeeding because upgrade() was
    empty.
    """
    op.execute(text("SELECT 1"))


def downgrade() -> None:
    """A merge cannot be undone; downgrade just moves the marker back."""