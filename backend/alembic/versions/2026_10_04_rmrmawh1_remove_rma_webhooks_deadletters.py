"""Remove the RMA, outbound-webhook and dead-letter modules (decision 2026-10-04).

The owner asked for all three to be deleted outright — none has a use in a
retail storefront («هیچ اثری نمیخواهم»). The code is archived under
``_archived/rma-webhooks-deadletters-2026-10-04/`` and this migration drops
their tables.

Verified at removal time (live probe 2026-10-04):
- ``order_returns`` = 0 rows, ``order_return_items`` = 0 rows.
- ``webhook_endpoints`` = 22 rows, ``webhook_deliveries`` = 6 rows — all
  e2e test artifacts (``https://example.com/e2e-hook``).
- ``outbox_messages``: 5,691 pending ``webhook.*`` rows (fan-out from the
  content module that no longer has a dispatcher). Deleted here because the
  code that could ever process them is gone; leaving them would be a queue
  no consumer can drain. ``ReturnApproved``/``ReturnRefunded`` rows: none.

``downgrade()`` recreates the four tables exactly as ``c4d9e1a5f7b2``
(RMA) and ``m5n6o7p8q9r0`` (webhooks) defined them, so the schema change is
reversible. The deleted ``webhook.*`` outbox rows are data, not schema, and
are *not* restored — they were test-only fan-out traffic.

Not touched on purpose: the payment-gateway callback table
(``payment_webhook_events``, 719 rows) and the outbox infrastructure itself
(``outbox_messages`` table + ``OutboxStatus`` enum including DEAD_LETTER) —
those are live features the worker still needs.

Revision ID: rmrmawh1
Revises: rmpickup1
Create Date: 2026-10-04
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "rmrmawh1"
down_revision = "rmpickup1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Queue rows the removed dispatcher could never drain (test-only fan-out).
    op.execute("DELETE FROM outbox_messages WHERE event_type LIKE 'webhook.%'")
    op.execute(
        "DELETE FROM outbox_messages WHERE event_type IN ('ReturnApproved', 'ReturnRefunded')"
    )

    # Children before parents: items holds the FK into returns.
    op.drop_index("ix_order_return_items_return_id", table_name="order_return_items")
    op.drop_table("order_return_items")
    op.drop_index("ix_order_returns_status", table_name="order_returns")
    op.drop_index("ix_order_returns_user_id", table_name="order_returns")
    op.drop_index("ix_order_returns_order_id", table_name="order_returns")
    op.drop_table("order_returns")

    # Deliveries holds the FK into endpoints.
    op.drop_index("ix_webhook_deliveries_status_next", table_name="webhook_deliveries")
    op.drop_index("ix_webhook_deliveries_endpoint_id", table_name="webhook_deliveries")
    op.drop_table("webhook_deliveries")
    op.drop_table("webhook_endpoints")


def downgrade() -> None:
    """Recreate the four tables as ``c4d9e1a5f7b2`` / ``m5n6o7p8q9r0`` defined them."""
    op.create_table(
        "order_returns",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("rma_number", sa.String(length=32), nullable=False),
        sa.Column("order_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("admin_notes", sa.Text(), nullable=True),
        sa.Column("refund_amount", sa.BigInteger(), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("inspected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("refunded_at", sa.DateTime(timezone=True), nullable=True),
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
            name=op.f("fk_order_returns_order_id_orders"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_order_returns_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_order_returns")),
        sa.UniqueConstraint("rma_number", name=op.f("uq_order_returns_rma_number")),
    )
    op.create_index("ix_order_returns_order_id", "order_returns", ["order_id"], unique=False)
    op.create_index("ix_order_returns_user_id", "order_returns", ["user_id"], unique=False)
    op.create_index("ix_order_returns_status", "order_returns", ["status"], unique=False)

    op.create_table(
        "order_return_items",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("return_id", sa.UUID(), nullable=False),
        sa.Column("order_item_id", sa.UUID(), nullable=False),
        sa.Column("variant_id", sa.UUID(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=50), nullable=False),
        sa.Column("inspection_outcome", sa.String(length=50), nullable=True),
        sa.Column("customer_notes", sa.Text(), nullable=True),
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
            ["return_id"],
            ["order_returns.id"],
            name=op.f("fk_order_return_items_return_id_order_returns"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["order_item_id"],
            ["order_items.id"],
            name=op.f("fk_order_return_items_order_item_id_order_items"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["variant_id"],
            ["product_variants.id"],
            name=op.f("fk_order_return_items_variant_id_product_variants"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_order_return_items")),
        sa.CheckConstraint("quantity > 0", name=op.f("ck_order_return_items_quantity_positive")),
    )
    op.create_index("ix_order_return_items_return_id", "order_return_items", ["return_id"], unique=False)

    op.create_table(
        "webhook_endpoints",
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("url", sa.String(length=1000), nullable=False),
        sa.Column(
            "events",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'"),
            nullable=False,
        ),
        sa.Column("secret", sa.String(length=200), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
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
    )
    op.create_table(
        "webhook_deliveries",
        sa.Column("endpoint_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event", sa.String(length=100), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            server_default=sa.text("'PENDING'::character varying"),
            nullable=False,
        ),
        sa.Column("attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "next_attempt_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("response_status", sa.Integer(), nullable=True),
        sa.Column("last_error", sa.String(length=500), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["endpoint_id"], ["webhook_endpoints.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_webhook_deliveries_endpoint_id",
        "webhook_deliveries",
        ["endpoint_id"],
        unique=False,
    )
    op.create_index(
        "ix_webhook_deliveries_status_next",
        "webhook_deliveries",
        ["status", "next_attempt_at"],
        unique=False,
    )
