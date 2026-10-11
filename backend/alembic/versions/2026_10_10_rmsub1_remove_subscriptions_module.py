"""Remove the subscriptions module (recurring plans: tables + permissions).

The «اشتراک‌های دوره‌ای» (recurring subscription plans) module was retired on
2026-10-10 by operator decision: a general e-commerce store does not use
recurring billing plans — the storefront sells one-off orders, and the B2B
partner flow (API keys + pre-paid credit) covers the wholesale side. It was
verified to be unused in practice:

- all three tables were empty at removal time (0 subscriptions, 0 items,
  0 billings — verified against the live database);
- no order ever originated from a subscription cycle (0 orders carry the
  cycle's notes marker);
- the Celery beat entry (``bill-due-subscriptions``, every 15 min) had never
  written a billing row — the module shipped with a MissingGreenlet bug that
  made every run count as an error (fixed earlier on 2026-10-10, then the
  module retired the same day);
- no FK from any other table points into the three tables (checked via
  pg_constraint).

Decision record: ``_archived/subscriptions-removal-2026-10-10/README.md``.
Removed code is archived under the same folder. ``downgrade()`` recreates
the full schema (three tables, constraints, indexes) and both permission
rows, so the removal is reversible.

Revision ID: rmsub1
Revises: rmtaxengine1
Create Date: 2026-10-10
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "rmsub1"
down_revision = "rmtaxengine1"
branch_labels = None
depends_on = None

#: The permission rows as they existed at removal (verified against the live
#: database before dropping — ids are the real ones, pinned so a downgrade
#: restores the exact rows the removed code referenced).
_PERMISSIONS = (
    {
        "id": "56a0f445-086b-4120-bac8-93abe7378baf",
        "slug": "subscriptions:read",
        "resource": "subscriptions",
        "action": "read",
        "name": "مشاهده اشتراک‌ها",
        "description": "مشاهده فهرست و جزئیات اشتراک‌های کاربران و تاریخچه صورتحساب دوره‌ها",
    },
    {
        "id": "1550261e-849d-4081-a172-93ef492a3081",
        "slug": "subscriptions:write",
        "resource": "subscriptions",
        "action": "write",
        "name": "مدیریت اشتراک‌ها",
        "description": "اجرای دستی دوره صورتحساب و عملیات مدیریتی اشتراک‌ها",
    },
)


def upgrade() -> None:
    # Children before parents: items and billings hold FKs into subscriptions.
    op.drop_index("ix_subscription_items_subscription_id", table_name="subscription_items")
    op.drop_table("subscription_items")

    op.drop_index("ix_subscription_billings_period", table_name="subscription_billings")
    op.drop_index(
        "ix_subscription_billings_subscription_id", table_name="subscription_billings"
    )
    op.drop_table("subscription_billings")

    op.drop_index("ix_subscriptions_next_billing_at", table_name="subscriptions")
    op.drop_index("ix_subscriptions_status", table_name="subscriptions")
    op.drop_index("ix_subscriptions_user_id", table_name="subscriptions")
    op.drop_table("subscriptions")

    # The permissions leave with the feature they guarded. role_permissions
    # has ON DELETE CASCADE on permission_id, so the admin grants go too.
    op.execute(
        sa.text(
            "DELETE FROM permissions WHERE slug IN "
            "('subscriptions:read', 'subscriptions:write')"
        )
    )


def downgrade() -> None:
    # ── subscriptions (initial schema, d7f1b3c5e9a2) ───────────────────────
    op.create_table(
        "subscriptions",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            server_default=sa.text("'ACTIVE'"),
            nullable=False,
        ),
        sa.Column("interval", sa.String(length=32), nullable=False),
        sa.Column("interval_count", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("custom_interval_days", sa.Integer(), nullable=True),
        sa.Column(
            "saved_method_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("saved_payment_methods.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("total_per_cycle", sa.BigInteger(), nullable=False),
        sa.Column("shipping_address_snapshot", postgresql.JSONB(), nullable=True),
        sa.Column("notes", sa.String(length=2000), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("next_billing_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_billed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_reason", sa.String(length=500), nullable=True),
        sa.Column("failure_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name="pk_subscriptions"),
        sa.UniqueConstraint(
            "user_id", "idempotency_key", name="uq_subscriptions_user_idempotency"
        ),
        sa.CheckConstraint("interval_count > 0", name="ck_subscriptions_interval_count"),
        sa.CheckConstraint(
            "status::text = ANY (ARRAY['ACTIVE','PAUSED','PAST_DUE','CANCELLED','EXPIRED'])",
            name="ck_subscriptions_status",
        ),
        sa.CheckConstraint(
            '"interval"::text = ANY (ARRAY[\'WEEKLY\',\'MONTHLY\',\'QUARTERLY\',\'YEARLY\',\'CUSTOM_DAYS\'])',
            name="ck_subscriptions_interval",
        ),
    )
    op.create_index("ix_subscriptions_user_id", "subscriptions", ["user_id"])
    op.create_index("ix_subscriptions_status", "subscriptions", ["status"])
    op.create_index("ix_subscriptions_next_billing_at", "subscriptions", ["next_billing_at"])

    # ── subscription_items ─────────────────────────────────────────────────
    op.create_table(
        "subscription_items",
        sa.Column(
            "subscription_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("subscriptions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "variant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("product_variants.id", ondelete="RESTRICT"),
            nullable=False,
        ),
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
        sa.PrimaryKeyConstraint("id", name="pk_subscription_items"),
        sa.CheckConstraint("quantity > 0", name="ck_subscription_items_quantity_positive"),
        sa.CheckConstraint(
            "unit_price_rial >= 0", name="ck_subscription_items_price_non_negative"
        ),
    )
    op.create_index(
        "ix_subscription_items_subscription_id", "subscription_items", ["subscription_id"]
    )

    # ── subscription_billings ──────────────────────────────────────────────
    op.create_table(
        "subscription_billings",
        sa.Column(
            "subscription_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("subscriptions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("period_index", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default=sa.text("'PENDING'"),
            nullable=False,
        ),
        sa.Column("amount_rial", sa.BigInteger(), nullable=False),
        sa.Column(
            "order_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("orders.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "payment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("payments.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("attempt_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("last_error", sa.String(length=500), nullable=True),
        sa.Column("billed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "renewal_notified", sa.Boolean(), server_default=sa.text("false"), nullable=False
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
        sa.PrimaryKeyConstraint("id", name="pk_subscription_billings"),
        sa.UniqueConstraint(
            "subscription_id", "period_index", name="uq_subscription_billings_period"
        ),
        sa.CheckConstraint(
            "status::text = ANY (ARRAY['PENDING','PAID','FAILED','SKIPPED'])",
            name="ck_subscription_billings_status",
        ),
    )
    op.create_index(
        "ix_subscription_billings_subscription_id", "subscription_billings", ["subscription_id"]
    )
    op.create_index(
        "ix_subscription_billings_period", "subscription_billings", ["period_index"]
    )

    # ── permissions ────────────────────────────────────────────────────────
    for perm in _PERMISSIONS:
        op.execute(
            sa.text(
                "INSERT INTO permissions (id, slug, resource, action, name, description) "
                "VALUES (CAST(:id AS uuid), :slug, :resource, :action, :name, :description) "
                "ON CONFLICT (slug) DO NOTHING"
            ).bindparams(**perm)
        )
    # Grant both to the super-admin role, as they were before removal.
    op.execute(
        sa.text(
            "INSERT INTO role_permissions (id, role_id, permission_id, created_at, updated_at) "
            "SELECT gen_random_uuid(), r.id, p.id, now(), now() FROM roles r, permissions p "
            "WHERE r.name = 'مدیر سیستم' "
            "AND p.slug IN ('subscriptions:read', 'subscriptions:write') "
            "AND NOT EXISTS (SELECT 1 FROM role_permissions rp "
            "  WHERE rp.role_id = r.id AND rp.permission_id = p.id)"
        )
    )
