"""inventory_items.low_stock_threshold → nullable — per-product "no alert".

The owner's feedback: the low-stock threshold field was labeled "optional"
but leaving it empty fell back to the store-wide default (5), so there was
NO way to disable the low-stock alert for a single product.

New semantics (matches the storefront form):
- threshold set  → the admin is alerted when stock reaches that count;
- threshold NULL → this product NEVER triggers a low-stock alert. The daily
  scan and the sale-time transition simply skip NULL thresholds, and the
  admin editor shows an empty field for them.

Existing rows keep their stored values; only the constraint is relaxed.

Revision ID: invthr1
Revises: skunull1
Create Date: 2026-11-01
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "invthr1"
down_revision: str | None = "skunull1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "inventory_items",
        "low_stock_threshold",
        existing_type=sa.Integer(),
        nullable=True,
        server_default=None,
    )


def downgrade() -> None:
    # Backfill NULLs with the old store default before restoring NOT NULL.
    op.execute(
        "UPDATE inventory_items SET low_stock_threshold = 5 "
        "WHERE low_stock_threshold IS NULL"
    )
    op.alter_column(
        "inventory_items",
        "low_stock_threshold",
        existing_type=sa.Integer(),
        nullable=False,
        server_default=sa.text("5"),
    )
