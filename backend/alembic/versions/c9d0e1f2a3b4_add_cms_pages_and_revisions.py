"""Add CMS pages and page revisions; merge the two migration heads.

The ``CmsPage``/``CmsPageRevision`` models shipped in ``content/domain/models.py``
without a migration, so the tables never existed in any database. This revision
creates them.

It also merges the two heads present in the history (``a1c8f2b3d4e5`` from the
order price-snapshot branch and ``b3c4d5e6f7a8`` from the multi-warehouse
branch), both of which branch off ``f8a2b4c6d9e1``. Without the merge,
``alembic upgrade head`` aborts with "Multiple head revisions are present".

Revision ID: c9d0e1f2a3b4
Revises: a1c8f2b3d4e5, b3c4d5e6f7a8
Create Date: 2026-09-24 00:30:00

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c9d0e1f2a3b4"
down_revision = ("a1c8f2b3d4e5", "b3c4d5e6f7a8")
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cms_pages",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("slug", sa.String(length=220), nullable=False),
        sa.Column("body_html", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("excerpt", sa.String(length=1000), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("seo_title", sa.String(length=200), nullable=True),
        sa.Column("seo_description", sa.String(length=500), nullable=True),
        sa.Column("author_id", sa.UUID(), nullable=True),
        sa.Column("revision_number", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["author_id"],
            ["users.id"],
            name=op.f("fk_cms_pages_author_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cms_pages")),
        sa.UniqueConstraint("slug", name=op.f("uq_cms_pages_slug")),
    )
    op.create_index("ix_cms_pages_slug", "cms_pages", ["slug"], unique=False)
    op.create_index("ix_cms_pages_status", "cms_pages", ["status"], unique=False)
    op.create_index("ix_cms_pages_published_at", "cms_pages", ["published_at"], unique=False)

    op.create_table(
        "cms_page_revisions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("page_id", sa.UUID(), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("slug", sa.String(length=220), nullable=False),
        sa.Column("body_html", sa.Text(), nullable=False),
        sa.Column("excerpt", sa.String(length=1000), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("seo_title", sa.String(length=200), nullable=True),
        sa.Column("seo_description", sa.String(length=500), nullable=True),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["page_id"],
            ["cms_pages.id"],
            name=op.f("fk_cms_page_revisions_page_id_cms_pages"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_cms_page_revisions_created_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cms_page_revisions")),
        sa.UniqueConstraint(
            "page_id", "revision_number", name="uq_cms_page_revisions_page_rev"
        ),
    )
    op.create_index(
        "ix_cms_page_revisions_page_id", "cms_page_revisions", ["page_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_cms_page_revisions_page_id", table_name="cms_page_revisions")
    op.drop_table("cms_page_revisions")
    op.drop_index("ix_cms_pages_published_at", table_name="cms_pages")
    op.drop_index("ix_cms_pages_status", table_name="cms_pages")
    op.drop_index("ix_cms_pages_slug", table_name="cms_pages")
    op.drop_table("cms_pages")
