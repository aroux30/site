"""Add WordPress parity features to blog

Revision ID: b752d5ceb564
Revises: d6g8b0c2e4f7
Create Date: 2026-09-26 12:41:36.912851+03:30

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "b752d5ceb564"
down_revision: Union[str, None] = "d6g8b0c2e4f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create post visibility enum
    op.execute("CREATE TYPE post_visibility_enum AS ENUM ('PUBLIC', 'PRIVATE', 'PASSWORD')")

    # Create comment status enum
    op.execute("CREATE TYPE comment_status_enum AS ENUM ('PENDING', 'APPROVED', 'SPAM', 'TRASH')")

    # Add new fields to blog_posts
    op.add_column('blog_posts', sa.Column('is_featured', sa.Boolean(), server_default=sa.text('false'), nullable=False))
    op.add_column('blog_posts', sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('blog_posts', sa.Column('visibility', sa.Enum('PUBLIC', 'PRIVATE', 'PASSWORD', name='post_visibility_enum', native_enum=False), server_default=sa.text("'PUBLIC'::character varying"), nullable=False))
    op.add_column('blog_posts', sa.Column('visibility_password', sa.String(length=255), nullable=True))
    op.add_column('blog_posts', sa.Column('allow_comments', sa.Boolean(), server_default=sa.text('true'), nullable=False))

    # Create indexes on new fields
    op.create_index('ix_blog_posts_is_featured', 'blog_posts', ['is_featured'])
    op.create_index('ix_blog_posts_deleted_at', 'blog_posts', ['deleted_at'])

    # Create blog_comments table
    op.create_table(
        'blog_comments',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('post_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('author_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('author_name', sa.String(length=200), nullable=True),
        sa.Column('author_email', sa.String(length=255), nullable=True),
        sa.Column('author_url', sa.String(length=500), nullable=True),
        sa.Column('author_ip', sa.String(length=45), nullable=True),
        sa.Column('author_user_agent', sa.String(length=500), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('status', sa.Enum('PENDING', 'APPROVED', 'SPAM', 'TRASH', name='comment_status_enum', native_enum=False), server_default=sa.text("'PENDING'::character varying"), nullable=False),
        sa.Column('parent_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['author_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['parent_id'], ['blog_comments.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['post_id'], ['blog_posts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes on blog_comments
    op.create_index('ix_blog_comments_post_id', 'blog_comments', ['post_id'])
    op.create_index('ix_blog_comments_author_id', 'blog_comments', ['author_id'])
    op.create_index('ix_blog_comments_parent_id', 'blog_comments', ['parent_id'])
    op.create_index('ix_blog_comments_status', 'blog_comments', ['status'])
    op.create_index('ix_blog_comments_created_at', 'blog_comments', ['created_at'])


def downgrade() -> None:
    # Drop blog_comments table and its indexes
    op.drop_index('ix_blog_comments_created_at', table_name='blog_comments')
    op.drop_index('ix_blog_comments_status', table_name='blog_comments')
    op.drop_index('ix_blog_comments_parent_id', table_name='blog_comments')
    op.drop_index('ix_blog_comments_author_id', table_name='blog_comments')
    op.drop_index('ix_blog_comments_post_id', table_name='blog_comments')
    op.drop_table('blog_comments')

    # Drop new blog_posts indexes
    op.drop_index('ix_blog_posts_deleted_at', table_name='blog_posts')
    op.drop_index('ix_blog_posts_is_featured', table_name='blog_posts')

    # Drop new blog_posts columns
    op.drop_column('blog_posts', 'allow_comments')
    op.drop_column('blog_posts', 'visibility_password')
    op.drop_column('blog_posts', 'visibility')
    op.drop_column('blog_posts', 'deleted_at')
    op.drop_column('blog_posts', 'is_featured')

    # Drop enums
    op.execute("DROP TYPE comment_status_enum")
    op.execute("DROP TYPE post_visibility_enum")

