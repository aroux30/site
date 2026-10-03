"""add blog_tags.description

Categories carried a `description` from the start — it is the text shown on the
category archive — but tags did not, so a tag could be renamed and re-slugged
and nothing else about it could be said. WordPress lets a term carry a
description whatever its taxonomy, and the editor had no field for it because
the column was never there.

Nullable with no backfill: an existing tag simply has no description yet, which
reads the same as an empty one.

RevisionLimit:
- Type: added Column
- Table: blog_tags
- Nullable: yes

ColumnLimit:
- Column: blog_tags.description
- Type: Text
- Nullable: yes

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "t1u2v3w4x5y6"
# Only `b3n4o5p6q7r8` was a head when this ran; the other three are its
# ancestors, so listing them made alembic delete their `alembic_version` rows a
# second time and abort a from-empty `upgrade head` (KeyError on each).
down_revision = "b3n4o5p6q7r8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "blog_tags",
        sa.Column("description", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("blog_tags", "description")
