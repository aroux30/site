"""Application passwords (WordPress parity)

Revision ID: u1v2w3x4y5z6
Revises: r8s9t0u1v2w3
Create Date: 2026-09-28 19:20:00.000000+03:00

A phone app or a personal script needs to act on the user's behalf. Sharing
the account password for that is the thing WordPress application passwords
exist to stop, and it is the recommended path in the official mobile app
documentation — so skipping it pushes every user of that app back onto
sharing their real password.

Only a SHA-256 of the secret is stored. ``scopes`` is an empty list by
default, meaning "everything the user can do" (WordPress's own default); a
non-empty list is a strict subset, so a read-only client cannot write.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "u1v2w3x4y5z6"
down_revision: str = "r8s9t0u1v2w3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "application_passwords",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("token_prefix", sa.String(length=12), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("scopes", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_ip", sa.String(length=45), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_application_passwords_user_id", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_application_passwords"),
    )
    op.create_index("ix_application_passwords_user_id", "application_passwords", ["user_id"])
    op.create_index("ix_application_passwords_token_hash", "application_passwords", ["token_hash"], unique=True)
    op.create_index("ix_application_passwords_is_active", "application_passwords", ["is_active"])


def downgrade() -> None:
    op.drop_index("ix_application_passwords_is_active", table_name="application_passwords")
    op.drop_index("ix_application_passwords_token_hash", table_name="application_passwords")
    op.drop_index("ix_application_passwords_user_id", table_name="application_passwords")
    op.drop_table("application_passwords")
