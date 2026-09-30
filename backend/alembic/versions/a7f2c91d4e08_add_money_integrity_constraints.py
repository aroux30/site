"""Add money-integrity constraints (TASK P2-01).

Schema-level defense-in-depth for invariants the application already enforces:

1. UNIQUE (coupon_id, order_id) on coupon_redemptions — an order can never
   redeem one coupon twice, regardless of code path or race.
2. CHECK constraints preventing negative wallet balances, negative inventory
   counters, and non-positive line-item quantities.

Pre-flight (run against production BEFORE deploying this revision — the
migration fails loudly if any row violates an invariant):

    SELECT id, balance FROM wallets WHERE balance < 0;
    SELECT id FROM inventory_items
      WHERE available < 0 OR reserved < 0 OR committed < 0;
    SELECT coupon_id, order_id, COUNT(*) FROM coupon_redemptions
      GROUP BY 1, 2 HAVING COUNT(*) > 1;
    SELECT id FROM order_items WHERE quantity <= 0;
    SELECT id FROM cart_items WHERE quantity <= 0;

If any query returns rows, remediate the data (and the root cause) first.

Revision ID: a7f2c91d4e08
Revises: 41444c67e586
Create Date: 2026-09-11 22:50:00

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "a7f2c91d4e08"
down_revision = "41444c67e586"
branch_labels = None
depends_on = None

_INTEGRITY_CHECKS = (
    ("ck_wallets_balance_non_negative", "wallets", "balance >= 0"),
    ("ck_inventory_available_non_negative", "inventory_items", "available >= 0"),
    ("ck_inventory_reserved_non_negative", "inventory_items", "reserved >= 0"),
    ("ck_inventory_committed_non_negative", "inventory_items", "committed >= 0"),
    ("ck_order_items_quantity_positive", "order_items", "quantity > 0"),
    ("ck_cart_items_quantity_positive", "cart_items", "quantity > 0"),
)


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_coupon_redemptions_coupon_order",
        "coupon_redemptions",
        ["coupon_id", "order_id"],
    )
    for name, table, condition in _INTEGRITY_CHECKS:
        op.create_check_constraint(name, table, condition)


def downgrade() -> None:
    op.drop_constraint(
        "uq_coupon_redemptions_coupon_order",
        "coupon_redemptions",
        type_="unique",
    )
    for name, table, _condition in reversed(_INTEGRITY_CHECKS):
        op.drop_constraint(name, table, type_="check")
