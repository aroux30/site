"""Add post format and gallery image ids to blog posts

Revision ID: 96f9e8f86d63
Revises: 13723d51dc09
Create Date: 2026-09-26 13:53:11.805048+03:30

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "96f9e8f86d63"
down_revision: Union[str, None] = "13723d51dc09"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'blog_posts',
        sa.Column(
            'post_format',
            sa.Enum('STANDARD', 'GALLERY', 'VIDEO', 'AUDIO', 'QUOTE', 'LINK', 'STATUS', 'IMAGE',
                     name='post_format_enum', native_enum=False),
            server_default=sa.text("'STANDARD'::character varying"),
            nullable=False,
        ),
    )
    op.add_column(
        'blog_posts',
        sa.Column('gallery_image_ids', postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('blog_posts', 'gallery_image_ids')
    op.drop_column('blog_posts', 'post_format')
