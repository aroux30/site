"""add form_submissions table for visual page builder (Phase P4).

Revision ID: formsub1
Revises: theme1
Create Date: 2026-11-18
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "formsub1"
down_revision: str | None = "theme1"

branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "form_submissions",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
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
        sa.Column("form_id", sa.String(length=100), nullable=False),
        sa.Column(
            "page_id",
            UUID(as_uuid=True),
            sa.ForeignKey("cms_pages.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("page_slug", sa.String(length=220), nullable=True),
        sa.Column("data", JSONB, nullable=False),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.Column(
            "is_read",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.create_index("ix_form_submissions_form_id", "form_submissions", ["form_id"])
    op.create_index("ix_form_submissions_page_id", "form_submissions", ["page_id"])
    op.create_index("ix_form_submissions_created_at", "form_submissions", ["created_at"])
    op.create_index("ix_form_submissions_is_read", "form_submissions", ["is_read"])


def downgrade() -> None:
    op.drop_index("ix_form_submissions_is_read", table_name="form_submissions")
    op.drop_index("ix_form_submissions_created_at", table_name="form_submissions")
    op.drop_index("ix_form_submissions_page_id", table_name="form_submissions")
    op.drop_index("ix_form_submissions_form_id", table_name="form_submissions")
    op.drop_table("form_submissions")
