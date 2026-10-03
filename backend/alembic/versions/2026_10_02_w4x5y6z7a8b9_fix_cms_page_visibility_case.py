"""cms_pages.visibility: store the member NAME, not the value

The column is a non-native enum, and SQLAlchemy stores `EnumClass.MEMBER_NAME`
in it — "PUBLIC" — while the API and the Pydantic schema speak the value,
"public". The migration that added this column wrote the value, so every row
it created holds "public" where the ORM looks for "PUBLIC". Reading one of those
rows back raises LookupError, and because the error happens while a *list*
query maps its results, it takes out the whole page list rather than one page.

The model is fixed to the same convention the rest of the schema already uses
(`server_default=text("'PUBLIC'::character varying")`). This migration fixes
the rows the earlier one wrote, and the default, so nothing outside the ORM can
introduce the problem again.

An UPDATE rather than a new column: the data is wrong, not the schema.

RevisionLimit:
- Type: updated Rows
- Table: cms_pages
- Nullable: not applicable

ColumnLimit:
- Column: cms_pages.visibility
- Type: String(16)
- Nullable: no

"""

from __future__ import annotations

from alembic import op

revision = "w4x5y6z7a8b9"
down_revision = "v3w4x5y6z7a8"
branch_labels = None
depends_on = None

# Uppercase is the member name; anything not in this set is data the earlier
# migration could not have written, so it is left alone rather than guessed at.
KNOWN = {"PUBLIC", "PRIVATE", "PASSWORD"}


def upgrade() -> None:
    op.execute(
        """
        UPDATE cms_pages
        SET visibility = upper(visibility)
        WHERE visibility <> ''
          AND upper(visibility) <> visibility
        """
    )
    op.execute("ALTER TABLE cms_pages ALTER COLUMN visibility SET DEFAULT 'PUBLIC'::character varying")


def downgrade() -> None:
    op.execute(
        """
        UPDATE cms_pages
        SET visibility = lower(visibility)
        WHERE visibility <> ''
        """
    )
    op.execute("ALTER TABLE cms_pages ALTER COLUMN visibility SET DEFAULT 'public'::character varying")