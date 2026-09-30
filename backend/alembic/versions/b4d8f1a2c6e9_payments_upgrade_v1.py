"""Payments upgrade v1: saved cards (tokenization), installment plans, split tender.

ERP benchmark gap analysis (feature #6 Payments, P1 — scoped IMPLEMENT):

- ``saved_payment_methods``: card-on-file references. Stores ONLY the
  gateway's opaque token plus display metadata (masked PAN, last4, Jalali
  expiry label). No PAN/CVV column exists — that is the point of the table.
  Partial unique index enforces one default per user.
- ``installment_plans``: schedule of integer-Rial installments on an order.
  The schedule JSONB holds ``[{due_date_jalali, due_date, amount_rial,
  status, paid_at, is_prepayment}]``; ``first + sum(rest) == total`` is
  asserted in the service before insert. ``uq_installment_plans_order_id``
  (not partial — unlike the existing reporting_saved_reports precedent there
  is no soft-delete here) keeps one live plan per order.
- ``payment_allocations``: split-tender slices linking one payment to one
  order, with ``uq_payment_allocations_payment_id`` and a partial unique index
  ``uq_payment_allocations_one_completing_per_order`` that makes exactly-once
  order completion a database constraint rather than a code convention.

Additive only: no existing table is altered, so the single-payment flow and
the existing refund flow are untouched.

Revision ID: b4d8f1a2c6e9
Revises: a9c1e3f5b7d9
Create Date: 2026-09-25 00:40:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "b4d8f1a2c6e9"
down_revision = "a9c1e3f5b7d9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. saved_payment_methods ──────────────────────────────────────────
    op.create_table(
        "saved_payment_methods",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("token", sa.String(length=255), nullable=False),
        sa.Column("masked_pan", sa.String(length=30), nullable=True),
        sa.Column("last4", sa.String(length=4), nullable=True),
        sa.Column("expiry_jalali", sa.String(length=10), nullable=True),
        sa.Column("card_holder_name", sa.String(length=150), nullable=True),
        sa.Column("bank_name", sa.String(length=100), nullable=True),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="ACTIVE",
        ),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_reason", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_saved_payment_methods_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_saved_payment_methods")),
    )
    op.create_index(
        "ix_saved_payment_methods_user_id", "saved_payment_methods", ["user_id"], unique=False
    )
    op.create_index(
        "ix_saved_payment_methods_provider", "saved_payment_methods", ["provider"], unique=False
    )
    # A gateway token identifies one card globally; two rows holding the same
    # token would let one customer's delete silently orphan another's card.
    op.create_index(
        "uq_saved_payment_methods_provider_token",
        "saved_payment_methods",
        ["provider", "token"],
        unique=True,
    )
    # One default per user, enforced by the database under concurrency.
    op.create_index(
        "uq_saved_payment_methods_one_default",
        "saved_payment_methods",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("is_default = true AND is_active = true"),
    )

    # ── 2. installment_plans ──────────────────────────────────────────────
    op.create_table(
        "installment_plans",
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("first_payment_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("total_rial", sa.BigInteger(), nullable=False),
        sa.Column("num_installments", sa.Integer(), nullable=False),
        sa.Column("first_installment_rial", sa.BigInteger(), nullable=False),
        sa.Column("schedule", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("next_due_date", sa.Date(), nullable=True),
        sa.Column("paid_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "created_by_gateway", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("canceled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_reason", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name=op.f("fk_installment_plans_order_id_orders"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_installment_plans_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["first_payment_id"],
            ["payments.id"],
            name=op.f("fk_installment_plans_first_payment_id_payments"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_installment_plans")),
        sa.UniqueConstraint("order_id", name="uq_installment_plans_order_id"),
        # Integer-Rial guards mirror the money-integrity constraints migration
        # a7f2c91d4e08 established for the other financial tables.
        sa.CheckConstraint("total_rial > 0", name="ck_installment_plans_total_positive"),
        sa.CheckConstraint(
            "first_installment_rial > 0",
            name="ck_installment_plans_first_positive",
        ),
        sa.CheckConstraint(
            "first_installment_rial <= total_rial",
            name="ck_installment_plans_first_within_total",
        ),
        sa.CheckConstraint(
            "num_installments >= 2 AND num_installments <= 24",
            name="ck_installment_plans_count_range",
        ),
    )
    op.create_index("ix_installment_plans_user_id", "installment_plans", ["user_id"], unique=False)
    op.create_index(
        "ix_installment_plans_provider", "installment_plans", ["provider"], unique=False
    )
    op.create_index("ix_installment_plans_status", "installment_plans", ["status"], unique=False)

    # ── 3. payment_allocations ────────────────────────────────────────────
    op.create_table(
        "payment_allocations",
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("payment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("amount_rial", sa.BigInteger(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column(
            "is_completing", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("idempotency_key", sa.String(length=255), nullable=True),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("refunded_rial", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("wallet_transaction_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name=op.f("fk_payment_allocations_order_id_orders"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["payment_id"],
            ["payments.id"],
            name=op.f("fk_payment_allocations_payment_id_payments"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_payment_allocations")),
        sa.UniqueConstraint("payment_id", name="uq_payment_allocations_payment_id"),
        sa.CheckConstraint(
            "amount_rial > 0", name="ck_payment_allocations_amount_positive"
        ),
        sa.CheckConstraint(
            "refunded_rial >= 0 AND refunded_rial <= amount_rial",
            name="ck_payment_allocations_refunded_within_amount",
        ),
    )
    op.create_index(
        "ix_payment_allocations_order_id", "payment_allocations", ["order_id"], unique=False
    )
    op.create_index(
        "ix_payment_allocations_status", "payment_allocations", ["status"], unique=False
    )
    op.create_index(
        "ix_payment_allocations_provider", "payment_allocations", ["provider"], unique=False
    )
    # Exactly-once completion: at most one allocation per order may carry the
    # completing marker, so a duplicate completion is a constraint violation.
    op.create_index(
        "uq_payment_allocations_one_completing_per_order",
        "payment_allocations",
        ["order_id"],
        unique=True,
        postgresql_where=sa.text("is_completing = true"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_payment_allocations_one_completing_per_order", table_name="payment_allocations"
    )
    op.drop_index("ix_payment_allocations_provider", table_name="payment_allocations")
    op.drop_index("ix_payment_allocations_status", table_name="payment_allocations")
    op.drop_index("ix_payment_allocations_order_id", table_name="payment_allocations")
    op.drop_table("payment_allocations")

    op.drop_index("ix_installment_plans_status", table_name="installment_plans")
    op.drop_index("ix_installment_plans_provider", table_name="installment_plans")
    op.drop_index("ix_installment_plans_user_id", table_name="installment_plans")
    op.drop_table("installment_plans")

    op.drop_index("uq_saved_payment_methods_one_default", table_name="saved_payment_methods")
    op.drop_index("uq_saved_payment_methods_provider_token", table_name="saved_payment_methods")
    op.drop_index("ix_saved_payment_methods_provider", table_name="saved_payment_methods")
    op.drop_index("ix_saved_payment_methods_user_id", table_name="saved_payment_methods")
    op.drop_table("saved_payment_methods")
