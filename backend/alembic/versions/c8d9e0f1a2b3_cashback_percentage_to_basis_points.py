"""cashback_rules.percentage (float) -> percentage_bp (integer basis points)

Money-math hardening: cashback percentages were stored as double-precision
floats, which violates the project's integer-money constraint. Percentages
are now integer basis points (1% = 100 bp); existing rows are converted with
round(percentage * 100) and the float column is dropped.

Revision ID: c8d9e0f1a2b3
Revises: b6c7d8e9f0a1
Create Date: 2026-09-17
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "c8d9e0f1a2b3"
down_revision = "b6c7d8e9f0a1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "cashback_rules",
        sa.Column("percentage_bp", sa.Integer(), nullable=True),
    )
    # 1% = 100 bp; round() keeps e.g. 7.5% -> 750 bp exactly.
    op.execute(
        "UPDATE cashback_rules SET percentage_bp = round(percentage * 100)::int"
    )
    with op.batch_alter_table("cashback_rules") as batch_op:
        batch_op.alter_column("percentage_bp", existing_type=sa.Integer(), nullable=False)
    op.drop_column("cashback_rules", "percentage")


def downgrade() -> None:
    op.add_column(
        "cashback_rules",
        sa.Column("percentage", sa.Float(), nullable=True),
    )
    op.execute(
        "UPDATE cashback_rules SET percentage = percentage_bp / 100.0"
    )
    with op.batch_alter_table("cashback_rules") as batch_op:
        batch_op.alter_column("percentage", existing_type=sa.Float(), nullable=False)
    op.drop_column("cashback_rules", "percentage_bp")
