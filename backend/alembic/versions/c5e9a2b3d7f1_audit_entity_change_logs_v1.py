"""Audit field-level change log (ERP benchmark feature #9 Audit trail, P1).

Creates ``entity_change_logs``: one row per (flush, tracked entity) that
changed at least one tracked field, carrying the before/after diff as JSONB.

The existing ``audit_logs`` table records *actions* ("admin updated product
X"); this table answers the ERP-grade question "who changed this product's
price from 1,200,000 to 950,000, and when?".

Design notes (see ``app.modules.audit.domain.entity_changelog`` and
``app.modules.audit.application.change_tracking``):

- Observation-only. The capture hook runs in ``after_flush`` and is
  fail-soft — a capture failure is logged, never propagated.
- Money stays integer: ``changed_fields`` holds JSON-safe raw values with
  integer Rial amounts kept as ``int`` (no float coercion).
- ``actor_id`` is nullable with ``ondelete=SET NULL``: system/Celery changes
  have no user, and deleting a user must not erase the evidence.
- ``operation`` is a native-enum=False VARCHAR + CHECK, matching the project
  convention.

Additive only: no existing table is altered.

Revision ID: c5e9a2b3d7f1
Revises: b4d8f1a2c6e9
Create Date: 2026-09-25 01:20:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "c5e9a2b3d7f1"
down_revision = "b4d8f1a2c6e9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "entity_change_logs",
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("entity_id", sa.String(length=255), nullable=False),
        sa.Column("operation", sa.String(length=16), nullable=False, server_default="UPDATE"),
        sa.Column(
            "changed_fields",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("actor_type", sa.String(length=16), nullable=False, server_default="SYSTEM"),
        sa.Column("request_id", sa.String(length=255), nullable=True),
        sa.Column("source", sa.String(length=16), nullable=False, server_default="SERVICE"),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("truncated", sa.Boolean(), nullable=False, server_default=sa.text("false")),
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
            "operation IN ('CREATE', 'UPDATE', 'DELETE')",
            name=op.f("ck_entity_change_logs_operation"),
        ),
        sa.CheckConstraint(
            # Enum member NAMES (see Enum(ChangeActorType).enums): the ORM
            # persists 'USER'/'SYSTEM'/'CELERY', never the lowercase values.
            "actor_type IN ('USER', 'SYSTEM', 'CELERY')",
            name=op.f("ck_entity_change_logs_actor_type"),
        ),
        sa.CheckConstraint(
            "source IN ('API', 'ADMIN', 'SERVICE', 'SEED')",
            name=op.f("ck_entity_change_logs_source"),
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["users.id"],
            name=op.f("fk_entity_change_logs_actor_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_entity_change_logs")),
    )
    op.create_index(
        "ix_entity_change_logs_entity",
        "entity_change_logs",
        ["entity_type", "entity_id"],
        unique=False,
    )
    op.create_index(
        "ix_entity_change_logs_entity_type",
        "entity_change_logs",
        ["entity_type"],
        unique=False,
    )
    op.create_index(
        "ix_entity_change_logs_actor_id",
        "entity_change_logs",
        ["actor_id"],
        unique=False,
    )
    op.create_index(
        "ix_entity_change_logs_occurred_at",
        "entity_change_logs",
        ["occurred_at"],
        unique=False,
    )
    op.create_index(
        "ix_entity_change_logs_request_id",
        "entity_change_logs",
        ["request_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_entity_change_logs_request_id", table_name="entity_change_logs")
    op.drop_index("ix_entity_change_logs_occurred_at", table_name="entity_change_logs")
    op.drop_index("ix_entity_change_logs_actor_id", table_name="entity_change_logs")
    op.drop_index("ix_entity_change_logs_entity_type", table_name="entity_change_logs")
    op.drop_index("ix_entity_change_logs_entity", table_name="entity_change_logs")
    op.drop_table("entity_change_logs")
