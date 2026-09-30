"""Add reusable blocks table

Revision ID: c1d2e3f4a5b6
Revises: ba316b31a4e6
Create Date: 2026-09-27 10:15:00.000000+03:30

WordPress "synced patterns": a named HTML fragment embedded into pages and
posts by token, so an edit to the block reaches every page that embeds it.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "c1d2e3f4a5b6"
down_revision: Union[str, None] = "ba316b31a4e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'reusable_blocks',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('slug', sa.String(220), nullable=False),
        sa.Column('body_html', sa.Text(), nullable=False, server_default=''),
        sa.Column('description', sa.String(500), nullable=True),
        sa.Column('status', sa.String(32), nullable=False, server_default='DRAFT'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('author_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['author_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slug'),
    )
    op.create_index('ix_reusable_blocks_slug', 'reusable_blocks', ['slug'])
    op.create_index('ix_reusable_blocks_status', 'reusable_blocks', ['status'])


def downgrade() -> None:
    op.drop_index('ix_reusable_blocks_status', table_name='reusable_blocks')
    op.drop_index('ix_reusable_blocks_slug', table_name='reusable_blocks')
    op.drop_table('reusable_blocks')
