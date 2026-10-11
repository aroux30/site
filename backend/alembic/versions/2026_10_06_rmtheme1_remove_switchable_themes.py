"""Remove the switchable themes module (decision 2026-10-06).

The owner asked for «پوسته‌ها» to be deleted outright — a retail storefront
needs only the day/night toggle, which lives entirely in ``globals.css``
(``:root`` + ``.dark``) and is untouched by this removal. The code is
archived under ``_archived/themes-removal-2026-10-06/``.

What the module was:

- **``site_themes``** — named token sets (colors, radius, dark-mode default).
  Activation copied a theme's tokens into the ``theme`` single type; the
  storefront root layout then injected them as CSS variables. Four builtin
  presets existed (default/minimal-light/midnight/warm-safran); operators
  could save and switch between snapshots.
- **``site_settings`` row ``key='theme'`` (group ``cms``)** — the single type
  the storefront actually rendered from. With the module gone the registry
  entry is gone, so the row is dead data.

Verified at removal time (live probe 2026-10-06):
- ``site_themes`` = 4 rows (all builtin presets; 1 active), ``site_settings``
  theme row = 1. Full rows captured to ``_capture_theme.json`` in the archive.
- ``audit_logs`` holds 20 rows with ``resource='site_theme'`` — left untouched
  by established practice (the audit trail records history, it is not module
  state).

``downgrade()`` recreates ``site_themes`` exactly as
``c4d81f52a9b7_cms_parity_completion_newsletter_themes_i18n`` defined it —
same columns, types, defaults, unique constraint, indexes — re-inserts the
four observed theme rows and the ``site_settings`` theme row with their
captured UUIDs/timestamps (``ON CONFLICT DO NOTHING``, so a database that
already has the rows is left alone).

Chain: ``rmnews1 → rmdms1 → auditct1 → rmtheme1`` — a strictly linear head
chain. ``auditct1`` (session 2's entity-change-log enum-case fix) was already
applied to the live database when this migration landed, so it re-parents onto
it instead of forming a parallel head off ``rmdms1``.

Revision ID: rmtheme1
Revises: auditct1
Create Date: 2026-10-06
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "rmtheme1"
down_revision = "auditct1"
branch_labels = None
depends_on = None


#: The four builtin theme rows as they existed at removal (captured live to
#: ``_capture_theme.json``). ``tokens`` is the JSONB document as JSON text.
_THEMES: list[dict[str, str]] = [
    {
        "id": "60ea6529-2e51-4993-8f5c-f0598b51799d",
        "slug": "default",
        "name": "پیش‌فرض سبزفام",
        "tokens": '{"colors": {"text": "#1c1917", "muted": "#78716c", "accent": "#f59e0b", "primary": "#0f766e", "surface": "#ffffff", "secondary": "#134e4a", "background": "#fafaf9"}, "radius": "0.75rem", "dark_mode_default": false}',
        "is_builtin": "true",
        "is_active": "true",
        "created_at": "2026-09-30T16:54:09.518455+00:00",
        "updated_at": "2026-10-05T12:29:49.706064+00:00",
    },
    {
        "id": "c208227b-8c24-4c64-8758-abfa55022acc",
        "slug": "midnight",
        "name": "شب",
        "tokens": '{"colors": {"text": "#e2e8f0", "muted": "#94a3b8", "accent": "#22d3ee", "primary": "#8b5cf6", "surface": "#141a2b", "secondary": "#6d28d9", "background": "#0b0f1a"}, "radius": "1rem", "dark_mode_default": true}',
        "is_builtin": "true",
        "is_active": "false",
        "created_at": "2026-09-30T16:54:09.518455+00:00",
        "updated_at": "2026-09-30T17:00:51.273034+00:00",
    },
    {
        "id": "389f726a-7a6b-4e30-b224-463e3a88db2c",
        "slug": "minimal-light",
        "name": "روشن مینیمال",
        "tokens": '{"colors": {"text": "#0f172a", "muted": "#64748b", "accent": "#06b6d4", "primary": "#2563eb", "surface": "#f8fafc", "secondary": "#1e3a8a", "background": "#ffffff"}, "radius": "0.375rem", "dark_mode_default": false}',
        "is_builtin": "true",
        "is_active": "false",
        "created_at": "2026-09-30T16:54:09.518455+00:00",
        "updated_at": "2026-09-30T17:00:46.004754+00:00",
    },
    {
        "id": "6a3f1b0a-24d2-4ea3-9b07-2055fd4ec926",
        "slug": "warm-safran",
        "name": "گرم زعفرانی",
        "tokens": '{"colors": {"text": "#292524", "muted": "#a8a29e", "accent": "#dc2626", "primary": "#b45309", "surface": "#fef3c7", "secondary": "#7c2d12", "background": "#fffbeb"}, "radius": "0.5rem", "dark_mode_default": false}',
        "is_builtin": "true",
        "is_active": "false",
        "created_at": "2026-09-30T16:54:09.518455+00:00",
        "updated_at": "2026-10-05T12:29:49.706067+00:00",
    },
]

#: The ``theme`` single-type row (site_settings, group='cms') as it existed at
#: removal. Value is the same JSONB document as the active theme's tokens.
_SETTINGS_THEME_ROW: dict[str, str] = {
    "id": "01d40ce3-24a3-429e-a56d-3035f61b3ccd",
    "value": '{"colors": {"text": "#1c1917", "muted": "#78716c", "accent": "#f59e0b", "primary": "#0f766e", "surface": "#ffffff", "secondary": "#134e4a", "background": "#fafaf9"}, "radius": "0.75rem", "dark_mode_default": false}',
    "description": "توکن‌های تم فروشگاه (رنگ‌ها، تایپوگرافی، گردی گوشه‌ها) — بدون دیپلوی قابل تغییر",
    "created_at": "2026-09-24T11:14:26.995962+00:00",
    "updated_at": "2026-10-05T12:29:49.704766+00:00",
}


def upgrade() -> None:
    # Children first: indexes, then the table. The four rows are captured in
    # the archive's _capture_theme.json (and inlined below for downgrade), so
    # dropping loses nothing recoverable.
    op.drop_index("ix_site_themes_slug", table_name="site_themes")
    op.drop_index("ix_site_themes_is_active", table_name="site_themes")
    op.drop_table("site_themes")

    # The single-type row the storefront used to render from. "group" is a
    # reserved word and must stay double-quoted.
    op.execute(
        sa.text("DELETE FROM site_settings WHERE key = 'theme' AND \"group\" = 'cms'")
    )


def downgrade() -> None:
    """Recreate ``site_themes`` exactly as ``c4d81f52a9b7`` defined it.

    Schema-faithful: same column order, types, defaults, unique constraint and
    indexes. The four builtin rows and the ``site_settings`` theme row are
    re-inserted with their observed UUIDs and timestamps.
    """
    op.create_table(
        "site_themes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("tokens", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "is_builtin",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_site_themes")),
        sa.UniqueConstraint("slug", name="uq_site_themes_slug"),
    )
    op.create_index("ix_site_themes_slug", "site_themes", ["slug"])
    op.create_index("ix_site_themes_is_active", "site_themes", ["is_active"])

    for theme in _THEMES:
        op.execute(
            sa.text(
                "INSERT INTO site_themes (id, slug, name, tokens, is_builtin, is_active,"
                " created_at, updated_at)"
                " VALUES (CAST(:id AS uuid), :slug, :name, CAST(:tokens AS jsonb),"
                " CAST(:is_builtin AS boolean), CAST(:is_active AS boolean),"
                " CAST(:created_at AS timestamptz), CAST(:updated_at AS timestamptz))"
                " ON CONFLICT (slug) DO NOTHING"
            ).bindparams(**theme)
        )

    op.execute(
        sa.text(
            "INSERT INTO site_settings (id, key, value, \"group\", description, is_public,"
            " created_at, updated_at)"
            " VALUES (CAST(:id AS uuid), 'theme', CAST(:value AS jsonb), 'cms',"
            " :description, true,"
            " CAST(:created_at AS timestamptz), CAST(:updated_at AS timestamptz))"
            " ON CONFLICT (key) DO NOTHING"
        ).bindparams(**_SETTINGS_THEME_ROW)
    )
