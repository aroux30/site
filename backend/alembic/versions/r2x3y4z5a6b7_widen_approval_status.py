"""Widen approval_requests.status for the IN_REVIEW member.

`ApprovalStatus.IN_REVIEW` is the longest member value (``"in_review"``, nine
characters) but the column is ``varchar(8)`` — SQLAlchemy derives the width
from the longest member *name* when the enum is created, and the name
``IN_REVIEW`` is eight. Multi-step approvals promote a request to IN_REVIEW in
``approval_service`` after the first signature, so the second signature of
every chained approval failed with a StringDataRightTruncationError at flush.

Widened to 20 to match the sibling fix on ``email_delivery_logs.status`` and
to leave headroom for future members.

Revision ID: r2x3y4z5a6b7
Revises: q1w2e3r4t5y6
Create Date: 2026-09-29
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "r2x3y4z5a6b7"
down_revision: Union[str, None] = "q1w2e3r4t5y6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

#: must cover the longest member value; see test_tool_blind_regressions.py
_TARGET_LENGTH = 20


def upgrade() -> None:
    op.alter_column(
        "approval_requests",
        "status",
        existing_type=sa.String(length=8),
        type_=sa.String(length=_TARGET_LENGTH),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "approval_requests",
        "status",
        existing_type=sa.String(length=_TARGET_LENGTH),
        type_=sa.String(length=8),
        existing_nullable=False,
    )
