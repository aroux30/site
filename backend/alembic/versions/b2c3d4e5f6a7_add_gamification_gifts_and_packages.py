"""Add internal gift cards, lucky wheel prizes, gift try logs, and charge packages (Karta Phase 5/7).

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-09-12 20:00:00

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. internal_gift_cards table
    op.create_table(
        "internal_gift_cards",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("remaining_balance", sa.BigInteger(), nullable=False),
        sa.Column("card_template", sa.String(length=32), nullable=False, server_default="gold"),
        sa.Column("sender_name", sa.String(length=100), nullable=True),
        sa.Column("recipient_email", sa.String(length=255), nullable=True),
        sa.Column("recipient_phone", sa.String(length=20), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by_user_id", sa.UUID(), nullable=True),
        sa.Column("claimed_by_user_id", sa.UUID(), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], name=op.f("fk_internal_gift_cards_created_by_user_id_users"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["claimed_by_user_id"], ["users.id"], name=op.f("fk_internal_gift_cards_claimed_by_user_id_users"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_internal_gift_cards")),
        sa.UniqueConstraint("code", name=op.f("uq_internal_gift_cards_code")),
    )
    op.create_index("ix_internal_gift_cards_code", "internal_gift_cards", ["code"], unique=False)
    op.create_index("ix_internal_gift_cards_created_by", "internal_gift_cards", ["created_by_user_id"], unique=False)
    op.create_index("ix_internal_gift_cards_claimed_by", "internal_gift_cards", ["claimed_by_user_id"], unique=False)
    op.create_index("ix_internal_gift_cards_is_active", "internal_gift_cards", ["is_active"], unique=False)

    # 2. lucky_wheel_prizes table
    op.create_table(
        "lucky_wheel_prizes",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=150), nullable=False),
        sa.Column("prize_type", sa.String(length=32), nullable=False),
        sa.Column("value", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("probability_weight", sa.Integer(), nullable=False, server_default=sa.text("10")),
        sa.Column("icon", sa.String(length=100), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("max_claims_total", sa.Integer(), nullable=True),
        sa.Column("claimed_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_lucky_wheel_prizes")),
    )
    op.create_index("ix_lucky_wheel_prizes_is_active", "lucky_wheel_prizes", ["is_active"], unique=False)

    # 3. gift_try_logs table
    op.create_table(
        "gift_try_logs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("order_id", sa.UUID(), nullable=False),
        sa.Column("prize_id", sa.UUID(), nullable=True),
        sa.Column("prize_title", sa.String(length=150), nullable=False),
        sa.Column("prize_type", sa.String(length=50), nullable=False),
        sa.Column("awarded_value", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_gift_try_logs_user_id_users"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], name=op.f("fk_gift_try_logs_order_id_orders"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["prize_id"], ["lucky_wheel_prizes.id"], name=op.f("fk_gift_try_logs_prize_id_lucky_wheel_prizes"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_gift_try_logs")),
        sa.UniqueConstraint("order_id", name=op.f("uq_gift_try_logs_order_id")),
    )
    op.create_index("ix_gift_try_logs_user_id", "gift_try_logs", ["user_id"], unique=False)
    op.create_index("ix_gift_try_logs_order_id", "gift_try_logs", ["order_id"], unique=False)

    # 4. charge_packages table
    op.create_table(
        "charge_packages",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=100), nullable=False),
        sa.Column("pay_amount", sa.BigInteger(), nullable=False),
        sa.Column("credit_amount", sa.BigInteger(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("ordering", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_charge_packages")),
    )
    op.create_index("ix_charge_packages_is_active", "charge_packages", ["is_active"], unique=False)
    op.create_index("ix_charge_packages_ordering", "charge_packages", ["ordering"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_charge_packages_ordering", table_name="charge_packages")
    op.drop_index("ix_charge_packages_is_active", table_name="charge_packages")
    op.drop_table("charge_packages")
    op.drop_index("ix_gift_try_logs_order_id", table_name="gift_try_logs")
    op.drop_index("ix_gift_try_logs_user_id", table_name="gift_try_logs")
    op.drop_table("gift_try_logs")
    op.drop_index("ix_lucky_wheel_prizes_is_active", table_name="lucky_wheel_prizes")
    op.drop_table("lucky_wheel_prizes")
    op.drop_index("ix_internal_gift_cards_is_active", table_name="internal_gift_cards")
    op.drop_index("ix_internal_gift_cards_claimed_by", table_name="internal_gift_cards")
    op.drop_index("ix_internal_gift_cards_created_by", table_name="internal_gift_cards")
    op.drop_index("ix_internal_gift_cards_code", table_name="internal_gift_cards")
    op.drop_table("internal_gift_cards")
