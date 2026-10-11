"""Remove the pickup-points feature (decision 2026-10-04).

The owner asked for «نقاط تحویل حضوری» to be deleted — a retail storefront
here delivers to addresses; the in-person-pickup catalogue had no consumer.
The code is archived under ``_archived/pickup-scan-2026-10-04/`` and this
migration drops its table, the shipments column that referenced it, and the
now-invalid ``PICKUP_POINT`` member of the delivery_type CHECK.

Verified **unused at removal time** (live probe 2026-10-04):
``pickup_points`` = 0 rows, ``shipments.pickup_point_id`` non-null = 0,
``shipments.delivery_type = 'PICKUP_POINT'`` = 0 (all 173 shipments are
``HOME``). ``downgrade()`` recreates the table, column, FK and the original
three-member CHECK, so the removal is reversible.

Kept on purpose: the rest of the shipping upgrade (COD, cancellation) shares
the same tables and CHECK constraint — only the ``'PICKUP_POINT'`` member is
removed from the vocabulary.

Revision ID: rmpickup1
Revises: rmjournal1
Create Date: 2026-10-04
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "rmpickup1"
down_revision = "rmjournal1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The CHECK must shrink before the column it guards goes: the constraint
    # is rewritten in place (it also guards HOME / CASH_ON_DELIVERY).
    op.drop_constraint("ck_shipments_delivery_type", "shipments", type_="check")
    op.create_check_constraint(
        "ck_shipments_delivery_type",
        "shipments",
        "delivery_type IN ('HOME', 'CASH_ON_DELIVERY')",
    )
    op.drop_constraint(
        "fk_shipments_pickup_point_id_pickup_points", "shipments", type_="foreignkey"
    )
    op.drop_column("shipments", "pickup_point_id")

    op.drop_index("ix_pickup_points_provider", table_name="pickup_points")
    op.drop_index("ix_pickup_points_city", table_name="pickup_points")
    op.drop_table("pickup_points")


def downgrade() -> None:
    """Recreate the table, column, FK and the original CHECK."""
    op.create_table(
        "pickup_points",
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("external_id", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=300), nullable=False),
        sa.Column("city", sa.String(length=100), nullable=False),
        sa.Column("province", sa.String(length=100), nullable=True),
        sa.Column("address", sa.Text(), nullable=False),
        sa.Column("postal_code", sa.String(length=20), nullable=True),
        sa.Column("phone", sa.String(length=20), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_pickup_points")),
        sa.UniqueConstraint(
            "provider",
            "external_id",
            name="uq_pickup_points_provider_external",
        ),
    )
    op.create_index("ix_pickup_points_city", "pickup_points", ["city"])
    op.create_index("ix_pickup_points_provider", "pickup_points", ["provider"])

    op.add_column(
        "shipments",
        sa.Column("pickup_point_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        op.f("fk_shipments_pickup_point_id_pickup_points"),
        "shipments",
        "pickup_points",
        ["pickup_point_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.drop_constraint("ck_shipments_delivery_type", "shipments", type_="check")
    op.create_check_constraint(
        "ck_shipments_delivery_type",
        "shipments",
        "delivery_type IN ('HOME', 'PICKUP_POINT', 'CASH_ON_DELIVERY')",
    )
