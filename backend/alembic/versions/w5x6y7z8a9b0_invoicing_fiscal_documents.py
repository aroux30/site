"""Invoicing hardening v1: fiscal documents, lines, and per-period sequences.

ERP benchmark gap analysis (feature #2 Invoicing, P0):

- ``invoices``: fiscal document header (invoice / credit_note) with draft →
  posted → paid lifecycle, gapless per-Jalali-period numbering, totals and
  customer snapshots (JSONB), SHA-256 tamper-evident hash chain, archive
  pointer, and idempotency key.
- ``invoice_lines``: immutable line snapshots (integer Rial).
- ``invoice_sequences``: per (fiscal_period, doc_type) counter row locked
  FOR UPDATE at post time for gapless number allocation.

Revision ID: w5x6y7z8a9b0
Revises: v4w5x6y7z8a9
Create Date: 2026-09-24 23:30:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "w5x6y7z8a9b0"
down_revision = "v4w5x6y7z8a9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "invoices",
        sa.Column(
            "order_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("orders.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "type",
            sa.Enum("INVOICE", "CREDIT_NOTE", name="invoice_type_enum", native_enum=False),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "DRAFT", "POSTED", "PAID", "CANCELLED",
                name="invoice_status_enum",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("number", sa.String(length=32), nullable=True),
        sa.Column("fiscal_period", sa.String(length=8), nullable=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_reason", sa.Text(), nullable=True),
        sa.Column("totals", postgresql.JSONB(), nullable=False),
        sa.Column("customer", postgresql.JSONB(), nullable=False),
        sa.Column("hash", sa.String(length=64), nullable=True),
        sa.Column("previous_hash", sa.String(length=64), nullable=True),
        sa.Column(
            "credit_for_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("invoices.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("credit_reason", sa.Text(), nullable=True),
        sa.Column("archive_path", sa.String(length=500), nullable=True),
        sa.Column("archive_content_type", sa.String(length=100), nullable=True),
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
        sa.UniqueConstraint("number", name="uq_invoices_number"),
        sa.UniqueConstraint("idempotency_key", name="uq_invoices_idempotency_key"),
    )
    op.create_index("ix_invoices_order_id", "invoices", ["order_id"])
    op.create_index("ix_invoices_status", "invoices", ["status"])
    op.create_index("ix_invoices_fiscal_period", "invoices", ["fiscal_period"])
    op.create_index("ix_invoices_type", "invoices", ["type"])
    op.create_index("ix_invoices_issued_at", "invoices", ["issued_at"])
    op.create_index("ix_invoices_idempotency_key", "invoices", ["idempotency_key"])

    op.create_table(
        "invoice_lines",
        sa.Column(
            "invoice_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("invoices.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("product_name", sa.String(length=500), nullable=False),
        sa.Column("sku", sa.String(length=100), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.BigInteger(), nullable=False),
        sa.Column("total_price", sa.BigInteger(), nullable=False),
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
        sa.CheckConstraint("quantity >= 0", name="ck_invoice_lines_quantity_nonneg"),
    )
    op.create_index("ix_invoice_lines_invoice_id", "invoice_lines", ["invoice_id"])

    op.create_table(
        "invoice_sequences",
        sa.Column("fiscal_period", sa.String(length=8), nullable=False),
        sa.Column(
            "doc_type",
            sa.Enum("INVOICE", "CREDIT_NOTE", name="invoice_type_enum", native_enum=False),
            nullable=False,
        ),
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
        sa.UniqueConstraint("fiscal_period", "doc_type", name="uq_invoice_sequences_period_type"),
    )


def downgrade() -> None:
    op.drop_table("invoice_sequences")
    op.drop_index("ix_invoice_lines_invoice_id", table_name="invoice_lines")
    op.drop_table("invoice_lines")
    op.drop_index("ix_invoices_idempotency_key", table_name="invoices")
    op.drop_index("ix_invoices_issued_at", table_name="invoices")
    op.drop_index("ix_invoices_type", table_name="invoices")
    op.drop_index("ix_invoices_fiscal_period", table_name="invoices")
    op.drop_index("ix_invoices_status", table_name="invoices")
    op.drop_index("ix_invoices_order_id", table_name="invoices")
    op.drop_table("invoices")
