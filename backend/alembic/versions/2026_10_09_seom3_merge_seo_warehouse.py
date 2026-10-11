"""Merge the SEO branch and the warehouse-removal branch.

Two sessions worked in parallel: this session built the SEO menu
(`seokw1`→`seokw2`→`seokw3`→`seom1`→`seom2`) and the other removed the
warehouse dimension (`rmwarehouse1`). Both chained from the same parent
(`seom1`), so `alembic upgrade head` became ambiguous with two heads.

No schema change of its own — a merge revision only names its parents. The
`upgrade()` body touches the connection so a broken merge fails loudly
instead of silently succeeding (same reasoning as the earlier merges).

Chain: ``seom2 + rmwarehouse1 -> seom3``.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

revision: str = "seom3"
down_revision: tuple[str, ...] = ("seom2", "rmwarehouse1")

branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # A merge with an empty body can "succeed" while the branch state is
    # inconsistent; touching the connection surfaces that at this step.
    op.get_bind().execute(text("SELECT 1"))


def downgrade() -> None:
    # Nothing to undo: the two branches keep their own downgrade paths.
    pass
