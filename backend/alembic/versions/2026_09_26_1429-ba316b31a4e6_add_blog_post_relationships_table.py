"""Add blog post relationships table

Revision ID: ba316b31a4e6
Revises: 5ed5f59525e2
Create Date: 2026-09-26 14:29:48.964118+03:30

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "ba316b31a4e6"
down_revision: Union[str, None] = "5ed5f59525e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'blog_post_relationships',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('source_post_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('target_post_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('relationship_type', sa.String(50), nullable=False, server_default='related'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['source_post_id'], ['blog_posts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['target_post_id'], ['blog_posts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('source_post_id', 'target_post_id', 'relationship_type', name='uq_blog_post_rel_src_tgt_type'),
    )
    op.create_index('ix_blog_post_rel_source', 'blog_post_relationships', ['source_post_id'])
    op.create_index('ix_blog_post_rel_target', 'blog_post_relationships', ['target_post_id'])
    op.create_index('ix_blog_post_rel_type', 'blog_post_relationships', ['relationship_type'])


def downgrade() -> None:
    op.drop_table('blog_post_relationships')
