"""USD→Toman automatic price updater (Nobitex), ported from the owner's
WordPress plugin "Nobitex Price Updater Ultimate" v4.5.0.

Two additive changes, no existing data touched:

* ``product_variants.usd_price`` / ``usd_sale_price`` — the plugin's
  ``_usd_price`` / ``_usd_sale_price`` product meta, as real NUMERIC columns
  (money is never a float). NULL = the variant is NOT managed by the sweep.
* ``usd_price_updates`` — the plugin's rotating text log replaced by a
  queryable table (rate used, outcome, per-variant before/after as JSONB).

Every existing variant gets NULL USD prices, so installing this changes no
price and no storefront behaviour until an operator sets a USD price on a
variant and the updater runs.

Revision ID: curr1
Revises: refbon2
Create Date: 2026-10-16
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "curr1"
down_revision: str | None = "refbon2"

branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "product_variants",
        sa.Column("usd_price", sa.Numeric(precision=12, scale=2), nullable=True),
    )
    op.add_column(
        "product_variants",
        sa.Column("usd_sale_price", sa.Numeric(precision=12, scale=2), nullable=True),
    )
    # The sweep's working set query filters on usd_price IS NOT NULL on every
    # run; a partial index keeps that cheap as the catalog grows without
    # indexing the (majority) unmanaged rows.
    op.create_index(
        "ix_product_variants_usd_price",
        "product_variants",
        ["usd_price"],
        postgresql_where=sa.text("usd_price IS NOT NULL"),
    )

    op.create_table(
        "usd_price_updates",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rate_rial", sa.Integer(), nullable=False),
        sa.Column("rate_source", sa.String(length=20), nullable=False, server_default="api"),
        sa.Column("updated_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("scheduled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="success"),
        sa.Column("error", sa.String(length=500), nullable=True),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_usd_price_updates_created_at", "usd_price_updates", ["created_at"])
    op.create_index("ix_usd_price_updates_status", "usd_price_updates", ["status"])


def downgrade() -> None:
    op.drop_index("ix_usd_price_updates_status", table_name="usd_price_updates")
    op.drop_index("ix_usd_price_updates_created_at", table_name="usd_price_updates")
    op.drop_table("usd_price_updates")
    op.drop_index("ix_product_variants_usd_price", table_name="product_variants")
    op.drop_column("product_variants", "usd_sale_price")
    op.drop_column("product_variants", "usd_price")
