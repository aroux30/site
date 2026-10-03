"""add comment_type to blog_comments

WordPress's wp_comments has a comment_type column: "comment" for a real
comment, "note" for a private team note, "pingback"/"trackback" for linkbacks.
Only the first two are used here. Without the column the team had nowhere to put
a note — WordPress's own answer to "leave a private note on this post for the
other editors".

The column is NOT NULL with a server_default of 'comment', so every existing
row becomes a real comment and every query that predates notes stays correct
without being taught about them. The public read paths filter on it explicitly
anyway (list_comments, _get_replies, the comment feed): the default is the
safety net, not the mechanism.

RevisionLimit:
- Type: added Column
- Table: blog_comments
- Nullable: no

ColumnLimit:
- Column: blog_comments.comment_type
- Type: varchar(20)
- Nullable: no (server_default 'comment')

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "q7w8e9r0t1y2"
down_revision = "z4y5x6w7v8u9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "blog_comments",
        sa.Column(
            "comment_type",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'comment'"),
        ),
    )
    # A partial index for the public reads, which always filter
    # comment_type='comment' alongside a status or a post. The composite is
    # what those queries actually use; a bare comment_type index would not help
    # them and would only cost write throughput.
    op.create_index(
        "ix_blog_comments_type_post",
        "blog_comments",
        ["comment_type", "post_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_blog_comments_type_post", table_name="blog_comments")
    op.drop_column("blog_comments", "comment_type")