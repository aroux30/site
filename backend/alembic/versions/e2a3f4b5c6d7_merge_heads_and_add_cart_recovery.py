"""Merge two Alembic heads and add abandoned-cart recovery columns.

Two heads existed — a1c8f2b3d4e5 (order price snapshots) and b3c4d5e6f7a8
(multi-warehouse inventory) — so ``alembic upgrade head`` aborted with
"Multiple head revisions are present" and a fresh database could never be
migrated. This revision has both heads as parents, restoring a single head,
and then adds the abandoned-cart recovery schema:

* ``carts.last_activity_at`` — timestamp of the last cart edit; the recovery
  task measures each reminder stage's quiet window from it.
* ``carts.recovery_stage`` — highest recovery stage already attempted
  (0-based index into Settings.CART_RECOVERY_STAGES_MINUTES).
* ``cart_recovery_attempts`` — one row per (cart, stage) attempted reminder;
  its (cart_id, stage) unique constraint is the idempotence ledger that makes
  a retried reminder task send exactly one SMS per stage.

Concept: Odoo ``website_sale`` abandoned-cart follow-up, rebuilt clean-room.

Revision ID: e2a3f4b5c6d7
Revises: a1c8f2b3d4e5, b3c4d5e6f7a8
Create Date: 2026-09-24
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision = "e2a3f4b5c6d7"
down_revision = ("a1c8f2b3d4e5", "b3c4d5e6f7a8")
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Recovery state on the cart itself.
    op.add_column("carts", sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "carts",
        sa.Column("recovery_stage", sa.Integer(), nullable=False, server_default="0"),
    )
    op.alter_column("carts", "recovery_stage", server_default=None)

    # Idempotence ledger: one attempted reminder per (cart, stage).
    op.create_table(
        "cart_recovery_attempts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "cart_id",
            UUID(as_uuid=True),
            sa.ForeignKey("carts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("stage", sa.Integer(), nullable=False),
        sa.Column(
            "channel",
            sa.Enum("SMS", "IN_APP", name="recovery_channel_enum", native_enum=False),
            nullable=False,
        ),
        sa.Column("subtotal_rial", sa.BigInteger(), nullable=False),
        sa.Column("item_count", sa.Integer(), nullable=False),
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
        sa.UniqueConstraint("cart_id", "stage", name="uq_cart_recovery_cart_stage"),
    )
    op.create_index("ix_cart_recovery_cart_id", "cart_recovery_attempts", ["cart_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_cart_recovery_cart_id", table_name="cart_recovery_attempts")
    op.drop_table("cart_recovery_attempts")
    op.drop_column("carts", "recovery_stage")
    op.drop_column("carts", "last_activity_at")
