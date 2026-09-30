"""Add custom post types tables

Revision ID: 60ffa5b4074e
Revises: 088d59a38212
Create Date: 2026-09-26 14:00:45.207202+03:30

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "60ffa5b4074e"
down_revision: Union[str, None] = "088d59a38212"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'custom_post_types',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('slug', sa.String(220), unique=True, nullable=False),
        sa.Column('description', sa.String(500), nullable=True),
        sa.Column('icon', sa.String(50), nullable=True),
        sa.Column('field_schema', postgresql.JSONB(), nullable=True),
        sa.Column('supports_categories', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('supports_comments', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_custom_post_types_slug', 'custom_post_types', ['slug'])

    op.create_table(
        'custom_post_entries',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('post_type_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('slug', sa.String(550), nullable=False),
        sa.Column('fields', postgresql.JSONB(), nullable=True),
        sa.Column('excerpt', sa.String(1000), nullable=True),
        sa.Column('cover_image_url', sa.String(500), nullable=True),
        sa.Column('status', sa.Enum('DRAFT', 'PUBLISHED', 'ARCHIVED', name='custom_post_type_status_enum', native_enum=False), server_default=sa.text("'DRAFT'::character varying"), nullable=False),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('author_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('position', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['post_type_id'], ['custom_post_types.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['author_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('post_type_id', 'slug', name='uq_custom_post_entries_type_slug'),
    )
    op.create_index('ix_custom_post_entries_post_type_id', 'custom_post_entries', ['post_type_id'])
    op.create_index('ix_custom_post_entries_slug', 'custom_post_entries', ['slug'])
    op.create_index('ix_custom_post_entries_status', 'custom_post_entries', ['status'])
    op.create_index('ix_custom_post_entries_published_at', 'custom_post_entries', ['published_at'])


def downgrade() -> None:
    op.drop_table('custom_post_entries')
    op.drop_table('custom_post_types')
