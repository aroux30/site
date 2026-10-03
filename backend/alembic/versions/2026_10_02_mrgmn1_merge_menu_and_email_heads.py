"""Merge the menu-location and email-verification heads.

Two sessions branched from ``mdtitle1`` at once: this one added ``mnloc1``
(site_menus.location as a free slug) and the users session added ``emlver1``
(``email_verification_tokens``), which was itself extended by ``emlchg1`` and
``dspname1``. Two heads make ``alembic upgrade head`` ambiguous and refuse to
run, which blocks every later migration on both branches — the failure mode
this project has hit before, so the merge is a revision rather than a manual
fix on the database.

Empty on purpose: a merge revision changes no schema, it only gives the two
lines a single descendant so ``head`` means one thing again.

Revision ID: mrgmn1
Revises: mnloc1, dspname1
Create Date: 2026-10-02
"""

from __future__ import annotations

revision = "mrgmn1"
down_revision = ("mnloc1", "dspname1")

branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
