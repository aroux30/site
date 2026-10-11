"""Remove the approvals module (tables + permission).

The «کارتابل تاییدها» module was retired on 2026-10-04 by operator decision.
It was verified to be decorative rather than functional:

- no code path outside the module ever created an approval request (grep
  across the whole backend: zero `create_request` callers outside its own
  routes) — price changes, refunds, publishing and withdrawal all execute
  directly;
- `POST /wallet/withdraw` never consulted approvals, and approving a
  `wallet_withdrawal`/`vendor_settlement` request executed nothing (no branch
  in `_execute_side_effects`; the `ApprovalRequestCompleted` event had zero
  consumers);
- the multi-step chain's `IN_REVIEW` state was not rendered or actionable in
  the admin UI at all.

Keeping a cartable that reviews nothing is worse than not having one: it
advertises control that does not exist. The decision record and evidence are
in `docs/gaps-approval-workflow-2026-10-04.md`, and the removed code is
archived under `_archived/approvals-module-2026-10-04/`.

Both approval tables were empty at removal time (0 requests/actions/steps;
3 seeded policy rows), so no business data is lost. `downgrade()` recreates
the full schema — four tables, constraints, indexes, and the `approvals:review`
permission with its admin grant — so the removal is reversible.

Revision ID: rmapprov1
Revises: cprev2
Create Date: 2026-10-04
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "rmapprov1"
down_revision = "cprev2"
branch_labels = None
depends_on = None

#: The permission row as it existed at removal (verified against the live
#: database before dropping). The id is pinned so a downgrade restores the
#: exact row the removed code referenced.
_PERMISSION_ID = "b0e558e4-f71c-4ee6-81b1-fd920f107f98"
_PERMISSION_SLUG = "approvals:review"
_PERMISSION_RESOURCE = "approvals"
_PERMISSION_ACTION = "review"
_PERMISSION_NAME = "بررسی درخواست‌های تایید"
_PERMISSION_DESCRIPTION = "بررسی و تایید/رد درخواست‌های در صف تایید"


def upgrade() -> None:
    # Children before parents: approval_actions and approval_steps both hold
    # FKs into approval_requests.
    op.drop_index("ix_approval_actions_actor_id", table_name="approval_actions")
    op.drop_index("ix_approval_actions_request_id", table_name="approval_actions")
    op.drop_table("approval_actions")

    op.drop_index("ix_approval_steps_status", table_name="approval_steps")
    op.drop_index("ix_approval_steps_request_id", table_name="approval_steps")
    op.drop_table("approval_steps")

    op.drop_index("ix_approval_policies_active", table_name="approval_policies")
    op.drop_index("ix_approval_policies_resource", table_name="approval_policies")
    op.drop_table("approval_policies")

    op.drop_index("ix_approval_requests_created_at", table_name="approval_requests")
    op.drop_index("ix_approval_requests_requester_id", table_name="approval_requests")
    op.drop_index("ix_approval_requests_resource", table_name="approval_requests")
    op.drop_index("ix_approval_requests_status", table_name="approval_requests")
    op.drop_index("ix_approval_requests_type", table_name="approval_requests")
    op.drop_table("approval_requests")

    # The permission leaves with the feature it guarded. role_permissions has
    # ON DELETE CASCADE on permission_id, so the admin grant goes with it.
    op.execute(
        sa.text("DELETE FROM permissions WHERE slug = :slug").bindparams(
            slug=_PERMISSION_SLUG
        )
    )


def downgrade() -> None:
    # ── approval_requests (initial schema, status widened to 20 by
    #    r2x3y4z5a6b7 which this removal sits after) ─────────────────────────
    op.create_table(
        "approval_requests",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("requester_id", sa.UUID(), nullable=False),
        sa.Column("type", sa.String(length=100), nullable=False),
        sa.Column("resource", sa.String(length=100), nullable=False),
        sa.Column("resource_id", sa.UUID(), nullable=True),
        sa.Column(
            "level",
            sa.Enum("LOW", "MEDIUM", "HIGH", name="approval_level_enum", native_enum=False),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING", "APPROVED", "REJECTED", name="approval_status_enum", native_enum=False
            ),
            nullable=False,
        ),
        sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["requester_id"],
            ["users.id"],
            name=op.f("fk_approval_requests_requester_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_approval_requests")),
    )
    op.create_index(
        "ix_approval_requests_created_at", "approval_requests", ["created_at"], unique=False
    )
    op.create_index(
        "ix_approval_requests_requester_id", "approval_requests", ["requester_id"], unique=False
    )
    op.create_index(
        "ix_approval_requests_resource", "approval_requests", ["resource"], unique=False
    )
    op.create_index("ix_approval_requests_status", "approval_requests", ["status"], unique=False)
    op.create_index("ix_approval_requests_type", "approval_requests", ["type"], unique=False)

    # ── approval_actions ──────────────────────────────────────────────────
    op.create_table(
        "approval_actions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("request_id", sa.UUID(), nullable=False),
        sa.Column("actor_id", sa.UUID(), nullable=False),
        sa.Column(
            "action",
            sa.Enum("APPROVE", "REJECT", name="approval_action_type_enum", native_enum=False),
            nullable=False,
        ),
        sa.Column("comment", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["users.id"],
            name=op.f("fk_approval_actions_actor_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["request_id"],
            ["approval_requests.id"],
            name=op.f("fk_approval_actions_request_id_approval_requests"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_approval_actions")),
    )
    op.create_index("ix_approval_actions_actor_id", "approval_actions", ["actor_id"], unique=False)
    op.create_index(
        "ix_approval_actions_request_id", "approval_actions", ["request_id"], unique=False
    )

    # ── approval_steps (e8a2c4d6f1b3) ─────────────────────────────────────
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

    # ── approval_policies (e8a2c4d6f1b3) ──────────────────────────────────
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

    # The status vocabulary the table carried at cprev2 (widened by
    # r2x3y4z5a6b7, check constraint from e8a2c4d6f1b3).
    op.execute(
        "ALTER TABLE approval_requests DROP CONSTRAINT IF EXISTS ck_approval_requests_status"
    )
    op.create_check_constraint(
        "ck_approval_requests_status",
        "approval_requests",
        "status IN ('PENDING', 'APPROVED', 'REJECTED', 'IN_REVIEW')",
    )

    # ── the permission row and its admin grant ────────────────────────────
    op.execute(
        sa.text(
            "INSERT INTO permissions (id, slug, resource, action, name, description,"
            " created_at, updated_at)"
            " VALUES (CAST(:id AS uuid), :slug, :resource, :action, :name, :description,"
            " now(), now())"
            " ON CONFLICT (slug) DO NOTHING"
        ).bindparams(
            id=_PERMISSION_ID,
            slug=_PERMISSION_SLUG,
            resource=_PERMISSION_RESOURCE,
            action=_PERMISSION_ACTION,
            name=_PERMISSION_NAME,
            description=_PERMISSION_DESCRIPTION,
        )
    )
    # Re-grant to the seeded admin role, matching permission_seed.py's blanket
    # grant to ADMIN_ROLE_SLUG. Missing role (a database that never seeded)
    # is fine: the row is granted by the next startup seed.
    op.execute(
        sa.text(
            "INSERT INTO role_permissions (id, role_id, permission_id, created_at, updated_at)"
            " SELECT gen_random_uuid(), r.id, p.id, now(), now()"
            " FROM roles r, permissions p"
            " WHERE r.slug = 'admin' AND p.slug = :slug"
            " ON CONFLICT DO NOTHING"
        ).bindparams(slug=_PERMISSION_SLUG)
    )
