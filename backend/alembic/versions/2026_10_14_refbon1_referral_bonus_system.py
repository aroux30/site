"""Referral + bonus reward system: earner linkage and payout idempotency.

Ports the VPN project's referral/bonus reward system (owner's reference
implementation, hardened by the 2026-10-13 arena — champion: reward ledger
idempotency, per-order uniqueness, clamped percents). No new tables: the
existing ``referrals`` / ``referral_commissions`` / ``wallet_transactions``
schema carries the whole feature.

Changes (all additive):

* ``referral_commissions.earner_id`` — the user who actually receives the
  commission. Previously only ``referral_id`` existed, which cannot express
  a level-2 earner (the level-2 relationship is resolved at payout time by
  walking the chain, so no second ``referrals`` row exists for it). Backfilled
  from ``referrals.referrer_id`` for any existing rows.
* ``uq_referral_commissions_order_earner`` — one commission per order per
  earner. The payout sweep's concurrency backstop (at-most-once).
* ``uq_wallet_referral_rewards_once`` — one wallet credit per
  (reference_type, reference_id) for the referral/bonus reward types. This is
  the money-level backstop: even if a sweep retries, the credit cannot happen
  twice. Partial index (only reward types) so unrelated wallet rows are not
  affected.

Enums are stored as NAMES (``native_enum=False``), the repo-wide contract.

Revision ID: refbon1
Revises: chatw1
Create Date: 2026-10-14
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "refbon1"
down_revision: str | None = "chatw1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: Wallet reference types this feature writes. The partial unique index below
#: only covers these; every other wallet credit path is untouched.
_REWARD_REFERENCE_TYPES = (
    "referral_signup_gift_l1",
    "referral_signup_gift_l2",
    "referral_commission_l1",
    "referral_commission_l2",
    "recharge_bonus",
)


def upgrade() -> None:
    # ── referral_commissions.earner_id ────────────────────────────────
    op.add_column(
        "referral_commissions",
        sa.Column("earner_id", sa.UUID(), nullable=True),
    )
    # Backfill: before this feature every commission row belonged to the
    # referral's referrer (level 1). The table is empty in practice, but the
    # migration must be correct for any environment that ran the old code.
    op.execute(
        """
        UPDATE referral_commissions rc
        SET earner_id = r.referrer_id
        FROM referrals r
        WHERE rc.referral_id = r.id AND rc.earner_id IS NULL
        """
    )
    # Any row whose referral row is gone cannot exist (FK CASCADE), so after
    # the backfill there is no NULL left. Guard anyway: refuse to set NOT NULL
    # while orphans remain rather than corrupting the column.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM referral_commissions WHERE earner_id IS NULL) THEN
                RAISE EXCEPTION 'refbon1: referral_commissions rows without a resolvable earner remain';
            END IF;
        END $$;
        """
    )
    op.alter_column("referral_commissions", "earner_id", nullable=False)
    op.create_foreign_key(
        "fk_referral_commissions_earner_id_users",
        "referral_commissions",
        "users",
        ["earner_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_referral_commissions_earner_id",
        "referral_commissions",
        ["earner_id"],
        unique=False,
    )
    op.create_unique_constraint(
        "uq_referral_commissions_order_earner",
        "referral_commissions",
        ["order_id", "earner_id"],
    )

    # ── wallet_transactions reward uniqueness ─────────────────────────
    op.create_index(
        "uq_wallet_referral_rewards_once",
        "wallet_transactions",
        ["reference_type", "reference_id"],
        unique=True,
        postgresql_where=sa.text(
            "reference_type IN ("
            + ", ".join(f"'{t}'" for t in _REWARD_REFERENCE_TYPES)
            + ")"
        ),
    )


def downgrade() -> None:
    op.drop_index("uq_wallet_referral_rewards_once", table_name="wallet_transactions")
    op.drop_constraint(
        "uq_referral_commissions_order_earner",
        "referral_commissions",
        type_="unique",
    )
    op.drop_index("ix_referral_commissions_earner_id", table_name="referral_commissions")
    op.drop_constraint(
        "fk_referral_commissions_earner_id_users",
        "referral_commissions",
        type_="foreignkey",
    )
    op.drop_column("referral_commissions", "earner_id")
