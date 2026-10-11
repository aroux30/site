"""Advanced redirects: nullable target, regex flag, note.

Rank Math's Redirections module supports 301/302/307/308/410/451, a Regex
comparison mode with $1 back-references, and an operator note per rule. The
table carried only from/to/status/is_active/hit_count, and `to_path` was NOT
NULL — so a 410 (Gone) rule, which by definition has no destination, could
not be stored at all.

Changes:

- ``to_path`` becomes NULLable (410/451 rules have no target).
- ``is_regex`` (default false) — existing rows keep exact/wildcard matching.
- ``note`` (nullable) — operator-facing memo.

Revision ID: seord1
Revises: seotm1
Create Date: 2026-10-09
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "seord1"
down_revision: str | None = "seotm1"

branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("seo_redirects", "to_path", existing_type=sa.String(500), nullable=True)
    op.add_column(
        "seo_redirects",
        sa.Column("is_regex", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column("seo_redirects", sa.Column("note", sa.String(length=500), nullable=True))


def downgrade() -> None:
    # Rows a 410/451 rule left with NULL target would violate NOT NULL on the
    # way back. They are deleted rather than given a fabricated destination —
    # a wrong redirect is worse than a missing rule, and the rule's meaning
    # (410/451) cannot survive a NOT NULL target column anyway.
    op.execute(sa.text("DELETE FROM seo_redirects WHERE to_path IS NULL"))
    op.drop_column("seo_redirects", "note")
    op.drop_column("seo_redirects", "is_regex")
    op.alter_column("seo_redirects", "to_path", existing_type=sa.String(500), nullable=False)
