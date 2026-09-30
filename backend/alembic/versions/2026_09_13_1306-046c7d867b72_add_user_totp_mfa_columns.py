"""add user totp mfa columns

Revision ID: 046c7d867b72
Revises: d4e5f6a7b8c9
Create Date: 2026-09-13 13:06:15.944426+03:30

Deliberately minimal: only the two new ``users`` columns. The auto-generated
server_default noise against older tables is pre-existing drift and must not
be touched by this migration.

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "046c7d867b72"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Backfill pattern: add nullable, backfill existing rows, then enforce
    # NOT NULL — leaves no lingering server_default so the model and the
    # database stay in exact agreement.
    op.add_column("users", sa.Column("totp_secret", sa.String(length=64), nullable=True))
    op.add_column("users", sa.Column("totp_enabled", sa.Boolean(), nullable=True))
    op.execute("UPDATE users SET totp_enabled = false WHERE totp_enabled IS NULL")
    op.alter_column("users", "totp_enabled", existing_type=sa.Boolean(), nullable=False)


def downgrade() -> None:
    op.drop_column("users", "totp_enabled")
    op.drop_column("users", "totp_secret")
