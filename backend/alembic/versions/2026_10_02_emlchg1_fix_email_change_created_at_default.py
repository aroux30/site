"""email_change_requests.created_at/updated_at: restore the server default

The migration that created ``email_change_requests`` declared both timestamp
columns ``NOT NULL`` but gave them no default, while the model inherits
``TimestampMixin`` — whose columns carry ``server_default=func.now()`` and rely
on the database to fill them. The two disagreed, and the database won: every
insert raised ``NotNullViolationError``, so the email-change flow (request,
confirmation mail, the whole two-step change) had never once worked on a
database created from migrations.

Found while building the sibling ``email_verification_tokens`` table, whose
first test insert failed the same way. A direct probe of the live database then
confirmed this table is the only other one in the schema with the mismatch.

Revision ID: emlchg1
Revises: emlver1
Create Date: 2026-10-02
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "emlchg1"
down_revision: str | None = "emlver1"

branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "email_change_requests",
        "created_at",
        server_default=sa.text("now()"),
        existing_type=sa.DateTime(timezone=True),
        existing_nullable=False,
    )
    op.alter_column(
        "email_change_requests",
        "updated_at",
        server_default=sa.text("now()"),
        existing_type=sa.DateTime(timezone=True),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "email_change_requests",
        "updated_at",
        server_default=None,
        existing_type=sa.DateTime(timezone=True),
        existing_nullable=False,
    )
    op.alter_column(
        "email_change_requests",
        "created_at",
        server_default=None,
        existing_type=sa.DateTime(timezone=True),
        existing_nullable=False,
    )