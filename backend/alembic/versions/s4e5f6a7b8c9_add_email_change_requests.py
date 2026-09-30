"""email change requests: confirm an address change before it takes effect

An account's email could be replaced outright, with no confirmation sent to
either address. Since password reset travels by email, that made the change a
way to take an account over: change the address, then trigger a reset.

This adds the request table that makes the change two-step. The user's
``email`` is untouched until the token is redeemed, so a reset issued in the
meantime still goes to the address the account really owns.

Revision ID: s4e5f6a7b8c9
Revises: r2x3y4z5a6b7
Create Date: 2026-09-29
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "s4e5f6a7b8c9"
down_revision: str | None = "r2x3y4z5a6b7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "email_change_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("new_email", sa.String(length=255), nullable=False),
        sa.Column("current_email", sa.String(length=255), nullable=True),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("invalidated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("request_ip", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_email_change_requests_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Index names are capped at Postgres's 63-byte identifier limit. These are
    # written out rather than generated so the truncation is visible here
    # instead of arriving as a truncated name on a live database.
    op.create_index(
        "ix_email_change_requests_token_hash",
        "email_change_requests",
        ["token_hash"],
        unique=True,
    )
    op.create_index(
        "ix_email_change_requests_user_id",
        "email_change_requests",
        ["user_id"],
    )
    op.create_index(
        "ix_email_change_requests_expires_at",
        "email_change_requests",
        ["expires_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_email_change_requests_expires_at", table_name="email_change_requests")
    op.drop_index("ix_email_change_requests_user_id", table_name="email_change_requests")
    op.drop_index("ix_email_change_requests_token_hash", table_name="email_change_requests")
    op.drop_table("email_change_requests")
