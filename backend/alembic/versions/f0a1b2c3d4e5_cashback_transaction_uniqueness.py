"""Enforce one cashback award per (order, rule).

The scheduled cashback task discovers completed orders without a cashback
transaction and inserts one row per matching rule. Discovery ran without a
lock, so two overlapping runs could both insert rows for the same
(order, rule) and then both credit the wallet — a double payout.

This unique constraint makes a duplicate award impossible at the database
level; the worker treats the resulting IntegrityError as "already awarded".

AWARENESS: if historical data already contains duplicate (order_id, rule_id)
pairs, this migration will fail on ``create_unique_constraint``. Resolve the
duplicates first — those rows were already invalid from a business standpoint.

Revision ID: f0a1b2c3d4e5
Revises: f1a2b3c4d5e7
Create Date: 2026-09-17
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "f0a1b2c3d4e5"
down_revision = "f1a2b3c4d5e7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_cashback_transaction_order_rule",
        "cashback_transactions",
        ["order_id", "rule_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_cashback_transaction_order_rule",
        "cashback_transactions",
        type_="unique",
    )
