"""Deduplicate gamification awards per (rule, order).

The outbox worker awards loyalty points when it processes an
OrderConfirmed message. If the worker retries a message whose effects
committed but whose processed marker did not (lease expiry after a crash
between commit and mark_processed), a second GamificationEvent and a
second loyalty credit were inserted — gamification_events had no unique
constraint, so nothing rejected the replay.

This migration adds a nullable ``order_id`` column (denormalized from
event_data) plus a partial unique index on (rule_id, order_id) where
order_id is not null. Legacy rows keep NULL order_id and are exempt from
the index, so no data backfill or duplicate cleanup is needed for them.

Revision ID: b6c7d8e9f0a1
Revises: a5b6c7d8e9f0
Create Date: 2026-09-17
"""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision = "b6c7d8e9f0a1"
down_revision = "a5b6c7d8e9f0"
branch_labels = None
depends_on = None


def _uuid_default() -> str:
    return uuid.uuid4().hex


def upgrade() -> None:
    op.add_column(
        "gamification_events",
        sa.Column(
            "order_id",
            UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fk_gamification_events_order_id",
        "gamification_events",
        "orders",
        ["order_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "uq_gamification_event_rule_order",
        "gamification_events",
        ["rule_id", "order_id"],
        unique=True,
        postgresql_where="order_id IS NOT NULL",
    )


def downgrade() -> None:
    op.drop_index(
        "uq_gamification_event_rule_order",
        table_name="gamification_events",
        postgresql_where="order_id IS NOT NULL",
    )
    op.drop_constraint(
        "fk_gamification_events_order_id",
        "gamification_events",
        type_="foreignkey",
    )
    op.drop_column("gamification_events", "order_id")
