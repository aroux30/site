"""email_verification_tokens: confirm ownership of a registration address

P1 "کاربران: تأیید ایمیل هنگام ثبت‌نام". ``users.is_verified`` existed but was
only ever set by the OTP flow — proving the phone, not the email — so an address
given at registration was never checked and password resets were mailed to it
unverified.

Stores only the SHA-256 of the token, like ``password_reset_tokens`` and
``email_change_requests``: the plaintext exists solely in the email.

Revision ID: emlver1
Revises: mdtitle1
Create Date: 2026-10-02
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "emlver1"
down_revision: str | None = "mdtitle1"

branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "email_verification_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        # server_default, not just nullable=False: the ORM's TimestampMixin
        # declares ``server_default=func.now()`` and relies on the database to
        # fill these. A migration that omits it produces a table where every
        # insert fails NOT NULL — the model's own metadata and the migrated
        # schema must agree on who supplies the timestamp.
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
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        # Named explicitly: Postgres truncates identifiers over 63 bytes, and an
        # auto-generated name interpolating both table names plus the column
        # would silently drift from the constraint catalogue otherwise.
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_email_verification_tokens_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_email_verification_tokens_token_hash",
        "email_verification_tokens",
        ["token_hash"],
        unique=True,
    )
    op.create_index(
        "ix_email_verification_tokens_user_id",
        "email_verification_tokens",
        ["user_id"],
    )
    op.create_index(
        "ix_email_verification_tokens_expires_at",
        "email_verification_tokens",
        ["expires_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_email_verification_tokens_expires_at", table_name="email_verification_tokens")
    op.drop_index("ix_email_verification_tokens_user_id", table_name="email_verification_tokens")
    op.drop_index("ix_email_verification_tokens_token_hash", table_name="email_verification_tokens")
    op.drop_table("email_verification_tokens")