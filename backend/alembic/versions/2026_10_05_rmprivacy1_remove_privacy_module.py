"""Remove the Privacy / GDPR module (owner decision 2026-10-05).

The owner asked for «حریم خصوصی و GDPR» to be deleted outright — it has no
use in a retail storefront. The code is archived under
``_archived/privacy-scheduled-removal-2026-10-05/``.

What goes with this migration:

- **``privacy_requests``** — the data-subject request queue (GDPR export/erase
  workflow). Verified at removal time (live probe 2026-10-05): 2 rows, both
  test fixtures from the parity work (one PARTIAL, one COMPLETED, both with
  NULL payloads and NULL subject emails), zero foreign keys pointing into the
  table from anywhere else.
- **``privacy.*`` site options** — ``privacy.ip_retention_days``,
  ``privacy.export_retention_hours`` and ``privacy.policy_page``. Two rows
  existed in the live database (``export_retention_hours``, ``policy_page``);
  the snapshot with exact values is in the archive's
  ``db_snapshot_before.json``.

Not touched on purpose: the ``users`` table (the GDPR export/erase endpoints
operated on user rows; the rows themselves are the store's customers), and
``core/security/ip_anonymize.py``'s ``anonymize_ip`` — the registration
notice still masks the signup IP through it.

``downgrade()`` recreates ``privacy_requests`` exactly as the live database
had it at removal time — ``p9r1v2w3x4y5`` plus the ``prvmail1`` confirmation
token columns — and restores the two option rows with their exact ids and
timestamps from the snapshot. The 2 request rows are *not* restored: they were
test fixtures, and the removed queue was the only thing that could write them.

Revision ID: rmprivacy1
Revises: rmi18n2
Create Date: 2026-10-05
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "rmprivacy1"
down_revision = "rmi18n2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Children first: indexes, then the table.
    op.drop_index("ix_privacy_requests_status_created_at", table_name="privacy_requests")
    op.drop_index("ix_privacy_requests_user_id_status", table_name="privacy_requests")
    op.drop_table("privacy_requests")

    # The options the module read. LIKE covers every privacy.* key; the two
    # that existed are in the snapshot.
    op.execute("DELETE FROM site_options WHERE option_key LIKE 'privacy.%'")


def downgrade() -> None:
    """Recreate the table and the two option rows as of removal time.

    Column set is ``p9r1v2w3x4y5`` + ``prvmail1`` (confirm_token_hash,
    confirm_token_expires_at). Enum columns are VARCHAR + CHECK
    (``native_enum=False``); the live table's stored values are the member
    *names* (``EXPORT``/``ERASE``, ``PENDING``/``PROCESSING``/``COMPLETED``/
    ``PARTIAL``/``REJECTED``), per this schema's enum-storage contract.
    """
    op.create_table(
        "privacy_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "type",
            sa.Enum(
                "EXPORT",
                "ERASE",
                name="privacy_request_type_enum",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING",
                "PROCESSING",
                "COMPLETED",
                "PARTIAL",
                "REJECTED",
                name="privacy_request_status_enum",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("admin_note", sa.Text(), nullable=True),
        sa.Column("resolved_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("result_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("confirm_token_hash", sa.String(length=64), nullable=True),
        sa.Column("confirm_token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_privacy_requests_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_privacy_requests"),
    )
    op.create_index(
        "ix_privacy_requests_user_id_status",
        "privacy_requests",
        ["user_id", "status"],
    )
    op.create_index(
        "ix_privacy_requests_status_created_at",
        "privacy_requests",
        ["status", "created_at"],
    )

    # Restore the two option rows with their exact ids and timestamps from
    # db_snapshot_before.json. Explicit CASTs: asyncpg refuses to compare a
    # uuid column against a plain string parameter (the rmi18n1 lesson).
    op.execute(
        sa.text(
            """
            INSERT INTO site_options (id, option_key, option_value, autoload, created_at, updated_at)
            VALUES (
                CAST('ab66daf9-7615-4690-8223-2e2f440623ff' AS uuid),
                'privacy.export_retention_hours', '24', true,
                CAST('2026-10-02T16:41:14.976343+00:00' AS timestamptz),
                CAST('2026-10-02T16:41:14.994183+00:00' AS timestamptz)
            )
            ON CONFLICT (id) DO NOTHING
            """
        )
    )
    op.execute(
        sa.text(
            """
            INSERT INTO site_options (id, option_key, option_value, autoload, created_at, updated_at)
            VALUES (
                CAST('70c98849-ec71-461a-9164-035a70a17310' AS uuid),
                'privacy.policy_page', NULL, true,
                CAST('2026-10-02T19:23:09.259105+00:00' AS timestamptz),
                CAST('2026-10-03T21:46:21.938346+00:00' AS timestamptz)
            )
            ON CONFLICT (id) DO NOTHING
            """
        )
    )
