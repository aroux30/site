"""users.password_changed_at: when the password last rotated

P0 "کاربران: ایمیل اطلاع تغییر رمز". The rotation revoked every session and
wrote an audit row, and told the person nothing. Adding the notice needs a time
to put in it, and the two columns that already exist cannot supply one:

  - ``users.updated_at`` moves on any profile edit, so it is the last time
    anything changed, not the last time the password did
  - the audit log has the event, but reading an audit trail to answer "when did
    my password change?" is a support escalation, and a notice that cannot
    answer its own question is not a notice

Nullable with no default, so existing accounts read NULL — which the notice
renders as the account's last update, and which is honest: for an account that
has never rotated a password, there is no such time.

Revision ID: pw7h4c2d9k3m
Revises: x5y6z7a8b9c0
Create Date: 2026-10-02
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "pw7h4c2d9k3m"
down_revision = "x5y6z7a8b9c0"

branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    # Drops the notice's timestamp, not the notice: the email keeps working and
    # falls back to updated_at. A downgrade that also removed the feature would
    # turn a schema rollback into a behaviour rollback nobody asked for.
    op.drop_column("users", "password_changed_at")
