"""Remove the accounting journal + fiscal-period close (decision 2026-10-04).

The owner asked for «دفتر روزنامه» and «بستن دوره مالی» to be deleted — a
retail storefront's money record is the order/payment/wallet tables, and the
double-entry feed was a decorative second copy nothing downstream read. The
code is archived under ``_archived/inbound-journal-periods-2026-10-04/`` and
this migration drops its four tables.

All four tables were verified **empty at removal time** (live probe
2026-10-04: ``journal_entries`` = 0, ``journal_lines`` = 0,
``journal_sequences`` = 0, ``accounting_periods`` = 0 rows), so no business
data is lost. ``downgrade()`` recreates the full schema (columns, FKs,
check constraints, unique constraints, every index) exactly as
``a9c1e3f5b7d9`` created it, so the removal is reversible.

Kept on purpose: the ``accounts`` table (chart of accounts «کدینگ حساب‌ها»)
and its ``accounting:read`` / ``accounting:write`` permissions — only
``journal_lines`` referenced ``accounts``, and that FK dies with the table.

Revision ID: rmjournal1
Revises: rminbound1
Create Date: 2026-10-04
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "rmjournal1"
down_revision = "rminbound1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Children before parents: journal_lines holds FKs into journal_entries
    # and accounts; journal_entries has a self-FK (reversal_of_id).
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


def downgrade() -> None:
    """Recreate the four tables exactly as ``a9c1e3f5b7d9`` defined them."""
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
