"""Add referral_codes table.

A user's referral code was generated on demand and never persisted: the
``referrals`` table records a referrer→referred relationship, which does not
exist until someone signs up with the code. Every call to the referral-code
endpoint therefore returned a fresh random code, so a link shared with a
friend stopped working immediately and the code was unrecoverable.

``referral_codes`` stores one stable code per user (unique on both ``user_id``
and ``code``).

Revision ID: a5b6c7d8e9f0
Revises: f0a1b2c3d4e5
Create Date: 2026-09-17
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision = "a5b6c7d8e9f0"
down_revision = "f0a1b2c3d4e5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "referral_codes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
        ),
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
    )
    op.create_index(
        "ix_referral_codes_user_id", "referral_codes", ["user_id"], unique=True
    )
    op.create_index("ix_referral_codes_code", "referral_codes", ["code"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_referral_codes_code", table_name="referral_codes")
    op.drop_index("ix_referral_codes_user_id", table_name="referral_codes")
    op.drop_table("referral_codes")
