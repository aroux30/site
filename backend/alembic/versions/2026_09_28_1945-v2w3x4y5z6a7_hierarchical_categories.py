"""Hierarchical blog categories

Revision ID: v2w3x4y5z6a7
Revises: u1v2w3x4y5z6
Create Date: 2026-09-28 19:45:00.000000+03:00

Blog categories were flat: name and slug only, so an operator could not express
"لپ‌تاپ / گیمینگ" and the category archive had no description to show. The
custom-taxonomy terms already carried parent_id/description/position, so this
brings the built-in categories in line rather than inventing a second shape.

``parent_id`` is ON DELETE SET NULL: removing a category promotes its children
to top level instead of cascading the delete. A child is a thing an operator
created, and silently destroying a subtree they never asked to remove is the
wrong reading of "delete this category".

The table was empty at the time of this migration, so no backfill is needed.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "v2w3x4y5z6a7"
down_revision: str = "u1v2w3x4y5z6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("blog_categories", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("blog_categories", sa.Column("parent_id", sa.Uuid(), nullable=True))
    op.add_column(
        "blog_categories",
        sa.Column("position", sa.Integer(), server_default="0", nullable=False),
    )
    op.create_foreign_key(
        "fk_blog_categories_parent_id",
        "blog_categories",
        "blog_categories",
        ["parent_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_blog_categories_parent_id", "blog_categories", ["parent_id"])


def downgrade() -> None:
    op.drop_index("ix_blog_categories_parent_id", table_name="blog_categories")
    op.drop_constraint("fk_blog_categories_parent_id", "blog_categories", type_="foreignkey")
    op.drop_column("blog_categories", "position")
    op.drop_column("blog_categories", "parent_id")
    op.drop_column("blog_categories", "description")
