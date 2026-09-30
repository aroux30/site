"""add privacy_requests (GDPR data-subject request queue)

Revision ID: p9r1v2w3x4y5
Revises: n3o4p5q6r7s8
Create Date: 2026-09-29

``export_user_data`` and ``erase_user_data`` existed but were reachable only
by an operator typing a user UUID. GDPR asks for the *data subject* to make
the request, so the request needs somewhere to live: a row per subject, with
its own status, verification timestamps, operator note, and the finished
export payload plus its expiry.

There is no "target user" column — ``user_id`` is the requester and the
account the work runs on — so no handler can be aimed at another subject by a
path parameter.

Enums are stored with ``native_enum=False`` (VARCHAR + CHECK) to match
``CashbackTransactionStatus`` and every other enum column in this schema: a
native PG enum needs its own DROP TYPE on downgrade and cannot be altered in
place, and the codebase stores enum *names*, not values.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "p9r1v2w3x4y5"
down_revision = "n3o4p5q6r7s8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "privacy_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "type",
            sa.Enum(
                "EXPORT",
                "ERASE",
                name="privacy_request_type_enum",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING",
                "PROCESSING",
                "COMPLETED",
                "REJECTED",
                name="privacy_request_status_enum",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("admin_note", sa.Text(), nullable=True),
        sa.Column("resolved_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("result_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_privacy_requests_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_privacy_requests_user_id_status",
        "privacy_requests",
        ["user_id", "status"],
    )
    op.create_index(
        "ix_privacy_requests_status_created_at",
        "privacy_requests",
        ["status", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_privacy_requests_status_created_at", table_name="privacy_requests")
    op.drop_index("ix_privacy_requests_user_id_status", table_name="privacy_requests")
    op.drop_table("privacy_requests")
