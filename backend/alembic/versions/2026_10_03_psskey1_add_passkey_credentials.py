"""passkey_credentials: stored WebAuthn credentials

P1 "کاربران: پاسکی". The backend had a challenge generator and nothing else —
no verification, no credential storage, no assertion path. A passkey that
cannot be verified is not a passkey; this table is the missing half.

The public key is stored, never a secret: WebAuthn is a signature scheme and
the private half never leaves the authenticator. ``sign_count`` is kept so a
cloned authenticator (a backwards count) can be detected per assertion.

Revision ID: psskey1
Revises: aprvreg1
Create Date: 2026-10-03
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "psskey1"
down_revision: str | None = "aprvreg1"

branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "passkey_credentials",
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
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("credential_id", sa.String(length=500), nullable=False),
        sa.Column("public_key", sa.Text(), nullable=False),
        sa.Column("public_key_alg", sa.Integer(), nullable=False),
        sa.Column(
            "sign_count", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column("name", sa.String(length=100), nullable=True),
        sa.Column("transports", postgresql.JSONB(), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        # Named explicitly: Postgres truncates identifiers past 63 bytes, and
        # an auto-generated name interpolating both table names would drift
        # from the constraint catalogue silently.
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_passkey_credentials_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_passkey_credentials_user_id",
        "passkey_credentials",
        ["user_id"],
    )
    op.create_index(
        "ix_passkey_credentials_credential_id",
        "passkey_credentials",
        ["credential_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_passkey_credentials_credential_id", table_name="passkey_credentials")
    op.drop_index("ix_passkey_credentials_user_id", table_name="passkey_credentials")
    op.drop_table("passkey_credentials")