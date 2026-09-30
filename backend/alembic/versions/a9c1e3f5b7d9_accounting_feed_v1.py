"""Accounting feed v1: chart of accounts, journal entries, periods, sequences.

ERP benchmark gap analysis (feature #20 Accounting/GL, P1 — scoped IMPLEMENT):

- ``accounts``: minimal chart of accounts (code / name_fa / type / parent /
  is_active), seeded idempotently with an Iranian-standard skeleton.
- ``journal_entries``: double-entry header with per-Jalali-period gapless
  numbering (JE-1404-000123), source provenance, SHA-256 tamper-evident hash
  chain, posted lifecycle, reversal link, and a unique
  ``(source_type, source_id, entry_type)`` key so event-driven posting is
  idempotent per source.
- ``journal_lines``: one side of one account movement; check constraints
  enforce non-negative integer Rial amounts and that exactly one of
  debit/credit is non-zero.
- ``journal_sequences``: per-fiscal-period counter row locked FOR UPDATE at
  post time (same protocol as ``invoice_sequences``).
- ``accounting_periods``: Jalali period close record — status, closer, and a
  control-total snapshot of the locked period.

Revision ID: a9c1e3f5b7d9
Revises: wa1r2e3h4o5u6
Create Date: 2026-09-24 23:58:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "a9c1e3f5b7d9"
down_revision = "wa1r2e3h4o5u6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "accounts",
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("name_fa", sa.String(length=200), nullable=False),
        sa.Column(
            "type",
            sa.Enum(
                "ASSET",
                "LIABILITY",
                "EQUITY",
                "REVENUE",
                "EXPENSE",
                name="account_type_enum",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "parent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("accounts.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_accounts_code"),
    )
    op.create_index("ix_accounts_type", "accounts", ["type"])
    op.create_index("ix_accounts_parent_id", "accounts", ["parent_id"])
    op.create_index("ix_accounts_is_active", "accounts", ["is_active"])

    op.create_table(
        "journal_entries",
        sa.Column("number", sa.String(length=32), nullable=True),
        sa.Column("fiscal_period", sa.String(length=8), nullable=True),
        sa.Column("entry_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "source_type",
            sa.Enum(
                "ORDER",
                "PAYMENT",
                "REFUND",
                "WALLET",
                "SETTLEMENT",
                "MANUAL",
                name="journal_source_type_enum",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("source_id", sa.String(length=100), nullable=True),
        sa.Column("entry_type", sa.String(length=50), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "DRAFT",
                "POSTED",
                "REVERSED",
                name="journal_entry_status_enum",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("hash", sa.String(length=64), nullable=True),
        sa.Column("previous_hash", sa.String(length=64), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "reversal_of_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("journal_entries.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("reversal_reason", sa.Text(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=255), nullable=True),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("number", name="uq_journal_entries_number"),
        sa.UniqueConstraint("idempotency_key", name="uq_journal_entries_idempotency_key"),
        sa.UniqueConstraint(
            "source_type", "source_id", "entry_type", name="uq_journal_entries_source"
        ),
    )
    op.create_index("ix_journal_entries_fiscal_period", "journal_entries", ["fiscal_period"])
    op.create_index("ix_journal_entries_status", "journal_entries", ["status"])
    op.create_index("ix_journal_entries_source_type", "journal_entries", ["source_type"])
    op.create_index("ix_journal_entries_entry_date", "journal_entries", ["entry_date"])
    op.create_index("ix_journal_entries_posted_at", "journal_entries", ["posted_at"])
    op.create_index(
        "ix_journal_entries_idempotency_key", "journal_entries", ["idempotency_key"]
    )

    op.create_table(
        "journal_lines",
        sa.Column(
            "entry_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("journal_entries.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("accounts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("debit_rial", sa.BigInteger(), nullable=False),
        sa.Column("credit_rial", sa.BigInteger(), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
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
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "debit_rial >= 0 AND credit_rial >= 0", name="ck_journal_lines_nonneg"
        ),
        sa.CheckConstraint(
            "(debit_rial > 0 AND credit_rial = 0) OR (credit_rial > 0 AND debit_rial = 0)",
            name="ck_journal_lines_one_sided",
        ),
    )
    op.create_index("ix_journal_lines_entry_id", "journal_lines", ["entry_id"])
    op.create_index("ix_journal_lines_account_id", "journal_lines", ["account_id"])

    op.create_table(
        "journal_sequences",
        sa.Column("fiscal_period", sa.String(length=8), nullable=False),
        sa.Column("last_value", sa.BigInteger(), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fiscal_period", name="uq_journal_sequences_period"),
    )

    op.create_table(
        "accounting_periods",
        sa.Column("fiscal_period", sa.String(length=8), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "OPEN",
                "CLOSED",
                name="accounting_period_status_enum",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "closed_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("entry_count", sa.Integer(), nullable=False),
        sa.Column("debit_total_rial", sa.BigInteger(), nullable=False),
        sa.Column("credit_total_rial", sa.BigInteger(), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fiscal_period", name="uq_accounting_periods_period"),
    )
    op.create_index("ix_accounting_periods_status", "accounting_periods", ["status"])


def downgrade() -> None:
    op.drop_index("ix_accounting_periods_status", table_name="accounting_periods")
    op.drop_table("accounting_periods")
    op.drop_table("journal_sequences")
    op.drop_index("ix_journal_lines_account_id", table_name="journal_lines")
    op.drop_index("ix_journal_lines_entry_id", table_name="journal_lines")
    op.drop_table("journal_lines")
    op.drop_index("ix_journal_entries_idempotency_key", table_name="journal_entries")
    op.drop_index("ix_journal_entries_posted_at", table_name="journal_entries")
    op.drop_index("ix_journal_entries_entry_date", table_name="journal_entries")
    op.drop_index("ix_journal_entries_source_type", table_name="journal_entries")
    op.drop_index("ix_journal_entries_status", table_name="journal_entries")
    op.drop_index("ix_journal_entries_fiscal_period", table_name="journal_entries")
    op.drop_table("journal_entries")
    op.drop_index("ix_accounts_is_active", table_name="accounts")
    op.drop_index("ix_accounts_parent_id", table_name="accounts")
    op.drop_index("ix_accounts_type", table_name="accounts")
    op.drop_table("accounts")
