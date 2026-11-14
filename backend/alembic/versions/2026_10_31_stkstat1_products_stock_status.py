"""products.stock_status — WooCommerce "Stock status" parity.

WooCommerce keeps a manual per-product stock status (instock / outofstock /
onbackorder) so a shop can mark an item unavailable WITHOUT turning on stock
counting. Our catalog had no such field: an untracked product
(``track_inventory = False``) was always buyable, so the admin had no way to
say "this digital item is temporarily unavailable" short of archiving it.

This migration adds ``products.stock_status`` (``instock`` | ``outofstock``;
``onbackorder`` is derived from the inventory ledger's backorder flag at
runtime, mirroring how WooCommerce computes it for tracked products). Every
existing row defaults to ``instock`` — the exact behavior the storefront had
before this column existed, so nothing changes for current data.

Revision ID: stkstat1
Revises: ordnum1
Create Date: 2026-10-31
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "stkstat1"
down_revision: str | None = "ordnum1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column(
            "stock_status",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'instock'"),
        ),
    )
    # Guard the storefront's hottest filter (in-stock only) and admin list.
    op.create_index(
        "ix_products_stock_status", "products", ["stock_status"]
    )


def downgrade() -> None:
    op.drop_index("ix_products_stock_status", table_name="products")
    op.drop_column("products", "stock_status")
