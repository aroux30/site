"""Add P2 WordPress features: hierarchical pages, slug history, options table, comment meta

Revision ID: 5ed5f59525e2
Revises: 60ffa5b4074e
Create Date: 2026-09-26 14:19:50.606381+03:30

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "5ed5f59525e2"
down_revision: Union[str, None] = "60ffa5b4074e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── #31 Hierarchical pages: add parent_id + menu_order to cms_pages ──
    op.add_column('cms_pages', sa.Column('parent_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('cms_pages', sa.Column('menu_order', sa.Integer(), server_default=sa.text('0'), nullable=False))
    op.add_column('cms_pages', sa.Column('page_template', sa.String(100), nullable=True))
    op.create_foreign_key('fk_cms_pages_parent_id', 'cms_pages', 'cms_pages', ['parent_id'], ['id'], ondelete='SET NULL')
    op.create_index('ix_cms_pages_parent_id', 'cms_pages', ['parent_id'])
    op.create_index('ix_cms_pages_menu_order', 'cms_pages', ['menu_order'])

    # ── #34 Options/Settings table (wp_options parity) ──
    op.create_table(
        'site_options',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('option_key', sa.String(255), unique=True, nullable=False),
        sa.Column('option_value', sa.Text(), nullable=True),
        sa.Column('autoload', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_site_options_option_key', 'site_options', ['option_key'])
    op.create_index('ix_site_options_autoload', 'site_options', ['autoload'])

    # ── #37 Comment meta (key-value per comment) ──
    op.create_table(
        'blog_comment_meta',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('comment_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('meta_key', sa.String(255), nullable=False),
        sa.Column('meta_value', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['comment_id'], ['blog_comments.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('comment_id', 'meta_key', name='uq_blog_comment_meta_comment_key'),
    )
    op.create_index('ix_blog_comment_meta_comment_id', 'blog_comment_meta', ['comment_id'])

    # ── #40 Slug history for auto-redirect ──
    op.create_table(
        'slug_history',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('resource_type', sa.String(50), nullable=False),
        sa.Column('resource_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('old_slug', sa.String(550), nullable=False),
        sa.Column('new_slug', sa.String(550), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_slug_history_old_slug', 'slug_history', ['old_slug'])
    op.create_index('ix_slug_history_resource', 'slug_history', ['resource_type', 'resource_id'])

    # ── #32 Term meta (key-value per category/tag) ──
    op.create_table(
        'blog_term_meta',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('term_type', sa.String(50), nullable=False),
        sa.Column('term_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('meta_key', sa.String(255), nullable=False),
        sa.Column('meta_value', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('term_type', 'term_id', 'meta_key', name='uq_blog_term_meta_term_key'),
    )
    op.create_index('ix_blog_term_meta_term', 'blog_term_meta', ['term_type', 'term_id'])

    # ── #33 User meta (key-value per user) ──
    op.create_table(
        'user_meta',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('meta_key', sa.String(255), nullable=False),
        sa.Column('meta_value', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'meta_key', name='uq_user_meta_user_key'),
    )
    op.create_index('ix_user_meta_user_id', 'user_meta', ['user_id'])

    # ── #43 Attachment to post: link media to a blog post ──
    op.add_column('media_assets', sa.Column('post_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key('fk_media_assets_post_id', 'media_assets', 'blog_posts', ['post_id'], ['id'], ondelete='SET NULL')
    op.create_index('ix_media_assets_post_id', 'media_assets', ['post_id'])


def downgrade() -> None:
    op.drop_index('ix_media_assets_post_id', table_name='media_assets')
    op.drop_constraint('fk_media_assets_post_id', 'media_assets', type_='foreignkey')
    op.drop_column('media_assets', 'post_id')

    op.drop_table('user_meta')
    op.drop_table('blog_term_meta')
    op.drop_table('slug_history')
    op.drop_table('blog_comment_meta')
    op.drop_table('site_options')

    op.drop_index('ix_cms_pages_menu_order', table_name='cms_pages')
    op.drop_index('ix_cms_pages_parent_id', table_name='cms_pages')
    op.drop_constraint('fk_cms_pages_parent_id', 'cms_pages', type_='foreignkey')
    op.drop_column('cms_pages', 'page_template')
    op.drop_column('cms_pages', 'menu_order')
    op.drop_column('cms_pages', 'parent_id')
