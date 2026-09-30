"""Subscriptions v1: recurring order plans and their billing history.

ERP benchmark gap analysis (feature #30 Recurring/subscriptions, P1):

- ``subscriptions``: a plan (what to buy, how often, which card) plus its
  schedule. Prices are snapshotted at subscribe time so a catalog price change
  never silently re-prices an active plan.
- ``subscription_items``: the plan's lines with their agreed integer-Rial
  unit prices.
- ``subscription_billings``: one row per billing cycle attempted. The unique
  ``(subscription_id, period_index)`` is what makes a retried Celery run safe
  — a duplicate tick finds the row and returns it instead of charging again.

Additive only: no existing table is altered. Depends on
``saved_payment_methods`` (payments upgrade v1) for the card reference, and on
``orders``/``payments`` for the artifacts each cycle produces.

Revision ID: d7f1b3c5e9a2
Revises: c5e9a2b3d7f1
Create Date: 2026-09-25 02:10:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "d7f1b3c5e9a2"
down_revision = "c5e9a2b3d7f1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. subscriptions ──────────────────────────────────────────────────
    op.create_table(
        "subscriptions",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="ACTIVE"),
        sa.Column("interval", sa.String(length=32), nullable=False),
        sa.Column("interval_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("custom_interval_days", sa.Integer(), nullable=True),
        sa.Column("saved_method_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("total_per_cycle", sa.BigInteger(), nullable=False),
        sa.Column("shipping_address_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("notes", sa.String(length=2000), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("next_billing_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_billed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_reason", sa.String(length=500), nullable=True),
        sa.Column("failure_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("idempotency_key", sa.String(length=255), nullable=True),
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
        sa.CheckConstraint("interval_count > 0", name=op.f("ck_subscriptions_interval_count")),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'PAUSED', 'PAST_DUE', 'CANCELLED', 'EXPIRED')",
            name=op.f("ck_subscriptions_status"),
        ),
        sa.CheckConstraint(
            "interval IN ('WEEKLY', 'MONTHLY', 'QUARTERLY', 'YEARLY', 'CUSTOM_DAYS')",
            name=op.f("ck_subscriptions_interval"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_subscriptions_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["saved_method_id"],
            ["saved_payment_methods.id"],
            name=op.f("fk_subscriptions_saved_method_id_saved_payment_methods"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_subscriptions")),
        sa.UniqueConstraint(
            "user_id",
            "idempotency_key",
            name="uq_subscriptions_user_idempotency",
        ),
    )
    op.create_index("ix_subscriptions_user_id", "subscriptions", ["user_id"])
    op.create_index("ix_subscriptions_status", "subscriptions", ["status"])
    op.create_index(
        "ix_subscriptions_next_billing_at", "subscriptions", ["next_billing_at"]
    )

    # ── 2. subscription_items ─────────────────────────────────────────────
    op.create_table(
        "subscription_items",
        sa.Column("subscription_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("variant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_name", sa.String(length=500), nullable=False),
        sa.Column("sku", sa.String(length=100), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price_rial", sa.BigInteger(), nullable=False),
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
        sa.CheckConstraint(
            "quantity > 0", name=op.f("ck_subscription_items_quantity_positive")
        ),
        sa.CheckConstraint(
            "unit_price_rial >= 0", name=op.f("ck_subscription_items_price_non_negative")
        ),
        sa.ForeignKeyConstraint(
            ["subscription_id"],
            ["subscriptions.id"],
            name=op.f("fk_subscription_items_subscription_id_subscriptions"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["variant_id"],
            ["product_variants.id"],
            name=op.f("fk_subscription_items_variant_id_product_variants"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_subscription_items")),
    )
    op.create_index(
        "ix_subscription_items_subscription_id", "subscription_items", ["subscription_id"]
    )

    # ── 3. subscription_billings ──────────────────────────────────────────
    op.create_table(
        "subscription_billings",
        sa.Column("subscription_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("period_index", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="PENDING"),
        sa.Column("amount_rial", sa.BigInteger(), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("payment_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.String(length=500), nullable=True),
        sa.Column("billed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "renewal_notified", sa.Boolean(), nullable=False, server_default=sa.text("false")
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
        sa.CheckConstraint(
            "status IN ('PENDING', 'PAID', 'FAILED', 'SKIPPED')",
            name=op.f("ck_subscription_billings_status"),
        ),
        sa.ForeignKeyConstraint(
            ["subscription_id"],
            ["subscriptions.id"],
            name=op.f("fk_subscription_billings_subscription_id_subscriptions"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name=op.f("fk_subscription_billings_order_id_orders"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["payment_id"],
            ["payments.id"],
            name=op.f("fk_subscription_billings_payment_id_payments"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_subscription_billings")),
        # The idempotency guarantee: one billing row per cycle, ever.
        sa.UniqueConstraint(
            "subscription_id",
            "period_index",
            name="uq_subscription_billings_period",
        ),
    )
    op.create_index(
        "ix_subscription_billings_subscription_id",
        "subscription_billings",
        ["subscription_id"],
    )
    op.create_index(
        "ix_subscription_billings_period", "subscription_billings", ["period_index"]
    )


def downgrade() -> None:
    op.drop_index("ix_subscription_billings_period", table_name="subscription_billings")
    op.drop_index(
        "ix_subscription_billings_subscription_id", table_name="subscription_billings"
    )
    op.drop_table("subscription_billings")

    op.drop_index("ix_subscription_items_subscription_id", table_name="subscription_items")
    op.drop_table("subscription_items")

    op.drop_index("ix_subscriptions_next_billing_at", table_name="subscriptions")
    op.drop_index("ix_subscriptions_status", table_name="subscriptions")
    op.drop_index("ix_subscriptions_user_id", table_name="subscriptions")
    op.drop_table("subscriptions")
