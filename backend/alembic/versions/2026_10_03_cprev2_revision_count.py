"""custom_post_entries.revision_count

Separated from `cprev1` rather than added to it: `cprev1` has already been
applied to this database, and editing an applied migration is how two
deployments end up with different schemas from the same revision id.

The column is a cache of a count that `MAX(revision_number)` already answers.
It exists so the service can decide whether to snapshot without an aggregate on
every write, and so the panel can show "۱۲ نسخه" without asking for one.

RevisionLimit:
- Type: updated Rows
- Table: custom_post_entries

ColumnLimit:
- Column: custom_post_entries.revision_count
- Type: Integer
- Nullable: no

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "cprev2"
down_revision = "cprev1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "custom_post_entries",
        sa.Column(
            "revision_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    # Entries edited before this column existed have revisions on disk that the
    # counter cannot know about. Backfilling from `MAX` is cheaper than leaving
    # every one of them at zero, which would suppress their next snapshot.
    op.execute(
        """
        UPDATE custom_post_entries e
        SET revision_count = COALESCE(
            (SELECT MAX(r.revision_number)
             FROM custom_post_entry_revisions r
             WHERE r.entry_id = e.id),
            0
        )
        """
    )


def downgrade() -> None:
    op.drop_column("custom_post_entries", "revision_count")