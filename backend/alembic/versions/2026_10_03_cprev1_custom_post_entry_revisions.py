"""custom post type entries: revision history and scheduled publishing

Two capabilities the other content-entry system (`cms_content_entries`) has and
this one does not, and an operator filling in a `product` or a `testimonial`
through the blog admin's content-types tab had neither:

* **revisions.** The fields are operator-defined JSON with no stable schema, so
  there is nothing to diff — the only way back from a bad overwrite is the
  previous state, kept whole.
* **scheduled publishing.** `custom_post_entries.published_at` existed but
  nothing ever moved a row into `published` when its time arrived, so an entry
  could not be dated forward.

No data migration: `custom_post_entry_revisions` is new and empty, and the new
column is nullable with no default, so existing rows keep publishing whenever
they were last set to.

RevisionLimit:
- Type: create table, add column
- Table: custom_post_entry_revisions (new), custom_post_entries (new column)

ColumnLimit:
- Column: custom_post_entries.scheduled_publish_at
- Type: DateTime(timezone=True)
- Nullable: yes

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "cprev1"
down_revision = "psskey1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "custom_post_entry_revisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "entry_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("custom_post_entries.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("fields", postgresql.JSONB(), nullable=True),
        sa.Column("title", sa.String(length=500), nullable=True),
        sa.Column("excerpt", sa.String(length=1000), nullable=True),
        sa.Column(
            "revision_number",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        # The base model declares both timestamp columns, so the table needs
        # both — declaring only `created_at` produces a table that imports and
        # inserts fine until an UPDATE touches the mixin.
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    # The lookup that matters is "the revisions of this entry, newest first" —
    # one index on entry_id serves it.
    op.create_index(
        "ix_custom_post_entry_revisions_entry",
        "custom_post_entry_revisions",
        ["entry_id"],
    )

    op.add_column(
        "custom_post_entries",
        sa.Column(
            "scheduled_publish_at", sa.DateTime(timezone=True), nullable=True
        ),
    )


def downgrade() -> None:
    op.drop_column("custom_post_entries", "scheduled_publish_at")
    op.drop_index(
        "ix_custom_post_entry_revisions_entry",
        table_name="custom_post_entry_revisions",
    )
    op.drop_table("custom_post_entry_revisions")