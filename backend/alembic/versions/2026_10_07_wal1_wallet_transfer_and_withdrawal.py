"""Wallet completion: P2P transfers and reviewable withdrawal requests.

Completes the wallet module (deposit / withdraw / transfer / refund / history /
ledger / idempotency / admin). Two new tables, plus a merge of three heads.

**Heads merge.** At authoring time ``alembic heads`` reported three open heads —
``m7n8o9p0q1r2`` (media edit lineage), ``rmtheme1`` (themes removal) and
``n8o9p0q1r2s3`` (slug-history updated_at) — so ``alembic upgrade head`` was
ambiguous and ``start.sh`` refuses to serve. This revision parents onto all
three and is the single new head.

**New enum members + a widened column.** ``WalletTransactionType`` gains
``TRANSFER_OUT``, ``TRANSFER_IN``, ``WITHDRAWAL_HOLD`` and ``WITHDRAWAL_REVERSAL``.
The column is declared ``Enum(..., native_enum=False)`` **without**
``create_constraint``, so it is a plain ``VARCHAR`` with no CHECK — but
``native_enum=False`` sizes that VARCHAR to the longest member name **at table
creation**, which was ``WITHDRAWAL``/``ADJUSTMENT`` (10). The new members are up
to 19 chars (``WITHDRAWAL_REVERSAL``), so the column **must be widened** or the
first transfer/withdrawal hold fails at runtime with
``StringDataRightTruncationError``. This migration widens it to 32.

**Money.** ``amount``/``fee`` are ``BigInteger`` **Rial** integers (ADR-012),
never float/Decimal.

Revision ID: wal1
Revises: m7n8o9p0q1r2, rmtheme1, n8o9p0q1r2s3
Create Date: 2026-10-07
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "wal1"
down_revision = ("m7n8o9p0q1r2", "rmtheme1", "n8o9p0q1r2s3")
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Widen wallet_transactions.type from VARCHAR(10) to VARCHAR(32) so the new
    # longer member names (TRANSFER_OUT, WITHDRAWAL_REVERSAL, …) fit. See the
    # module docstring: native_enum=False sizes the column to the longest name
    # at creation time.
    op.alter_column(
        "wallet_transactions",
        "type",
        existing_type=sa.String(length=10),
        type_=sa.String(length=32),
        existing_nullable=False,
    )

    # ── Withdrawal requests ────────────────────────────────────────────────
    op.create_table(
        "wallet_withdrawal_requests",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING_REVIEW",
                "APPROVED",
                "REJECTED",
                "PAID",
                name="withdrawal_status_enum",
                native_enum=False,
            ),
            server_default=sa.text("'PENDING_REVIEW'::character varying"),
            nullable=False,
        ),
        sa.Column("iban", sa.String(length=34), nullable=True),
        sa.Column("card_number", sa.String(length=20), nullable=True),
        sa.Column("account_holder_name", sa.String(length=200), nullable=True),
        sa.Column("wallet_transaction_id", sa.UUID(), nullable=True),
        sa.Column("reviewed_by", sa.UUID(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("admin_notes", sa.Text(), nullable=True),
        sa.Column("payout_reference", sa.String(length=255), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("idempotency_key", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_wallet_withdrawal_requests_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["reviewed_by"],
            ["users.id"],
            name=op.f("fk_wallet_withdrawal_requests_reviewed_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_wallet_withdrawal_requests")),
        sa.UniqueConstraint(
            "idempotency_key",
            name=op.f("uq_wallet_withdrawal_requests_idempotency_key"),
        ),
    )
    op.create_index(
        "ix_wallet_withdrawal_requests_user_id",
        "wallet_withdrawal_requests",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_wallet_withdrawal_requests_status",
        "wallet_withdrawal_requests",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_wallet_withdrawal_requests_created_at",
        "wallet_withdrawal_requests",
        ["created_at"],
        unique=False,
    )

    # ── P2P transfers ──────────────────────────────────────────────────────
    op.create_table(
        "wallet_transfers",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("from_user_id", sa.UUID(), nullable=False),
        sa.Column("to_user_id", sa.UUID(), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("fee", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("journal_entry_id", sa.UUID(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["from_user_id"],
            ["users.id"],
            name=op.f("fk_wallet_transfers_from_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["to_user_id"],
            ["users.id"],
            name=op.f("fk_wallet_transfers_to_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_wallet_transfers")),
        sa.UniqueConstraint(
            "idempotency_key", name=op.f("uq_wallet_transfers_idempotency_key")
        ),
    )
    op.create_index(
        "ix_wallet_transfers_from_user_id", "wallet_transfers", ["from_user_id"], unique=False
    )
    op.create_index(
        "ix_wallet_transfers_to_user_id", "wallet_transfers", ["to_user_id"], unique=False
    )
    op.create_index(
        "ix_wallet_transfers_created_at", "wallet_transfers", ["created_at"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_wallet_transfers_created_at", table_name="wallet_transfers")
    op.drop_index("ix_wallet_transfers_to_user_id", table_name="wallet_transfers")
    op.drop_index("ix_wallet_transfers_from_user_id", table_name="wallet_transfers")
    op.drop_table("wallet_transfers")

    op.drop_index(
        "ix_wallet_withdrawal_requests_created_at", table_name="wallet_withdrawal_requests"
    )
    op.drop_index(
        "ix_wallet_withdrawal_requests_status", table_name="wallet_withdrawal_requests"
    )
    op.drop_index(
        "ix_wallet_withdrawal_requests_user_id", table_name="wallet_withdrawal_requests"
    )
    op.drop_table("wallet_withdrawal_requests")

    # Restore the original VARCHAR(10) width. Safe because the four new member
    # names never appear once the new tables and this revision are gone — the
    # downgrade is only reachable after those rows are removed.
    op.alter_column(
        "wallet_transactions",
        "type",
        existing_type=sa.String(length=32),
        type_=sa.String(length=10),
        existing_nullable=False,
    )
