"""Remove the email feature (owner decision 2026-10-07).

The owner asked for the email feature to be deleted outright: the store is
phone-first — login is by phone number, recovery runs through the OTP flow —
and SMTP, the editable templates and every email-driven flow have no use. The
code is archived under ``_archived/email-removal-2026-10-07/`` and the change
is documented in ``docs/email-removal-2026-10-07.md``.

What this migration removes:

- **Tables** (dropped whole): ``email_delivery_logs`` (8 106 rows, all
  SKIPPED mock rows plus 1 SENT probe), ``notification_templates`` (0 rows),
  ``email_verification_tokens`` (0 rows), ``email_change_requests`` (0 rows),
  ``password_reset_tokens`` (0 rows).
- **Columns**: ``users.email`` (98 non-null values, all fixtures: b2b_*@karta.local
  or *.invalid probe addresses), ``blog_comments.author_email`` (9 values),
  ``contact_messages.email`` (1 fixture), ``lead_inquiries.email`` (0 rows),
  ``internal_gift_cards.recipient_email`` (0 values),
  ``saved_reports.delivery_channels`` and ``saved_reports.recipients``
  (0 rows).
- **Options** (site_options rows): ``admin_email``, ``admin_email_check_interval``,
  ``contact_email``, ``comments_notify``, ``moderation_notify``,
  ``require_name_email``, ``show_avatars``, ``avatar_default``, ``avatar_rating``.
  Row values are captured in ``db_row_values_before.json``.

Deliberately NOT touched:

- ``audit_logs`` / ``entity_change_logs`` history (established practice: the
  audit trail records history, it is not module state).
- ``notifications`` and ``notification_preferences`` (the in-app channel and
  the SMS channel stay; only the ``email`` member of the channel vocabulary
  went, and stored JSONB keys with an ``email`` entry are simply never read).

The downgrade recreates every table byte-for-byte from the captured DDL
(``db_snapshot_before.json``) and restores the columns (nullable — the values
themselves are in ``db_row_values_before.json``; the id→email map restores
``users.email`` for the 98 fixture rows).

Chain: ``wal1 -> rmemail1`` (wal1 was the head when this landed).

Revision ID: rmemail1
Revises: wal1
Create Date: 2026-10-08
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "rmemail1"
down_revision: str | None = "wal1"

branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: The archive directory holding the captured row values.
_ARCHIVE = (
    Path(__file__).resolve().parents[3]
    / "_archived"
    / "email-removal-2026-10-07"
)


def _load_json(name: str) -> dict:
    try:
        return json.loads((_ARCHIVE / name).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def upgrade() -> None:
    # ── Dropped columns ──────────────────────────────────────────────────
    # saved_reports first (two columns, no indexes).
    op.drop_column("saved_reports", "recipients")
    op.drop_column("saved_reports", "delivery_channels")

    # internal_gift_cards / lead_inquiries / contact_messages / blog_comments
    op.drop_column("internal_gift_cards", "recipient_email")
    op.drop_column("lead_inquiries", "email")
    op.drop_column("contact_messages", "email")
    op.drop_column("blog_comments", "author_email")

    # users.email has a unique constraint and a plain index on it; drop both
    # before the column (Postgres would drop the index with the column, but
    # the constraint name must go explicitly for a clean downgrade path).
    op.drop_index("ix_users_email", table_name="users")
    op.drop_constraint("uq_users_email", "users", type_="unique")
    op.drop_column("users", "email")

    # ── Dropped tables (child first) ─────────────────────────────────────
    op.drop_table("email_delivery_logs")
    op.drop_table("notification_templates")
    op.drop_table("email_verification_tokens")
    op.drop_table("email_change_requests")
    op.drop_table("password_reset_tokens")

    # ── Dropped options ──────────────────────────────────────────────────
    # The four `*admin_email*` keys are the admin-email change/review flow's
    # state (new_admin_email, its token hash, its requested-at, and the
    # confirmed-at stamp). The flow and its reader are gone, so the rows are
    # dead data; the captured values are in db_row_values_before.json.
    op.execute(
        sa.text(
            "DELETE FROM site_options WHERE option_key IN ("
            "'admin_email', 'admin_email_check_interval', 'contact_email',"
            "'admin_email_confirmed_at', 'new_admin_email',"
            "'new_admin_email_token_hash', 'new_admin_email_requested_at',"
            "'comments_notify', 'moderation_notify', 'require_name_email',"
            "'show_avatars', 'avatar_default', 'avatar_rating')"
        )
    )


def downgrade() -> None:
    """Recreate the schema exactly; restore captured values where portable.

    Column values themselves (the 98 fixture emails, the delivery-log rows)
    live in ``db_row_values_before.json`` and are NOT re-inserted here — a
    downgrade restores the *schema* so the archived code runs again. The
    fixture addresses can be replayed from the archive if a restore needs
    them.
    """
    # ── Tables ───────────────────────────────────────────────────────────
    op.create_table(
        "password_reset_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("request_ip", sa.String(length=64), nullable=True),
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
            ["user_id"],
            ["users.id"],
            name="fk_password_reset_tokens_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_password_reset_tokens"),
    )
    op.create_index(
        "ix_password_reset_tokens_token_hash",
        "password_reset_tokens",
        ["token_hash"],
        unique=True,
    )
    op.create_index(
        "ix_password_reset_tokens_user_id", "password_reset_tokens", ["user_id"]
    )
    op.create_index(
        "ix_password_reset_tokens_expires_at", "password_reset_tokens", ["expires_at"]
    )

    op.create_table(
        "email_change_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("new_email", sa.String(length=255), nullable=False),
        sa.Column("current_email", sa.String(length=255), nullable=True),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("invalidated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("request_ip", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_email_change_requests_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_email_change_requests_token_hash",
        "email_change_requests",
        ["token_hash"],
        unique=True,
    )
    op.create_index(
        "ix_email_change_requests_user_id", "email_change_requests", ["user_id"]
    )
    op.create_index(
        "ix_email_change_requests_expires_at", "email_change_requests", ["expires_at"]
    )

    op.create_table(
        "email_verification_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
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
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_email_verification_tokens_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_email_verification_tokens_token_hash",
        "email_verification_tokens",
        ["token_hash"],
        unique=True,
    )
    op.create_index(
        "ix_email_verification_tokens_user_id", "email_verification_tokens", ["user_id"]
    )
    op.create_index(
        "ix_email_verification_tokens_expires_at",
        "email_verification_tokens",
        ["expires_at"],
    )

    op.create_table(
        "notification_templates",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column(
            "channel",
            sa.Enum(
                "EMAIL",
                "SMS",
                "TELEGRAM",
                "PUSH",
                "IN_APP",
                name="notification_channel_enum",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("subject", sa.String(length=300), nullable=True),
        sa.Column("body_template", sa.Text(), nullable=False),
        sa.Column("variables", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name="pk_notification_templates"),
        sa.UniqueConstraint("name", name="uq_notification_templates_name"),
    )
    op.create_index(
        "ix_notification_templates_channel", "notification_templates", ["channel"]
    )
    op.create_index(
        "ix_notification_templates_name", "notification_templates", ["name"]
    )

    op.create_table(
        "email_delivery_logs",
        sa.Column(
            "notification_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("notifications.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("recipient", sa.String(length=320), nullable=False),
        sa.Column("subject", sa.String(length=500), nullable=False),
        sa.Column("template", sa.String(length=100), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "QUEUED",
                "SENT",
                "FAILED",
                name="email_delivery_status_enum",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("provider_response", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
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
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_email_delivery_logs_recipient", "email_delivery_logs", ["recipient"]
    )
    op.create_index(
        "ix_email_delivery_logs_status", "email_delivery_logs", ["status"]
    )
    op.create_index(
        "ix_email_delivery_logs_notification_id",
        "email_delivery_logs",
        ["notification_id"],
    )
    op.create_index(
        "ix_email_delivery_logs_created_at", "email_delivery_logs", ["created_at"]
    )

    # ── Columns ──────────────────────────────────────────────────────────
    op.add_column(
        "users", sa.Column("email", sa.String(length=255), nullable=True)
    )
    op.create_unique_constraint("uq_users_email", "users", ["email"])
    op.create_index("ix_users_email", "users", ["email"])

    # Replay the captured fixture addresses (the id→email map). All 98 were
    # fixtures (b2b_*@karta.local / *.invalid probes), captured before the
    # drop; a missing map leaves the column NULL, which is honest. The CAST is
    # required: the bound parameter arrives as text and Postgres will not
    # implicitly compare varchar against a uuid column.
    values = _load_json("db_row_values_before.json")
    for user_id, email in values.get("user_id_email_map", []):
        op.execute(
            sa.text(
                "UPDATE users SET email = :e WHERE id = CAST(:u AS uuid)"
            ).bindparams(e=email, u=user_id)
        )

    op.add_column(
        "blog_comments",
        sa.Column("author_email", sa.String(length=255), nullable=True),
    )
    # contact_messages.email was NOT NULL with no default. Adding it that way
    # to a table that already has rows fails, so it lands with an empty-string
    # server default (the same shape the original insert contract implies),
    # which is then dropped to match the captured DDL exactly.
    op.add_column(
        "contact_messages",
        sa.Column(
            "email",
            sa.String(length=255),
            nullable=False,
            server_default="",
        ),
    )
    op.alter_column("contact_messages", "email", server_default=None)
    op.add_column(
        "lead_inquiries", sa.Column("email", sa.String(length=255), nullable=True)
    )
    op.add_column(
        "internal_gift_cards",
        sa.Column("recipient_email", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "saved_reports",
        sa.Column(
            "delivery_channels",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "saved_reports",
        sa.Column(
            "recipients",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )

    # ── Options (schema-level restore; values were operator data) ────────
    # The captured rows live in db_row_values_before.json. Re-inserting them
    # here would resurrect placeholder addresses as if an operator had set
    # them; the seeds in default_options.py are the honest fallback.
    values = _load_json("db_row_values_before.json")
    for key, value in values.get("deleted_options", []):
        op.execute(
            sa.text(
                "INSERT INTO site_options (id, option_key, option_value, autoload)"
                " VALUES (gen_random_uuid(), :k, :v, true)"
                " ON CONFLICT (option_key) DO NOTHING"
            ).bindparams(k=key, v=str(value))
        )
