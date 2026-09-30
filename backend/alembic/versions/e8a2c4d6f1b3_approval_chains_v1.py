"""Approval chains v1: ordered signature steps and amount-band policies.

ERP benchmark gap analysis (feature #23 Workflow/approvals, P1). The v1 engine
was single-step — one review action closed a request. These two tables add:

- ``approval_steps``: the frozen signature chain of one request, materialised
  at submission so a policy edited mid-flight cannot change the rules a live
  request is judged by.
- ``approval_policies``: data-driven rules mapping (resource, amount band) to
  a chain definition. Tuned by operators without a deployment.

Also widens the ``approval_requests.status`` vocab with ``in_review`` — a
chain with some signatures collected and some outstanding. The column is a
native-enum=False VARCHAR + CHECK (project convention), so the constraint is
replaced rather than the type altered.

Revision ID: e8a2c4d6f1b3
Revises: d7f1b3c5e9a2
Create Date: 2026-09-25 03:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "e8a2c4d6f1b3"
down_revision = "d7f1b3c5e9a2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. approval_steps ─────────────────────────────────────────────────
    op.create_table(
        "approval_steps",
        sa.Column("request_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column("required_role", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="PENDING"),
        sa.Column("acted_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("acted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("label", sa.String(length=200), nullable=True),
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
        sa.CheckConstraint("step_order >= 0", name=op.f("ck_approval_steps_order_non_negative")),
        sa.CheckConstraint(
            # Enum member NAMES, not values: ApprovalStep.status is
            # Enum(..., native_enum=False) without values_callable, so
            # SQLAlchemy persists 'PENDING' (verified via Enum(X).enums).
            "status IN ('PENDING', 'APPROVED', 'REJECTED', 'SKIPPED')",
            name=op.f("ck_approval_steps_status"),
        ),
        sa.ForeignKeyConstraint(
            ["request_id"],
            ["approval_requests.id"],
            name=op.f("fk_approval_steps_request_id_approval_requests"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["acted_by_id"],
            ["users.id"],
            name=op.f("fk_approval_steps_acted_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_approval_steps")),
        sa.UniqueConstraint(
            "request_id",
            "step_order",
            name="uq_approval_steps_request_order",
        ),
    )
    op.create_index("ix_approval_steps_request_id", "approval_steps", ["request_id"])
    op.create_index("ix_approval_steps_status", "approval_steps", ["status"])

    # ── 2. approval_policies ──────────────────────────────────────────────
    op.create_table(
        "approval_policies",
        sa.Column("resource", sa.String(length=100), nullable=False),
        sa.Column("min_amount_rial", sa.BigInteger(), nullable=True),
        sa.Column("max_amount_rial", sa.BigInteger(), nullable=True),
        sa.Column("steps", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("description", sa.String(length=500), nullable=True),
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
            "min_amount_rial IS NULL OR min_amount_rial >= 0",
            name=op.f("ck_approval_policies_min_amount_non_negative"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_approval_policies")),
    )
    op.create_index("ix_approval_policies_resource", "approval_policies", ["resource"])
    op.create_index("ix_approval_policies_active", "approval_policies", ["is_active"])

    # ── 3. widen the request-status vocabulary with 'in_review' ───────────
    # The original constraint (if the table was created with one) rejects the
    # new value; drop-then-recreate keeps the check honest either way.
    op.execute(
        "ALTER TABLE approval_requests DROP CONSTRAINT IF EXISTS ck_approval_requests_status"
    )
    op.create_check_constraint(
        "ck_approval_requests_status",
        "approval_requests",
        "status IN ('PENDING', 'APPROVED', 'REJECTED', 'IN_REVIEW')",
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE approval_requests DROP CONSTRAINT IF EXISTS ck_approval_requests_status"
    )
    # Enum member names, same as the upgrade path above.
    op.create_check_constraint(
        "ck_approval_requests_status",
        "approval_requests",
        "status IN ('PENDING', 'APPROVED', 'REJECTED')",
    )

    op.drop_index("ix_approval_policies_active", table_name="approval_policies")
    op.drop_index("ix_approval_policies_resource", table_name="approval_policies")
    op.drop_table("approval_policies")

    op.drop_index("ix_approval_steps_status", table_name="approval_steps")
    op.drop_index("ix_approval_steps_request_id", table_name="approval_steps")
    op.drop_table("approval_steps")
