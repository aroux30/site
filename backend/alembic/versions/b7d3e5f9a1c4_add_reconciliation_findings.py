"""Add durable reconciliation findings.

The payment reconciliation scanner needs storage that survives restarts and is
deduplicated across at-least-once runs. It is deliberately additive: the
existing in-memory operational exception center stays as-is (it is a real-time
alerting view, not durable storage), and ``audit_logs`` remains the immutable
trail of who did what.

``dedupe_key`` carries a UNIQUE constraint — that constraint IS the
deduplication guarantee. The scanner upserts with
``INSERT … ON CONFLICT (dedupe_key) DO UPDATE``, bumping ``occurrence_count``
and ``last_detected_at`` instead of inserting a second row for the same
condition.

Entity references are text, not foreign keys: a finding is evidence *about* a
payment/order/refund/webhook and must stay readable even if that row is later
removed. An FK would either block the delete or cascade the evidence away.

AWARENESS: if the table already exists (a partially applied deploy), the
create fails. Drop the table and re-run; the scanner rebuilds its findings on
the next pass, since findings are derived, not authoritative.

Revision ID: b7d3e5f9a1c4
Revises: a3f9c1e7d2b4
Create Date: 2026-09-19 07:40:00

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "b7d3e5f9a1c4"
down_revision = "a3f9c1e7d2b4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reconciliation_findings",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("dedupe_key", sa.String(length=255), nullable=False),
        sa.Column(
            "finding_type",
            sa.Enum(
                "PAYMENT_AMOUNT_MISMATCH",
                "PAYMENT_ORDER_STATUS_MISMATCH",
                "REFUND_TOTAL_EXCEEDS_PAYMENT",
                "WEBHOOK_UNPROCESSED",
                name="reconciliation_finding_type_enum",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "severity",
            sa.Enum(
                "CRITICAL",
                "HIGH",
                "MEDIUM",
                "LOW",
                name="reconciliation_finding_severity_enum",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "OPEN",
                "RESOLVED",
                "DISMISSED",
                name="reconciliation_finding_status_enum",
                native_enum=False,
            ),
            nullable=False,
            server_default="OPEN",
        ),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("entity_id", sa.String(length=255), nullable=False),
        sa.Column("expected_amount", sa.BigInteger(), nullable=True),
        sa.Column("actual_amount", sa.BigInteger(), nullable=True),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("first_detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("occurrence_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", sa.UUID(), nullable=True),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reconciliation_findings")),
        sa.UniqueConstraint("dedupe_key", name="uq_reconciliation_findings_dedupe_key"),
    )
    op.create_index(
        "ix_reconciliation_findings_status",
        "reconciliation_findings",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_reconciliation_findings_finding_type",
        "reconciliation_findings",
        ["finding_type"],
        unique=False,
    )
    op.create_index(
        "ix_reconciliation_findings_severity",
        "reconciliation_findings",
        ["severity"],
        unique=False,
    )
    op.create_index(
        "ix_reconciliation_findings_last_detected_at",
        "reconciliation_findings",
        ["last_detected_at"],
        unique=False,
    )
    op.create_index(
        "ix_reconciliation_findings_entity",
        "reconciliation_findings",
        ["entity_type", "entity_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_reconciliation_findings_entity", table_name="reconciliation_findings"
    )
    op.drop_index(
        "ix_reconciliation_findings_last_detected_at", table_name="reconciliation_findings"
    )
    op.drop_index(
        "ix_reconciliation_findings_severity", table_name="reconciliation_findings"
    )
    op.drop_index(
        "ix_reconciliation_findings_finding_type", table_name="reconciliation_findings"
    )
    op.drop_index(
        "ix_reconciliation_findings_status", table_name="reconciliation_findings"
    )
    op.drop_table("reconciliation_findings")
