"""Remove the i18n content-locale columns — wave 2 (decision 2026-10-05).

Wave 1 (``rmi18n1``) removed the string catalogue and the content
translation links but deliberately KEPT the ``locale`` columns on content
rows ("part of the content model"). The owner overrode that decision the
same day — «بقیه اش رو هم پاک کن هیچ اثری نمونه» — this store is
Persian-only and no locale column may remain. This migration completes the
removal; the code side (models, schemas, services, search, feed, admin UI,
``enabled_locales``/``default_locale`` options, ``Accept-Language`` in the
page-cache key) was stripped in the same wave.

What this migration drops:

* ``blog_posts.locale`` (``h1i2j3k4l5m6`` created it; 17 rows at removal
  time, ALL ``'fa'`` — zero non-Persian content).
* ``cms_pages.locale`` + ``ix_cms_pages_locale`` (``p8q9r0s1t2u3``).
* ``cms_content_entries.locale`` + ``ix_cms_content_entries_locale``
  (``q9r0s1t2u3v4``; zero rows at removal time).

Evidence at removal time (live probes 2026-10-05, dumped to
``_archived/i18n-removal-2026-10-05/locale_columns_rows_before_drop.json``):

* ``blog_posts``: 17 rows, 1 distinct locale value (``fa``).
* ``cms_pages``: 0 rows. ``cms_content_entries``: 0 rows.
* ``site_settings``: zero ``enabled_locales``/``default_locale`` rows (the
  options existed only as code defaults).

No business data is lost by the drop: every removed value was the column
default. ``downgrade()`` recreates all three columns exactly as their
creating migrations defined them (``String(10)``, NOT NULL,
``server_default 'fa'::character varying``) plus both indexes — a re-run
restores the 17 ``fa`` values structurally (the default backfills them).

Revision ID: rmi18n2
Revises: rmi18n1
Create Date: 2026-10-05
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "rmi18n2"
down_revision = "rmi18n1"
branch_labels = None
depends_on = None

#: The exact definition every creating migration used. Kept as one constant so
#: downgrade() recreates the three columns byte-identically.
_LOCALE_COLUMN = sa.Column(
    "locale",
    sa.String(length=10),
    server_default=sa.text("'fa'::character varying"),
    nullable=False,
)


def upgrade() -> None:
    # Indexes first, then the columns they cover.
    op.drop_index("ix_cms_content_entries_locale", table_name="cms_content_entries")
    op.drop_column("cms_content_entries", "locale")

    op.drop_index("ix_cms_pages_locale", table_name="cms_pages")
    op.drop_column("cms_pages", "locale")

    op.drop_column("blog_posts", "locale")


def downgrade() -> None:
    """Recreate the columns + indexes exactly as their migrations defined them."""
    op.add_column("blog_posts", _LOCALE_COLUMN.copy())

    op.add_column("cms_pages", _LOCALE_COLUMN.copy())
    op.create_index("ix_cms_pages_locale", "cms_pages", ["locale"], unique=False)

    op.add_column("cms_content_entries", _LOCALE_COLUMN.copy())
    op.create_index(
        "ix_cms_content_entries_locale", "cms_content_entries", ["locale"], unique=False
    )
