"""users.pending_approval: hold a new account until an operator approves it

P1 "کاربران: تأیید حساب توسط مدیر". Registration always returned a token pair
immediately, so a store that wants to vet signups (a wholesale storefront, a
closed beta) had no mechanism — an operator had to notice the account and block
it after the fact.

The flag is separate from ``is_active`` on purpose: a blocked account was
active and lost access, a pending one never had it. Conflating them would make
"unblock" and "approve" the same button and lose the reason the account is
closed.

Default false, and existing rows are backfilled false — every account that
exists today was admitted under the old rules and must not become pending on a
migration.

Revision ID: aprvreg1
Revises: prvmail1
Create Date: 2026-10-03
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "aprvreg1"
down_revision: str | None = "prvmail1"

branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "pending_approval",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "pending_approval")