"""privacy_requests: email confirmation token columns

P1 "حریم خصوصی: جریان ایمیلی تأیید درخواست". The request flow had one
confirmation path — an OTP over SMS — and a subject whose phone is out of
reach (changed number, travelling) had no way to confirm their own request.
WordPress's ``wp_send_user_request`` mails a link instead; this adds the same
for us, as a second path beside the OTP rather than a replacement.

Only the SHA-256 is stored, like every other token in this codebase; the
plaintext exists solely in the email.

Revision ID: prvmail1
Revises: mrgmn1
Create Date: 2026-10-02
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "prvmail1"
down_revision: str | None = "mrgmn1"

branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "privacy_requests",
        sa.Column("confirm_token_hash", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "privacy_requests",
        sa.Column(
            "confirm_token_expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("privacy_requests", "confirm_token_expires_at")
    op.drop_column("privacy_requests", "confirm_token_hash")