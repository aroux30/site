"""Remove the plugin/hook registry module (decision 2026-10-04).

The owner asked for the plugin/hook system («پلاگین‌ها و هوک‌ها») to be deleted
outright — «هیچ اثری نمیخواهم ازشون باشه» — it has no use in a retail
storefront. The code is archived under ``_archived/plugins-hooks-2026-10-04/``.

The module owned no tables and no columns: the registry was in-process code
(``app/shared/plugins/registry.py``) and the only persistent state it could
write was one optional ``site_settings`` row (key ``plugins.disabled``,
written only when an operator used the enable/disable toggle).

Verified at removal time (live probe 2026-10-04): zero ``site_settings`` rows
match ``plugins%`` — the toggle was never used, so this migration is a no-op
on the live database. The DELETE still runs so any deployment that did use it
drops the orphaned row rather than leaving a key no code can read.

``downgrade()`` recreates nothing: the deleted row was data (a list of
disabled-plugin names), not schema. The removed code did not exist in a
reverted state anyway — restoring the module means restoring the archived
files, and the row it wrote was pure derived state with no foreign keys and no
readers outside the removed module.

Revision ID: rmplugins1
Revises: rmrmawh1
Create Date: 2026-10-04
"""

from __future__ import annotations

from alembic import op

revision = "rmplugins1"
down_revision = "rmrmawh1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The one row the removed module could write. Data, not schema; deleting it
    # is the whole migration.
    op.execute("DELETE FROM site_settings WHERE key = 'plugins.disabled'")


def downgrade() -> None:
    """No-op: the deleted row was derived state of the removed module.

    There is no schema to restore and no row worth recreating — a fresh toggle
    writes the row again if the module is ever restored from the archive.
    """
    pass
