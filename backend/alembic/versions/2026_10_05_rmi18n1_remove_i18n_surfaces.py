"""Remove the i18n surfaces — string catalogue + content translation links.

The owner asked for «کاتالوگ رشته‌ها» and the translation-management surfaces
to be deleted outright: the store is Persian-only in practice, the string
catalogue had zero migrated strings and zero readers, and the content
translation UI had zero linked rows. Both were dead weight kept alive by
their own admin screens. The code is archived under
``_archived/i18n-removal-2026-10-05/``.

What this migration drops:

* ``localization_strings`` — the UI-string catalogue table (3 rows at
  removal time: one junk test key in fa/en/ar; dumped to
  ``localization_strings_rows_before_drop.json`` in the archive).
* ``blog_posts.translation_group`` + its index.
* ``cms_pages.translation_group`` + its index.

What is deliberately KEPT (not i18n surfaces): the ``locale`` columns on
``blog_posts``/``cms_pages`` (content rows still carry a locale; the site
is Persian-only but the column is part of the content model) and the
``enabled_locales``/``default_locale`` site options.

Evidence at removal time (live probes 2026-10-05):

* ``localization_strings`` = 3 rows, all one test key («شیسشسشسشی») in
  fa/en/ar — no operator data. Zero readers: no component calls ``t()``.
* ``blog_posts.translation_group``: 0 non-null. ``cms_pages``: 0 non-null.
  ``blog_post_relationships`` translation rows: 0.
* Zero live importers of the removed service/schemas outside the deleted
  routes; zero frontend consumers besides the deleted pages and the
  LanguageSwitcher.

``downgrade()`` recreates the table exactly as ``d5e9f2a3b8c1`` defined it,
re-inserts the 3 rows with their original ids, and re-adds both
``translation_group`` columns and indexes as ``c4d81f52a9b7`` created them —
so the removal is fully reversible. Chain note: this migration is the new
head (``down_revision = rmopscenter1`` — it was briefly parented to
``rmaccount1`` in parallel with the ops-center removal; the two were chained
linearly after the collision was detected, before either ran past
``rmaccount1``).

Revision ID: rmi18n1
Revises: rmopscenter1
Create Date: 2026-10-05
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "rmi18n1"
down_revision = "rmopscenter1"
branch_labels = None
depends_on = None

#: The three rows as they existed at removal (dumped live before dropping,
#: ids pinned so a downgrade restores the exact rows; values are a junk test
#: key, kept verbatim for byte-exact reversibility).
_SEED_ROWS: list[dict[str, object]] = [
    {
        "id": "3ed8ea8d-1e20-438e-bc3c-e1fc1bf4dd21",
        "key": "شیسشسشسشی",
        "locale": "ar",
        "value": "شسیشس",
        "created_at": "2026-10-05 18:44:12.909216+03:30",
    },
    {
        "id": "7b2a390a-759d-484c-8193-0e9f2e85784a",
        "key": "شیسشسشسشی",
        "locale": "en",
        "value": "شسیسش",
        "created_at": "2026-10-05 18:44:12.457241+03:30",
    },
    {
        "id": "f0031f2d-dffe-4179-ae62-9075e2700b92",
        "key": "شیسشسشسشی",
        "locale": "fa",
        "value": "سسس",
        "created_at": "2026-10-05 18:44:07.631388+03:30",
    },
]


def upgrade() -> None:
    # Children before parents: nothing FKs into localization_strings.
    op.drop_index("ix_localization_strings_group", table_name="localization_strings")
    op.drop_index("ix_localization_strings_locale", table_name="localization_strings")
    op.drop_table("localization_strings")

    op.drop_index("ix_blog_posts_translation_group", table_name="blog_posts")
    op.drop_column("blog_posts", "translation_group")

    op.drop_index("ix_cms_pages_translation_group", table_name="cms_pages")
    op.drop_column("cms_pages", "translation_group")


def downgrade() -> None:
    """Recreate everything exactly as the original migrations defined it."""
    op.create_table(
        "localization_strings",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("key", sa.String(200), nullable=False),
        sa.Column("locale", sa.String(10), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("group", sa.String(100), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key", "locale", name="uq_localization_strings_key_locale"),
    )
    op.create_index("ix_localization_strings_locale", "localization_strings", ["locale"])
    op.create_index("ix_localization_strings_group", "localization_strings", ["group"])

    op.add_column(
        "blog_posts",
        sa.Column("translation_group", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        "ix_blog_posts_translation_group", "blog_posts", ["translation_group"]
    )

    op.add_column(
        "cms_pages",
        sa.Column("translation_group", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        "ix_cms_pages_translation_group", "cms_pages", ["translation_group"]
    )

    # Restore the three rows with their original ids and timestamps.
    # Explicit casts: the bound parameters arrive as strings, and asyncpg
    # refuses a varchar expression for a uuid/timestamptz column.
    for row in _SEED_ROWS:
        op.execute(
            sa.text(
                "INSERT INTO localization_strings "
                "(id, key, locale, value, \"group\", is_active, created_at, updated_at) "
                "VALUES (CAST(:id AS uuid), :key, :locale, :value, NULL, true, "
                "CAST(:created_at AS timestamptz), CAST(:created_at AS timestamptz))"
            ).bindparams(**row)
        )
