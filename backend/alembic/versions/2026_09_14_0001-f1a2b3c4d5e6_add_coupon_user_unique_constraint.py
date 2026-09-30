"""Add per-user coupon redemption uniqueness.

Business rule: a coupon can be redeemed at most once per user
(see ``discounts.validate_coupon``). The application-level COUNT check raced
with concurrent checkouts by the same user; this constraint makes the rule
enforceable by the database itself.

AWARENESS: if historical data violates the rule (the same user redeemed the
same coupon on two different orders), this migration will fail on
``create_unique_constraint``. Resolve the duplicates first — the rows were
already invalid from a business standpoint.

Revision ID: f1a2b3c4d5e6
Revises: 046c7d867b72
Create Date: 2026-09-14
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "f1a2b3c4d5e6"
down_revision = "046c7d867b72"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_coupon_redemptions_coupon_user",
        "coupon_redemptions",
        ["coupon_id", "user_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_coupon_redemptions_coupon_user",
        "coupon_redemptions",
        type_="unique",
    )
