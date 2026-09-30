"""Add blog post meta custom fields table

Revision ID: 13723d51dc09
Revises: 7ff14c859393
Create Date: 2026-09-26 13:31:56.417806+03:30

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "13723d51dc09"
down_revision: Union[str, None] = "7ff14c859393"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'blog_post_meta',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('post_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('meta_key', sa.String(length=255), nullable=False),
        sa.Column('meta_value', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['post_id'], ['blog_posts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('post_id', 'meta_key', name='uq_blog_post_meta_post_key'),
    )
    op.create_index('ix_blog_post_meta_post_id', 'blog_post_meta', ['post_id'])
    op.create_index('ix_blog_post_meta_meta_key', 'blog_post_meta', ['meta_key'])


def downgrade() -> None:
    op.drop_index('ix_blog_post_meta_meta_key', table_name='blog_post_meta')
    op.drop_index('ix_blog_post_meta_post_id', table_name='blog_post_meta')
    op.drop_table('blog_post_meta')
