"""variation swatches: swatch payload columns on attribute_values

Revision ID: swatch1
Revises: invthr1
Create Date: 2026-11-04

woo-variation-swatches parity: a COLOR attribute value carries its hex, an
IMAGE one its thumbnail URL, and any value an optional hover tooltip. The
AttributeType VARCHAR gains no migration — native_enum=False renders it as a
plain VARCHAR, so the new IMAGE/LABEL members need no DDL.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "swatch1"
down_revision = "paddon1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "attribute_values",
        sa.Column("color", sa.String(30), nullable=True),
    )
    op.add_column(
        "attribute_values",
        sa.Column("image_url", sa.String(500), nullable=True),
    )
    op.add_column(
        "attribute_values",
        sa.Column("tooltip", sa.String(300), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("attribute_values", "tooltip")
    op.drop_column("attribute_values", "image_url")
    op.drop_column("attribute_values", "color")
