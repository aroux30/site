"""user_profiles.display_name: the name a person wants published

P1 "کاربران: نام نمایشی/نام مستعار (Display Name / Nickname)". The name shown
publicly was always derived from first+last, so an author who writes under a
pen name had their legal name published by every byline, and a customer whose
account is in a legal name had no way to show anything else on a review.

Nullable with no default and nothing backfilled: NULL means "use first+last",
which is exactly what every consumer does today, so existing rows render
unchanged. Backfilling would make an unedited profile indistinguishable from
one where the operator chose the same words.

Revision ID: dspname1
Revises: emlchg1
Create Date: 2026-10-02
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "dspname1"
down_revision: str | None = "emlchg1"

branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "user_profiles",
        sa.Column("display_name", sa.String(length=100), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("user_profiles", "display_name")