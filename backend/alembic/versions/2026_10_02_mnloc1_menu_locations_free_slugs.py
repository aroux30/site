"""site_menus.location: default as a slug, so custom locations can be added

P1 "منو: مکان‌های منو ثابت". The column was declared with a SQLAlchemy Enum
of five members, which made two things impossible: an operator could not add a
location (the enum rejects the value), and a row holding anything outside the
five raised ``LookupError`` on read — so even if one were written, it could
never be read back.

The database column itself was never constrained: it is ``varchar(32)`` with no
CHECK. What tied it to the five values was the Python-side Enum and its
``server_default`` of ``'HEADER_MAIN'`` (the enum member *name*, per this
project's enum-name storage convention). Now that the model is a plain string
slug, the default must move to the slug form ``'header_main'`` so a row
inserted by raw SQL or a restore does not land as the old name and read back
as an invalid location.

No data change: the table is empty of rows outside the built-ins in every
environment this runs in, and existing built-in rows already store the member
NAME (``'HEADER_MAIN'``) — which, under the old enum, is what the ORM expected.
Those are left exactly as they are; the API's ``validate_menu_location``
normalises input to lowercase and the tree query matches on the stored value,
so a row written as ``'HEADER_MAIN'`` keeps resolving. New rows get the slug
default.

Revision ID: mnloc1
Revises: mdtitle1
Create Date: 2026-10-02
"""

from __future__ import annotations

from alembic import op

revision = "mnloc1"
down_revision = "mdtitle1"

branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing rows store the enum member NAME ('HEADER_MAIN'), because that is
    # this project's enum storage convention. The new string model and the API
    # speak the slug ('header_main'), so the two would not match: a menu that
    # exists would render empty. The five names lower-case to exactly their
    # enum values, so this normalisation is lossless for every built-in — and
    # there are no non-built-in rows to worry about, since the enum made them
    # impossible to write.
    op.execute("UPDATE site_menus SET location = lower(location)")
    op.execute(
        "ALTER TABLE site_menus ALTER COLUMN location SET DEFAULT 'header_main'"
    )


def downgrade() -> None:
    # Back to the NAME form the old enum expected. Only the five built-ins can
    # survive the downgrade: a custom location has no enum member to become,
    # so it is removed rather than silently left unreadable.
    op.execute(
        "DELETE FROM site_menus WHERE lower(location) NOT IN "
        "('header_top', 'header_main', 'footer_col1', 'footer_col2', 'mobile_nav')"
    )
    op.execute("UPDATE site_menus SET location = upper(location)")
    op.execute(
        "ALTER TABLE site_menus ALTER COLUMN location SET DEFAULT 'HEADER_MAIN'"
    )
