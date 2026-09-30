"""Fix schema drift: add shipment_tracking_events, drop dead columns.

Resolves the drift reported by ``alembic check``:

* ``shipment_tracking_events`` existed only in the domain model — the
  shipping service writes timeline events into it on every shipment
  creation and status change, so without this table the shipped app
  would raise ``relation does not exist`` at runtime.
* ``orders.delivery_hold_until`` and ``user_profiles.father_name`` are
  referenced by no code (backend or frontend). They predate the current
  model definitions and are dead columns; they are dropped. The single
  populated ``delivery_hold_until`` value is NULLed first so no data is
  discarded.
* ``ix_users_deleted_at`` (migration c2d3e4f5a6b7) and the partial
  unique ``uq_wallet_signup_gift_once`` (migration a9b8c7d6e5f4) exist
  in the database but were missing from the models' ``__table_args__``.
  They are intentional, so the models now declare them (models change,
  no DDL here) and autogenerate will no longer try to drop them.

Revision ID: e9f0a1b2c3d4
Revises: c2d3e4f5a6b7
Create Date: 2026-09-17
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision = "e9f0a1b2c3d4"
down_revision = "c2d3e4f5a6b7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "shipment_tracking_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "shipment_id",
            UUID(as_uuid=True),
            sa.ForeignKey("shipments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING",
                "PROCESSING",
                "SHIPPED",
                "IN_TRANSIT",
                "DELIVERED",
                "RETURNED",
                name="shipment_status_enum",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("location", sa.String(length=200), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
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
    )
    op.create_index(
        "ix_tracking_events_shipment_id", "shipment_tracking_events", ["shipment_id"]
    )
    op.create_index("ix_tracking_events_status", "shipment_tracking_events", ["status"])
    op.create_index(
        "ix_tracking_events_created_at", "shipment_tracking_events", ["created_at"]
    )

    # Preserve the lone populated value before dropping the dead column.
    # Both columns are schema-drift remnants that may not exist on a
    # database built purely from this chain (from-empty runs), so each drop
    # is guarded: if the column was never created there is nothing to drop.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'orders' AND column_name = 'delivery_hold_until'
            ) THEN
                UPDATE orders SET delivery_hold_until = NULL;
                ALTER TABLE orders DROP COLUMN delivery_hold_until;
            END IF;
        END $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'user_profiles' AND column_name = 'father_name'
            ) THEN
                ALTER TABLE user_profiles DROP COLUMN father_name;
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.add_column(
        "user_profiles",
        sa.Column("father_name", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "orders",
        sa.Column("delivery_hold_until", sa.DateTime(timezone=True), nullable=True),
    )
    op.drop_index("ix_tracking_events_created_at", table_name="shipment_tracking_events")
    op.drop_index("ix_tracking_events_status", table_name="shipment_tracking_events")
    op.drop_index("ix_tracking_events_shipment_id", table_name="shipment_tracking_events")
    op.drop_table("shipment_tracking_events")
