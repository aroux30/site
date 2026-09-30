"""Add user bank cards, failed attempts, and trust profiles (Karta Phase 1).

Revision ID: e7f1a3b8c5d2
Revises: d5e8f2a1b9c3
Create Date: 2026-09-12 18:30:00

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "e7f1a3b8c5d2"
down_revision = "d5e8f2a1b9c3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. user_bank_cards table
    op.create_table(
        "user_bank_cards",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("card_pan_masked", sa.String(length=20), nullable=False),
        sa.Column("card_pan_hash", sa.String(length=64), nullable=False),
        sa.Column("card_pan_encrypted", sa.String(length=255), nullable=False),
        sa.Column("iban", sa.String(length=30), nullable=True),
        sa.Column("bank_name", sa.String(length=100), nullable=True),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_user_bank_cards_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_bank_cards")),
    )
    op.create_index("ix_user_bank_cards_user_id", "user_bank_cards", ["user_id"], unique=False)
    op.create_index("ix_user_bank_cards_card_pan_hash", "user_bank_cards", ["card_pan_hash"], unique=False)
    op.create_index("ix_user_bank_cards_is_verified", "user_bank_cards", ["is_verified"], unique=False)

    # 2. failed_attempts table
    op.create_table(
        "failed_attempts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("identifier", sa.String(length=100), nullable=False),
        sa.Column("attempt_type", sa.String(length=32), nullable=False),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=300), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_failed_attempts")),
    )
    op.create_index("ix_failed_attempts_identifier", "failed_attempts", ["identifier"], unique=False)
    op.create_index("ix_failed_attempts_attempt_type", "failed_attempts", ["attempt_type"], unique=False)
    op.create_index("ix_failed_attempts_created_at", "failed_attempts", ["created_at"], unique=False)

    # 3. user_trust_profiles table
    op.create_table(
        "user_trust_profiles",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("is_trusted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("shahkar_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("risk_score", sa.Integer(), nullable=False, server_default=sa.text("50")),
        sa.Column("delayed_delivery_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("daily_spend_limit", sa.BigInteger(), nullable=False, server_default=sa.text("50000000")),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_user_trust_profiles_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_trust_profiles")),
        sa.UniqueConstraint("user_id", name=op.f("uq_user_trust_profiles_user_id")),
    )
    op.create_index("ix_user_trust_profiles_user_id", "user_trust_profiles", ["user_id"], unique=False)
    op.create_index("ix_user_trust_profiles_is_trusted", "user_trust_profiles", ["is_trusted"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_user_trust_profiles_is_trusted", table_name="user_trust_profiles")
    op.drop_index("ix_user_trust_profiles_user_id", table_name="user_trust_profiles")
    op.drop_table("user_trust_profiles")
    op.drop_index("ix_failed_attempts_created_at", table_name="failed_attempts")
    op.drop_index("ix_failed_attempts_attempt_type", table_name="failed_attempts")
    op.drop_index("ix_failed_attempts_identifier", table_name="failed_attempts")
    op.drop_table("failed_attempts")
    op.drop_index("ix_user_bank_cards_is_verified", table_name="user_bank_cards")
    op.drop_index("ix_user_bank_cards_card_pan_hash", table_name="user_bank_cards")
    op.drop_index("ix_user_bank_cards_user_id", table_name="user_bank_cards")
    op.drop_table("user_bank_cards")
