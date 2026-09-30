"""Shipping upgrade v1: cancellation, cash-on-delivery, pickup points.

ERP benchmark gap analysis (feature #32 Shipping/carriers, P1). The gap:
carrier providers implemented ``cancel_shipment`` but no route exposed it,
and there was no COD or pickup-point support — both table stakes for Iranian
delivery (cash-on-delivery is a norm; Tipax/Post run agent networks).

- ``shipments`` gains: delivery_type, cod_amount_rial (+ collected_at),
  pickup_point_id, cancelled_at/reason, label_url.
- ``pickup_points``: cached carrier agent network, upserted by
  (provider, external_id) on each re-import.
- ``shipment_status_enum`` widens with 'cancelled' — the column is a
  native-enum=False VARCHAR + CHECK (project convention).

Additive only: existing columns are untouched; every new column is nullable
or has a server default, so pre-existing rows stay valid.

Revision ID: f1b3d5e7a9c2
Revises: e8a2c4d6f1b3
Create Date: 2026-09-25 03:40:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "f1b3d5e7a9c2"
down_revision = "e8a2c4d6f1b3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. pickup_points (created first: shipments references it) ─────────
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
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
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

    # ── 2. shipments: delivery mode, COD, pickup, cancellation ────────────
    # The default is the enum member NAME. This column stores names
    # (Enum(DeliveryType) without values_callable), and the column is
    # NOT NULL, so every pre-existing row is backfilled with whatever lands
    # here — a lowercase 'home' would be unmappable by the ORM and would also
    # violate the CHECK constraint added below.
    op.add_column(
        "shipments",
        sa.Column(
            "delivery_type",
            sa.String(length=32),
            nullable=False,
            server_default="HOME",
        ),
    )
    op.add_column(
        "shipments",
        sa.Column("cod_amount_rial", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "shipments",
        sa.Column("cod_collected_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "shipments",
        sa.Column("pickup_point_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "shipments",
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "shipments",
        sa.Column("cancelled_reason", sa.String(length=500), nullable=True),
    )
    op.add_column(
        "shipments",
        sa.Column("label_url", sa.String(length=500), nullable=True),
    )
    op.create_foreign_key(
        op.f("fk_shipments_pickup_point_id_pickup_points"),
        "shipments",
        "pickup_points",
        ["pickup_point_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_check_constraint(
        "ck_shipments_delivery_type",
        "shipments",
        "delivery_type IN ('HOME', 'PICKUP_POINT', 'CASH_ON_DELIVERY')",
    )
    op.create_check_constraint(
        "ck_shipments_cod_amount_non_negative",
        "shipments",
        "cod_amount_rial IS NULL OR cod_amount_rial >= 0",
    )

    # ── 3. widen the shipment-status vocabulary with 'cancelled' ──────────
    #
    # The literals are the enum member NAMES, not their lowercase values.
    # `Shipment.status` is `Enum(ShipmentStatus, native_enum=False)` with no
    # `values_callable`, and SQLAlchemy persists names by default — so the
    # column holds 'PENDING', not 'pending'. A constraint written from the
    # Python values looks obviously right and fails on every existing row; it
    # did exactly that on 173 shipments. Same for ck_shipments_delivery_type
    # above, and the downgrade below. Confirm with
    # `Enum(X).enums` before writing a CHECK over an enum column.
    op.execute(
        "ALTER TABLE shipments DROP CONSTRAINT IF EXISTS ck_shipments_status"
    )
    op.create_check_constraint(
        "ck_shipments_status",
        "shipments",
        "status IN ('PENDING', 'PROCESSING', 'SHIPPED', 'IN_TRANSIT', "
        "'DELIVERED', 'RETURNED', 'CANCELLED')",
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE shipments DROP CONSTRAINT IF EXISTS ck_shipments_status"
    )
    # Enum member names again (see the upgrade note): the ORM writes
    # 'PENDING', so a lowercase list here would reject every existing row on
    # a downgrade.
    op.create_check_constraint(
        "ck_shipments_status",
        "shipments",
        "status IN ('PENDING', 'PROCESSING', 'SHIPPED', 'IN_TRANSIT', "
        "'DELIVERED', 'RETURNED')",
    )
    op.drop_constraint(
        "ck_shipments_cod_amount_non_negative", "shipments", type_="check"
    )
    op.drop_constraint("ck_shipments_delivery_type", "shipments", type_="check")
    op.drop_constraint(
        op.f("fk_shipments_pickup_point_id_pickup_points"),
        "shipments",
        type_="foreignkey",
    )
    op.drop_column("shipments", "label_url")
    op.drop_column("shipments", "cancelled_reason")
    op.drop_column("shipments", "cancelled_at")
    op.drop_column("shipments", "pickup_point_id")
    op.drop_column("shipments", "cod_collected_at")
    op.drop_column("shipments", "cod_amount_rial")
    op.drop_column("shipments", "delivery_type")

    op.drop_index("ix_pickup_points_provider", table_name="pickup_points")
    op.drop_index("ix_pickup_points_city", table_name="pickup_points")
    op.drop_table("pickup_points")
