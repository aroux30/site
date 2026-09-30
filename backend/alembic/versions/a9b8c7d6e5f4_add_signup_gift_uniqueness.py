"""Enforce one-time signup gift via partial unique index.

Business rule (Karta signup_gift): the welcome gift is credited at most
once per user. The service-level COUNT check raced with concurrent claim
requests; this partial unique index on ``wallet_transactions.reference_id``
(where ``reference_type='signup_gift'`` and the ledger entry is a ``bonus``
credit) makes the rule enforceable by the database itself — the wallet
credit and its uniqueness commit atomically.

AWARENESS: if historical data contains duplicate signup-gift bonuses for a
user, this migration will fail on ``create_index``. Resolve the duplicates
first — those rows were already invalid from a business standpoint.

Revision ID: a9b8c7d6e5f4
Revises: f1a2b3c4d5e6
Create Date: 2026-09-14
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "a9b8c7d6e5f4"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "uq_wallet_signup_gift_once",
        "wallet_transactions",
        ["reference_id"],
        unique=True,
        postgresql_where=sa.text("reference_type = 'signup_gift' AND type = 'bonus'"),
    )


def downgrade() -> None:
    op.drop_index("uq_wallet_signup_gift_once", table_name="wallet_transactions")
