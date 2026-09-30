"""Add caption and description to media assets

Revision ID: 7ff14c859393
Revises: b752d5ceb564
Create Date: 2026-09-26 13:11:42.031244+03:30

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7ff14c859393"
down_revision: Union[str, None] = "b752d5ceb564"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('media_assets', sa.Column('caption', sa.String(length=1000), nullable=True))
    op.add_column('media_assets', sa.Column('description', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('media_assets', 'description')
    op.drop_column('media_assets', 'caption')
