"""allow comments on a custom post type entry

`blog_comments.resource_consistency` is a check constraint that matched exactly
two shapes: a blog post (where the legacy `post_id` and `resource_id` are the
same value) and a CMS page (`post_id` null). A custom post type entry matched
neither, so a comment on one was refused by the database even after the
service had decided it was allowed — the constraint fired on the INSERT, past
every guard above it.

That is why `supports_comments` appeared to do nothing even after it started
being read: the flag was consulted, the entry passed, and the row was rejected
three lines later. The error a moderator would see names a constraint, which is
not an answer to "can I comment here".

The new shape is the page one — `post_id` null, `resource_id` set — because an
entry has no legacy `post_id`. `content_entry` is added as a third accepted
resource type; nothing about the two existing shapes changes, and no row is
rewritten, because none could exist under the old constraint.

RevisionLimit:
- Type: no data change
- Table: blog_comments (constraint replaced)

ColumnLimit:
- Column: blog_comments.resource_type
- Type: varchar
- Nullable: no

"""

from __future__ import annotations

from alembic import op

revision = "cmtres1"
# The head at the moment this was written. Re-read it immediately
# before running rather than trusting this line: the parallel session
# adds revisions constantly and a stale value is a second head.
down_revision = "pw7h4c2d9k3m"
branch_labels = None
depends_on = None

CONSTRAINT = "ck_blog_comments_resource_consistency"

NEW_DEF = (
    "CHECK ("
    "  ((resource_type = 'blog_post'"
    "    AND post_id IS NOT NULL AND resource_id = post_id)"
    "   OR ((resource_type IN ('cms_page', 'content_entry'))"
    "       AND post_id IS NULL AND resource_id IS NOT NULL))"
    ")"
)

# The original, kept so `downgrade` restores it rather than dropping the
# constraint and leaving the column unchecked.
OLD_DEF = (
    "CHECK ("
    "  ((resource_type = 'blog_post'"
    "    AND post_id IS NOT NULL AND resource_id = post_id)"
    "   OR ((resource_type = 'cms_page')"
    "       AND post_id IS NULL AND resource_id IS NOT NULL))"
    ")"
)


def upgrade() -> None:
    # Raw SQL for the drop, not `op.drop_constraint`. That helper applies the
    # naming convention to whatever it is given, so both the qualified name and
    # the bare name come out prefixed (`ck_blog_comments_ck_blog_comments_…`,
    # `ck_blog_comments_blog_comments_…`) and the drop targets a constraint that
    # never existed. Alembic will not do this for a constraint it did not
    # create; this one predates the project's naming convention.
    op.execute(
        "ALTER TABLE blog_comments DROP CONSTRAINT IF EXISTS " + CONSTRAINT
    )
    op.execute(
        "ALTER TABLE blog_comments ADD CONSTRAINT " + CONSTRAINT + " " + NEW_DEF
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE blog_comments DROP CONSTRAINT IF EXISTS " + CONSTRAINT
    )
    op.execute(
        "ALTER TABLE blog_comments ADD CONSTRAINT " + CONSTRAINT + " " + OLD_DEF
    )