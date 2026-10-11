"""Remove the inbound webhook receiver module (decision 2026-10-04).

The owner asked for the «گیرنده‌های webhook» feature to be deleted outright —
it has no use in a retail storefront. The code is archived under
``_archived/inbound-journal-periods-2026-10-04/`` and this migration drops
its two tables.

Both tables were verified **empty at removal time** (live probe 2026-10-04:
``inbound_webhook_endpoints`` = 0 rows, ``inbound_webhook_deliveries`` = 0
rows), so no business data is lost. ``downgrade()`` recreates the full schema
(indexes, check constraint, FK) exactly as ``a2c4e6f8b1d3`` created it, so
the removal is reversible.

Not touched on purpose: the *outbound* webhook tables (``webhook_endpoints`` /
``webhook_deliveries``, 22 + 6 rows) and the payment-gateway callback table
(``payment_webhook_events``, 719 rows) — those are live features.

Revision ID: rminbound1
Revises: rminvoice1
Create Date: 2026-10-04
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "rminbound1"
down_revision = "rminvoice1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Children before parents: deliveries holds the FK into endpoints.
    op.drop_index(
        "ix_inbound_webhook_deliveries_idempotency",
        table_name="inbound_webhook_deliveries",
    )
    op.drop_index(
        "ix_inbound_webhook_deliveries_received_at",
        table_name="inbound_webhook_deliveries",
    )
    op.drop_index(
        "ix_inbound_webhook_deliveries_status", table_name="inbound_webhook_deliveries"
    )
    op.drop_index(
        "ix_inbound_webhook_deliveries_endpoint_id",
        table_name="inbound_webhook_deliveries",
    )
    op.drop_table("inbound_webhook_deliveries")

    op.drop_index(
        "ix_inbound_webhook_endpoints_is_active", table_name="inbound_webhook_endpoints"
    )
    op.drop_index(
        "ix_inbound_webhook_endpoints_name", table_name="inbound_webhook_endpoints"
    )
    op.drop_table("inbound_webhook_endpoints")


def downgrade() -> None:
    """Recreate both tables exactly as ``a2c4e6f8b1d3`` defined them."""
    op.create_table(
        "inbound_webhook_endpoints",
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("secret_encrypted", sa.Text(), nullable=False),
        sa.Column("ip_whitelist", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_received", sa.Integer(), nullable=False, server_default="0"),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_inbound_webhook_endpoints")),
        sa.UniqueConstraint("name", name="uq_inbound_webhook_endpoints_name"),
    )
    op.create_index(
        "ix_inbound_webhook_endpoints_name", "inbound_webhook_endpoints", ["name"]
    )
    op.create_index(
        "ix_inbound_webhook_endpoints_is_active",
        "inbound_webhook_endpoints",
        ["is_active"],
    )

    op.create_table(
        "inbound_webhook_deliveries",
        sa.Column("endpoint_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="RECEIVED"),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("idempotency_key", sa.String(length=255), nullable=True),
        sa.Column("source_ip", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=300), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
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
            "status IN ('RECEIVED', 'VERIFIED', 'REJECTED_SIGNATURE', "
            "'REJECTED_DUPLICATE', 'PROCESSED', 'FAILED')",
            name=op.f("ck_inbound_webhook_deliveries_status"),
        ),
        sa.ForeignKeyConstraint(
            ["endpoint_id"],
            ["inbound_webhook_endpoints.id"],
            name=op.f("fk_inbound_webhook_deliveries_endpoint_id_inbound_webhook_endpoints"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_inbound_webhook_deliveries")),
    )
    op.create_index(
        "ix_inbound_webhook_deliveries_endpoint_id",
        "inbound_webhook_deliveries",
        ["endpoint_id"],
    )
    op.create_index(
        "ix_inbound_webhook_deliveries_status", "inbound_webhook_deliveries", ["status"]
    )
    op.create_index(
        "ix_inbound_webhook_deliveries_received_at",
        "inbound_webhook_deliveries",
        ["received_at"],
    )
    op.create_index(
        "ix_inbound_webhook_deliveries_idempotency",
        "inbound_webhook_deliveries",
        ["endpoint_id", "idempotency_key"],
    )
