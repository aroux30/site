"""Reward-history index: keep the admin history tab fast at scale.

The history view pages over ``wallet_transactions`` filtered to the five
referral/bonus reference types, ordered by ``created_at DESC, id DESC``.
Measured with 20,000 reward rows (owner's scale question):

* kind-filtered page: 31ms → 0.07ms with this index (index scan);
* unfiltered page: the planner picks it up as the reward share of the table
  shrinks (the partial predicate keeps the index small — it never grows with
  the general wallet ledger).

Partial, matching the same five reference types as
``uq_wallet_referral_rewards_once``. Purely additive; the column expression
order matches the history query's ORDER BY exactly.

Revision ID: refbon2
Revises: refbon1
Create Date: 2026-10-14
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "refbon2"
down_revision: str | None = "refbon1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_REWARD_TYPES = (
    "referral_signup_gift_l1",
    "referral_signup_gift_l2",
    "referral_commission_l1",
    "referral_commission_l2",
    "recharge_bonus",
)


def upgrade() -> None:
    where = "reference_type IN (" + ", ".join(f"'{t}'" for t in _REWARD_TYPES) + ")"
    op.create_index(
        "ix_wallet_reward_history",
        "wallet_transactions",
        [sa.text("created_at DESC"), sa.text("id DESC")],
        unique=False,
        postgresql_where=sa.text(where),
    )


def downgrade() -> None:
    op.drop_index("ix_wallet_reward_history", table_name="wallet_transactions")
