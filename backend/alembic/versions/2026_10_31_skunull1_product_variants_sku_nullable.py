"""product_variants.sku → nullable — SKU becomes truly optional.

The owner's directive: leaving the SKU empty must NOT auto-generate a code —
a product can simply have no warehouse code. The column was NOT NULL, which
is why auto-generation existed at all; this migration makes it nullable so
"empty means empty".

Uniqueness is kept: Postgres allows multiple NULLs in a UNIQUE index, so
several products without a SKU coexist while typed codes stay unique.

Revision ID: skunull1
Revises: stkstat1
Create Date: 2026-10-31
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "skunull1"
down_revision: str | None = "stkstat1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("product_variants", "sku", nullable=True)


def downgrade() -> None:
    # Backfill NULLs with deterministic codes before restoring NOT NULL.
    op.execute(
        "UPDATE product_variants SET sku = 'SKU-' || left(md5(id::text), 8) "
        "WHERE sku IS NULL"
    )
    op.alter_column("product_variants", "sku", nullable=False)
