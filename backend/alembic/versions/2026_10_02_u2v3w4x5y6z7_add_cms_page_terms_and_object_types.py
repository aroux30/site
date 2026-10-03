"""cms_page_terms + custom_taxonomies.object_types

A custom taxonomy could be defined, filled with terms, and attached to posts —
and to nothing else. The link table's foreign key pointed at `blog_posts.id`,
so a CMS page could not carry a term at all: no "about us" page could be filed
under a category, and no size guide under a topic. On a store those labels are
what a reader (and a search engine) uses to find a page.

So: a second link table for pages, and `object_types` on the taxonomy saying
which content types it applies to. The column is not a label — `post_id` is
nullable here, which is what makes the split possible, and it is what the term
query below filters on.

Deliberately *not* normalised into a join table: the set of content types is
closed (blog_post, cms_page, custom_post_entry) and is read as a whole on every
taxonomy list. An array of strings answers that query in one round trip; a join
table would need a second query to render the same screen. Postgres has a GIN
index for array containment if the "which taxonomies apply to pages" direction
ever needs one.

Defaults to both types so an existing taxonomy keeps working untouched — an
empty array would have meant "applies to nothing" and silently broken every
taxonomy already in use.

RevisionLimit:
- Type: added Table
- Table: cms_page_terms
- Nullable: page_id is nullable (a term links to posts, pages, or both)

ColumnLimit:
- Column: custom_taxonomies.object_types
- Type: ARRAY(VARCHAR)
- Nullable: no (defaulted to both content types)

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "u2v3w4x5y6z7"
down_revision = "t1u2v3w4x5y6"
branch_labels = None
depends_on = None

# Postgres truncates an identifier at 63 bytes and silently drops the rest, so a
# migration can "succeed" while the constraint it named does not exist. Every
# name below is short by construction rather than by measurement alone.
TABLE = "cms_page_terms"
FK_PAGE = "fk_cms_page_terms_page"        # 25
FK_TERM = "fk_cms_page_terms_term"        # 25
UQ_PAIR = "uq_cms_page_terms_pair"        # 26
IX_PAGE = "ix_cms_page_terms_page"        # 26
IX_TERM = "ix_cms_page_terms_term"        # 26

for _n in (FK_PAGE, FK_TERM, UQ_PAIR, IX_PAGE, IX_TERM):
    assert len(_n) <= 63, f"identifier too long for Postgres: {_n}"


def upgrade() -> None:
    op.add_column(
        "custom_taxonomies",
        sa.Column(
            "object_types",
            postgresql.ARRAY(sa.String(32)),
            nullable=False,
            server_default=sa.text("ARRAY['blog_post','cms_page']::varchar[]"),
        ),
    )

    op.create_table(
        TABLE,
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        # Nullable on purpose: a term that applies to posts only has no page.
        # A NOT NULL here would force every post-only term to invent a page,
        # which is the opposite of what the column is for.
        sa.Column("page_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("term_id", postgresql.UUID(as_uuid=True), nullable=False),
        # BaseModel stamps these, and every sibling table has them. Omitting
        # them here fails at the first insert with "column does not exist",
        # not at migration time — which is how a missing column gets shipped.
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["page_id"], ["cms_pages.id"], name=FK_PAGE, ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["term_id"], ["custom_taxonomy_terms.id"], name=FK_TERM, ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("page_id", "term_id", name=UQ_PAIR),
    )
    op.create_index(IX_PAGE, TABLE, ["page_id"])
    op.create_index(IX_TERM, TABLE, ["term_id"])


def downgrade() -> None:
    op.drop_index(IX_TERM, table_name=TABLE)
    op.drop_index(IX_PAGE, table_name=TABLE)
    op.drop_table(TABLE)
    op.drop_column("custom_taxonomies", "object_types")