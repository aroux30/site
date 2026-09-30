"""CRM v1: the wholesale-inquiry pipeline.

ERP benchmark gap analysis (feature #18 CRM/leads, P2 — minimal scope). Full
sales suites (YetiForce-scale) are wrong for a B2C storefront; the concrete
gap is that a business wanting to buy in bulk has no tracked funnel before it
becomes a reseller.

- ``lead_inquiries``: one row per inquiry, with a validated stage machine
  (``new → contacted → qualified → negotiating → converted|lost``), an owner,
  a structured estimate and a JSONB notes timeline. Conversion provisions a
  real ``reseller_api_keys`` row — the pipeline's last step is not retyping.

Revision ID: c4e6a8b2d5f7
Revises: b3d5f7a9c1e4
Create Date: 2026-09-25 05:40:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "c4e6a8b2d5f7"
down_revision = "b3d5f7a9c1e4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lead_inquiries",
        sa.Column("contact_name", sa.String(length=200), nullable=False),
        sa.Column("company_name", sa.String(length=300), nullable=True),
        sa.Column("phone", sa.String(length=20), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("stage", sa.String(length=32), nullable=False, server_default="NEW"),
        sa.Column("source", sa.String(length=32), nullable=False, server_default="WEB_FORM"),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("estimated_monthly_value_rial", sa.BigInteger(), nullable=True),
        sa.Column("estimated_monthly_volume", sa.Integer(), nullable=True),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("converted_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("converted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lost_reason", sa.String(length=500), nullable=True),
        sa.Column("notes", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("next_follow_up_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.CheckConstraint(
            "contact_name <> ''", name=op.f("ck_lead_inquiries_contact_name_not_empty")
        ),
        sa.CheckConstraint(
            "estimated_monthly_value_rial IS NULL OR estimated_monthly_value_rial >= 0",
            name=op.f("ck_lead_inquiries_value_non_negative"),
        ),
        sa.CheckConstraint(
            "stage IN ('NEW', 'CONTACTED', 'QUALIFIED', 'NEGOTIATING', "
            "'CONVERTED', 'LOST')",
            name=op.f("ck_lead_inquiries_stage"),
        ),
        sa.CheckConstraint(
            "source IN ('WEB_FORM', 'PHONE', 'EMAIL', 'REFERRAL', 'SOCIAL', 'OTHER')",
            name=op.f("ck_lead_inquiries_source"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name=op.f("fk_lead_inquiries_owner_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["converted_user_id"],
            ["users.id"],
            name=op.f("fk_lead_inquiries_converted_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_lead_inquiries")),
    )
    op.create_index("ix_lead_inquiries_stage", "lead_inquiries", ["stage"])
    op.create_index("ix_lead_inquiries_owner_id", "lead_inquiries", ["owner_id"])
    op.create_index("ix_lead_inquiries_created_at", "lead_inquiries", ["created_at"])
    op.create_index("ix_lead_inquiries_company", "lead_inquiries", ["company_name"])
    # The pipeline list sorts by follow-up urgency; a partial index on the
    # unset rows keeps "what needs attention" cheap as history accumulates.
    op.create_index(
        "ix_lead_inquiries_next_follow_up",
        "lead_inquiries",
        ["next_follow_up_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_lead_inquiries_next_follow_up", table_name="lead_inquiries")
    op.drop_index("ix_lead_inquiries_company", table_name="lead_inquiries")
    op.drop_index("ix_lead_inquiries_created_at", table_name="lead_inquiries")
    op.drop_index("ix_lead_inquiries_owner_id", table_name="lead_inquiries")
    op.drop_index("ix_lead_inquiries_stage", table_name="lead_inquiries")
    op.drop_table("lead_inquiries")
