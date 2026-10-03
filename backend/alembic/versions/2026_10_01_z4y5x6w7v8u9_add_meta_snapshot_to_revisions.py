"""add meta_snapshot to blog_post_revisions

Revisions stored the post's title, body, excerpt, cover and SEO fields, but not
its custom fields (blog_post_meta). Restoring a revision therefore left the
newer SEO overrides and structured data in place while the text went back: the
editor saw a revision on screen and a post that did not match it, and the next
diff reported changes nobody made. WordPress stores postmeta inside the
revision row for the same reason (wp_postmeta has a revision_id).

RevisionLimit:
- Type: added Column
- Table: blog_post_revisions
- Nullable: yes — revisions written before this column keep NULL, which the
  restore path reads as "this revision has no custom fields", the same reading
  a post with an empty meta table gives.

ColumnLimit:
- Column: blog_post_revisions.meta_snapshot
- Type: text
- Nullable: yes

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "z4y5x6w7v8u9"
down_revision = "y3z4a5b6c7d8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "blog_post_revisions",
        sa.Column("meta_snapshot", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("blog_post_revisions", "meta_snapshot")