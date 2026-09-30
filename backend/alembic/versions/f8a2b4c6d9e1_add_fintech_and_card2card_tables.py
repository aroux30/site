"""Add card transfer receipts, direct invoices, and gateway settings (Karta Phase 3/5).

Revision ID: f8a2b4c6d9e1
Revises: e7f1a3b8c5d2
Create Date: 2026-09-12 19:00:00

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "f8a2b4c6d9e1"
down_revision = "e7f1a3b8c5d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. card_transfer_receipts table
    op.create_table(
        "card_transfer_receipts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("order_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("tracking_code", sa.String(length=100), nullable=False),
        sa.Column("source_card_last4", sa.String(length=4), nullable=False),
        sa.Column("destination_card_number", sa.String(length=20), nullable=True),
        sa.Column("receipt_image_url", sa.String(length=500), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending_review"),
        sa.Column("admin_notes", sa.Text(), nullable=True),
        sa.Column("reviewed_by", sa.UUID(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], name=op.f("fk_card_transfer_receipts_order_id_orders"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_card_transfer_receipts_user_id_users"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"], name=op.f("fk_card_transfer_receipts_reviewed_by_users"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_card_transfer_receipts")),
    )
    op.create_index("ix_card_transfer_receipts_order_id", "card_transfer_receipts", ["order_id"], unique=False)
    op.create_index("ix_card_transfer_receipts_user_id", "card_transfer_receipts", ["user_id"], unique=False)
    op.create_index("ix_card_transfer_receipts_status", "card_transfer_receipts", ["status"], unique=False)
    op.create_index("ix_card_transfer_receipts_tracking_code", "card_transfer_receipts", ["tracking_code"], unique=False)

    # 2. direct_invoices table
    op.create_table(
        "direct_invoices",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("invoice_number", sa.String(length=50), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("title", sa.String(length=250), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("payer_name", sa.String(length=150), nullable=True),
        sa.Column("payer_mobile", sa.String(length=20), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="unpaid"),
        sa.Column("payment_id", sa.UUID(), nullable=True),
        sa.Column("expire_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_direct_invoices_user_id_users"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["payment_id"], ["payments.id"], name=op.f("fk_direct_invoices_payment_id_payments"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_direct_invoices")),
        sa.UniqueConstraint("invoice_number", name=op.f("uq_direct_invoices_invoice_number")),
    )
    op.create_index("ix_direct_invoices_invoice_number", "direct_invoices", ["invoice_number"], unique=False)
    op.create_index("ix_direct_invoices_user_id", "direct_invoices", ["user_id"], unique=False)
    op.create_index("ix_direct_invoices_status", "direct_invoices", ["status"], unique=False)

    # 3. gateway_settings table
    op.create_table(
        "gateway_settings",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("provider_key", sa.String(length=50), nullable=False),
        sa.Column("title_fa", sa.String(length=100), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("priority", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("min_amount", sa.BigInteger(), nullable=False, server_default=sa.text("10000")),
        sa.Column("max_amount", sa.BigInteger(), nullable=False, server_default=sa.text("500000000")),
        sa.Column("credentials", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_gateway_settings")),
        sa.UniqueConstraint("provider_key", name=op.f("uq_gateway_settings_provider_key")),
    )
    op.create_index("ix_gateway_settings_provider_key", "gateway_settings", ["provider_key"], unique=False)
    op.create_index("ix_gateway_settings_is_active", "gateway_settings", ["is_active"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_gateway_settings_is_active", table_name="gateway_settings")
    op.drop_index("ix_gateway_settings_provider_key", table_name="gateway_settings")
    op.drop_table("gateway_settings")
    op.drop_index("ix_direct_invoices_status", table_name="direct_invoices")
    op.drop_index("ix_direct_invoices_user_id", table_name="direct_invoices")
    op.drop_index("ix_direct_invoices_invoice_number", table_name="direct_invoices")
    op.drop_table("direct_invoices")
    op.drop_index("ix_card_transfer_receipts_tracking_code", table_name="card_transfer_receipts")
    op.drop_index("ix_card_transfer_receipts_status", table_name="card_transfer_receipts")
    op.drop_index("ix_card_transfer_receipts_user_id", table_name="card_transfer_receipts")
    op.drop_index("ix_card_transfer_receipts_order_id", table_name="card_transfer_receipts")
    op.drop_table("card_transfer_receipts")
