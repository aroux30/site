"""drop passkey_credentials — the passkey feature is removed.

The store signs in with phone + password/OTP only. The WebAuthn service
(`passkey_service`), its endpoints (`/auth/mfa/passkey/*`), the
`PasskeyCredential` model, and the frontend card/button were all removed with
the feature; this migration drops the last trace — the table itself.

Revision ID: rmpass1
Revises: caddon1
Create Date: 2026-11-09
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "rmpass1"
down_revision: str | None = "caddon1"

branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index(
        "ix_passkey_credentials_credential_id", table_name="passkey_credentials"
    )
    op.drop_index("ix_passkey_credentials_user_id", table_name="passkey_credentials")
    op.drop_table("passkey_credentials")


def downgrade() -> None:
    # Recreating the table for rollback parity with `psskey1`, whose shape this
    # mirrors. A downgrade after the code removal would have no writer, but a
    # migration must still be able to walk backwards.
    op.create_table(
        "passkey_credentials",
        sa.Column("id", sa.UUID(), nullable=False),
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
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("credential_id", sa.String(length=500), nullable=False),
        sa.Column("public_key", sa.Text(), nullable=False),
        sa.Column("public_key_alg", sa.Integer(), nullable=False),
        sa.Column(
            "sign_count", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column("name", sa.String(length=100), nullable=True),
        sa.Column("transports", sa.JSON(), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_passkey_credentials_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_passkey_credentials_user_id", "passkey_credentials", ["user_id"]
    )
    op.create_index(
        "ix_passkey_credentials_credential_id",
        "passkey_credentials",
        ["credential_id"],
        unique=True,
    )
