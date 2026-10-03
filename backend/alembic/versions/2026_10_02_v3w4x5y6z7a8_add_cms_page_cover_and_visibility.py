"""cms_pages: cover image, review status, private and password-protected pages

Three gaps in one migration, all on the same table:

* **cover image.** A blog post had one; a CMS page did not. An "about us" or
  "size guide" page is exactly where a hero image belongs, and without the
  column the editor had nowhere to put one — the storefront shell rendered every
  page headerless.
* **review status.** ``PageStatus`` had draft/published/archived, so a page
  went straight from draft to live with nothing in between. The blog's own
  ``pending_review`` state existed on posts; a page had no way to say "ready,
  but not published yet".
* **private and password-protected.** Both existed on posts and on neither
  here. ``private`` means "staff only"; ``password`` means "published, but the
  body is withheld until the right password is given". The password is stored
  hashed, matching ``blog_posts.visibility_password`` — a plaintext column
  would put every page's secret next to its title in one ``SELECT *``.

Defaults chosen so existing rows keep working: draft pages stay draft, and the
new visibility is "public" for the pages already published. A migration that
defaults a new column to something surprising turns every existing row into a
change without anyone asking.

RevisionLimit:
- Type: added Column
- Table: cms_pages
- Nullable: yes (cover, password) / no (visibility, defaulted)

ColumnLimit:
- Column: cms_pages.cover_image_url
- Type: String(500)
- Nullable: yes

ColumnLimit:
- Column: cms_pages.visibility
- Type: String(16)
- Nullable: no (default 'public')

ColumnLimit:
- Column: cms_pages.visibility_password_hash
- Type: String(255)
- Nullable: yes

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "v3w4x5y6z7a8"
down_revision = "u2v3w4x5y6z7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "cms_pages", sa.Column("cover_image_url", sa.String(length=500), nullable=True)
    )
    # Non-native enum (native_enum=False on the model) to match how every other
    # status column in this schema is declared — a native Postgres enum would
    # need its own type lifecycle and could not gain a value without an
    # ALTER TYPE.
    op.add_column(
        "cms_pages",
        sa.Column(
            "visibility",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'public'"),
        ),
    )
    op.add_column(
        "cms_pages",
        sa.Column("visibility_password_hash", sa.String(length=255), nullable=True),
    )

    # Backfill: a published page is public, everything else is not visible
    # outside the admin panel either. Leaving every row at the 'public' default
    # would have been wrong for the drafts, and there is no way to tell from
    # the new column alone which rows were which.
    #
    # The comparison is case-insensitive on purpose: the column is a
    # non-native enum and the rows hold the *member name* ("PUBLISHED"), not
    # the value ("published"). Matching on the lowercase literal — which is
    # what the API contract uses — matches nothing, and every already-published
    # page would silently become private: a storefront that loses its pages the
    # moment a column is added.
    op.execute(
        """
        UPDATE cms_pages
        SET visibility = CASE
            WHEN upper(status) = 'PUBLISHED' THEN 'public'
            ELSE 'private'
        END
        """
    )
    op.execute("ALTER TABLE cms_pages ALTER COLUMN visibility DROP DEFAULT")


def downgrade() -> None:
    op.drop_column("cms_pages", "visibility_password_hash")
    op.drop_column("cms_pages", "visibility")
    op.drop_column("cms_pages", "cover_image_url")