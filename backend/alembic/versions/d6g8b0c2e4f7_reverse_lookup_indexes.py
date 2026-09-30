"""Add reverse-lookup indexes on association tables.

Every many-to-many association table in this schema declares a
``UniqueConstraint(first_id, second_id)``, which creates a composite index.
That index serves queries filtering on the *first* column — "this user's
roles" — but not the reverse.

The reverse direction is queried in real code:

  * ``WHERE user_roles.role_id = ?`` — used by auth_service to resolve a
    role's members and by rbac_service on every role rename or delete
    (``rbac_service.py:253``)
  * ``WHERE role_permissions.permission_id = ?`` — used by auth_service when
    building a user's permission set and by rbac_service when deleting a
    permission (``rbac_service.py:105``)
  * ``WHERE product_tags.tag_id = ?`` — used by the storefront tag listing
    (``catalog_repository.py:740``)
  * ``WHERE blog_post_tags.tag_id = ?`` — the blog's tag archive

Without these, each reverse lookup is a sequential scan of the association
table. The tables are small today, so this is a prevention index rather than a
fix: the cost is a few hundred kilobytes, and the alternative is discovering
the scan after a catalogue grows to six figures of rows.

``IF NOT EXISTS`` keeps the migration re-runnable: the ORM models already
declare some of these, so a database created after this change may already
have them.

Revision ID: d6g8b0c2e4f7
Revises: c5f7a9b1d3e6
Create Date: 2026-09-25 16:30:00
"""

from __future__ import annotations

from alembic import op

revision = "d6g8b0c2e4f7"
down_revision = "c5f7a9b1d3e6"
branch_labels = None
depends_on = None

#: (index name, table, column) — the reverse side of each association pair.
REVERSE_INDEXES: tuple[tuple[str, str, str], ...] = (
    ("ix_user_roles_role_id", "user_roles", "role_id"),
    ("ix_role_permissions_permission_id", "role_permissions", "permission_id"),
    ("ix_product_tags_tag_id", "product_tags", "tag_id"),
    ("ix_blog_post_tags_tag_id", "blog_post_tags", "tag_id"),
)


def upgrade() -> None:
    for index_name, table, column in REVERSE_INDEXES:
        # CREATE INDEX CONCURRENTLY is not used: it cannot run inside the
        # transaction alembic opens, and these tables are small enough that a
        # brief lock is not measurable.
        op.execute(
            f'CREATE INDEX IF NOT EXISTS {index_name} ON {table} ({column})'
        )


def downgrade() -> None:
    for index_name, table, _column in REVERSE_INDEXES:
        op.execute(f"DROP INDEX IF EXISTS {index_name}")
