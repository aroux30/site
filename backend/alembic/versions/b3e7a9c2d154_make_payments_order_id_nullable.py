"""Allow orderless (wallet top-up) payments (TASK P6-02).

``payments.order_id`` becomes nullable so a wallet top-up can be represented
as a payment whose ``extra_data.purpose == "wallet_topup"`` and whose owning
user is recorded in ``extra_data.wallet_user_id``.

Revision ID: b3e7a9c2d154
Revises: a7f2c91d4e08
Create Date: 2026-09-11 23:20:00

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "b3e7a9c2d154"
down_revision = "a7f2c91d4e08"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "payments",
        "order_id",
        existing_type=sa.UUID(),
        nullable=True,
    )


def downgrade() -> None:
    # Fails if orderless top-up payments exist — delete or reassign them first.
    op.alter_column(
        "payments",
        "order_id",
        existing_type=sa.UUID(),
        nullable=False,
    )
