"""Add notices and seen notices tables (Karta Phase 6/8).

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-09-12 20:30:00

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. notices table
    op.create_table(
        "notices",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("content_html", sa.Text(), nullable=False),
        sa.Column("notice_type", sa.String(length=32), nullable=False, server_default="popup"),
        sa.Column("target_page", sa.String(length=32), nullable=False, server_default="all"),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notices")),
    )
    op.create_index("ix_notices_is_active", "notices", ["is_active"], unique=False)
    op.create_index("ix_notices_target_page", "notices", ["target_page"], unique=False)
    op.create_index("ix_notices_time_window", "notices", ["start_at", "end_at"], unique=False)

    # 2. seen_notices table
    op.create_table(
        "seen_notices",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("notice_id", sa.UUID(), nullable=False),
        sa.Column("seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_seen_notices_user_id_users"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["notice_id"], ["notices.id"], name=op.f("fk_seen_notices_notice_id_notices"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_seen_notices")),
        sa.UniqueConstraint("user_id", "notice_id", name="uq_seen_notices_user_notice"),
    )
    op.create_index("ix_seen_notices_user_id", "seen_notices", ["user_id"], unique=False)
    op.create_index("ix_seen_notices_notice_id", "seen_notices", ["notice_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_seen_notices_notice_id", table_name="seen_notices")
    op.drop_index("ix_seen_notices_user_id", table_name="seen_notices")
    op.drop_table("seen_notices")
    op.drop_index("ix_notices_time_window", table_name="notices")
    op.drop_index("ix_notices_target_page", table_name="notices")
    op.drop_index("ix_notices_is_active", table_name="notices")
    op.drop_table("notices")
