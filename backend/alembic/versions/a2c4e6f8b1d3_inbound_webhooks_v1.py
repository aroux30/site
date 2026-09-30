"""Inbound webhooks v1: generic signed receiver for external systems.

ERP benchmark gap analysis (feature #4 API/webhooks, P1). The platform had
outbound webhooks and per-gateway payment callbacks, but no *general* inbound
receiver — an ERP/accounting connector or messaging gateway had nowhere to
POST events with signature verification and duplicate protection.

- ``inbound_webhook_endpoints``: one row per external system, with an
  AES-256-GCM encrypted signing secret (verification needs the raw key back,
  so a hash would not work) and an optional IP allowlist.
- ``inbound_webhook_deliveries``: every received call, *including refusals* —
  the rejected rows are the security audit trail.

Revision ID: a2c4e6f8b1d3
Revises: f1b3d5e7a9c2
Create Date: 2026-09-25 04:20:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "a2c4e6f8b1d3"
down_revision = "f1b3d5e7a9c2"
branch_labels = None
depends_on = None


def upgrade() -> None:
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
    # Idempotency lookups filter by endpoint + key; a composite index is what
    # keeps the duplicate check O(log n) as the table grows.
    op.create_index(
        "ix_inbound_webhook_deliveries_idempotency",
        "inbound_webhook_deliveries",
        ["endpoint_id", "idempotency_key"],
    )


def downgrade() -> None:
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
