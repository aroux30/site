"""Add custom taxonomies and terms tables

Revision ID: 088d59a38212
Revises: 96f9e8f86d63
Create Date: 2026-09-26 13:54:44.480420+03:30

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "088d59a38212"
down_revision: Union[str, None] = "96f9e8f86d63"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Custom taxonomies
    op.create_table(
        'custom_taxonomies',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('slug', sa.String(220), unique=True, nullable=False),
        sa.Column('description', sa.String(500), nullable=True),
        sa.Column('hierarchical', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_custom_taxonomies_slug', 'custom_taxonomies', ['slug'])

    # Custom taxonomy terms
    op.create_table(
        'custom_taxonomy_terms',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('taxonomy_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('slug', sa.String(220), nullable=False),
        sa.Column('description', sa.String(500), nullable=True),
        sa.Column('parent_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('position', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['taxonomy_id'], ['custom_taxonomies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['parent_id'], ['custom_taxonomy_terms.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('taxonomy_id', 'slug', name='uq_custom_taxonomy_terms_tax_slug'),
    )
    op.create_index('ix_custom_taxonomy_terms_taxonomy_id', 'custom_taxonomy_terms', ['taxonomy_id'])
    op.create_index('ix_custom_taxonomy_terms_parent_id', 'custom_taxonomy_terms', ['parent_id'])
    op.create_index('ix_custom_taxonomy_terms_slug', 'custom_taxonomy_terms', ['slug'])

    # Blog post <-> term association
    op.create_table(
        'blog_post_terms',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('post_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('term_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['post_id'], ['blog_posts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['term_id'], ['custom_taxonomy_terms.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('post_id', 'term_id', name='uq_blog_post_terms_post_term'),
    )
    op.create_index('ix_blog_post_terms_post_id', 'blog_post_terms', ['post_id'])
    op.create_index('ix_blog_post_terms_term_id', 'blog_post_terms', ['term_id'])


def downgrade() -> None:
    op.drop_table('blog_post_terms')
    op.drop_table('custom_taxonomy_terms')
    op.drop_table('custom_taxonomies')
