"""Widen the reconciliation finding-type column.

``native_enum=False`` stores an ``Enum`` as a plain VARCHAR sized to its
longest member. The original members topped out at 29 characters, so the
column was created as ``VARCHAR(29)`` — and the lifecycle auditor's
``ORDER_DELIVERED_SHIPMENT_OPEN`` is *exactly* 29. At the limit, any future
finding type one character longer would raise a database error at insert time,
in a background Celery sweep, where it would surface as a failed audit rather
than an obvious bug.

Widening the column ahead of the growth keeps the enum a code-level concern:
adding a finding type stays a one-line change with no migration.

Revision ID: c8e1f4a7b2d6
Revises: b7d3e5f9a1c4
Create Date: 2026-09-19 15:10:00

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "c8e1f4a7b2d6"
down_revision = "b7d3e5f9a1c4"
branch_labels = None
depends_on = None

#: Comfortably above the longest current member (29) and any near-term one.
_WIDENED_LENGTH = 64


def upgrade() -> None:
    op.alter_column(
        "reconciliation_findings",
        "finding_type",
        existing_type=sa.String(length=29),
        type_=sa.String(length=_WIDENED_LENGTH),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "reconciliation_findings",
        "finding_type",
        existing_type=sa.String(length=_WIDENED_LENGTH),
        type_=sa.String(length=29),
        existing_nullable=False,
    )