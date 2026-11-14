"""Category custom fields: full add-on parity with per-product addon fields.

Revision ID: caddon1
Revises: paddon1
Create Date: 2026-11-05

Additive-only: four nullable columns on ``category_custom_fields``
(description, display, min_val, max_val) so category-scoped order fields can
carry the same shape the per-product add-on fields already do (helper line,
multiple-choice display style, character/quantity/price restrictions).
No existing column is touched; legacy text/number/select rows keep working.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "caddon1"
down_revision = "swatch1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "category_custom_fields",
        sa.Column("description", sa.String(length=500), nullable=True),
    )
    op.add_column(
        "category_custom_fields",
        sa.Column("display", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "category_custom_fields",
        sa.Column("min_val", sa.Integer(), nullable=True),
    )
    op.add_column(
        "category_custom_fields",
        sa.Column("max_val", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("category_custom_fields", "max_val")
    op.drop_column("category_custom_fields", "min_val")
    op.drop_column("category_custom_fields", "display")
    op.drop_column("category_custom_fields", "description")
