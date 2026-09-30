"""Author archive slugs on users

Revision ID: q7r8s9t0u1v2
Revises: f7a8b9c0d1e2
Create Date: 2026-09-28 18:05:00.000000+03:30

The permalink structure accepts ``%author%``, but nothing could fill it: the
user table had no public identifier, so a structure like
``/blog/%author%/%postname%/`` produced ``/blog//my-post/`` — a broken link for
every post.

``users.author_slug`` is the public identity for ``/author/<slug>``. It is
nullable and deliberately not derived on read: deriving it from the display
name would change an already-published URL the moment somebody edits their
name, which is the exact failure ``slug_history`` exists to prevent.

Backfill: existing users get a slug from their profile name, falling back to a
prefix of their id so two users with the same (or no) name never collide —
the unique index would otherwise abort the migration.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "q7r8s9t0u1v2"
down_revision: str = "f7a8b9c0d1e2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("author_slug", sa.String(length=120), nullable=True),
    )
    # A partial unique index rather than a table constraint: several users may
    # legitimately have no author_slug (NULLs never conflict in a unique
    # index anyway), and this form also lets the slug be re-pointed freely.
    op.create_index(
        "ix_users_author_slug",
        "users",
        ["author_slug"],
        unique=True,
        postgresql_where=sa.text("author_slug IS NOT NULL"),
    )

    # Backfill inside the migration: a slug derived here is stable from the
    # moment the column exists, so no archive link is ever minted and orphaned
    # by a later rename.
    op.execute(
        """
        UPDATE users u
        SET author_slug = COALESCE(
            NULLIF(
                trim(
                    regexp_replace(
                        regexp_replace(
                            regexp_replace(
                                lower(COALESCE(p.first_name, '') || '-' ||
                                                 COALESCE(p.last_name, '')),
                                '[^a-z0-9]+', '-', 'g'
                            ),
                            '-{2,}', '-', 'g'
                        ),
                        '^-|-$', '', 'g'
                    )
                ),
                ''
            ),
            'author-' || replace(u.id::text, '-', '')
        )
        FROM user_profiles p
        WHERE p.user_id = u.id
        """
    )
    # A profile is optional, so anything still null needs the id fallback too.
    op.execute(
        """
        UPDATE users
        SET author_slug = 'author-' || replace(id::text, '-', '')
        WHERE author_slug IS NULL
        """
    )


def downgrade() -> None:
    op.drop_index("ix_users_author_slug", table_name="users")
    op.drop_column("users", "author_slug")
