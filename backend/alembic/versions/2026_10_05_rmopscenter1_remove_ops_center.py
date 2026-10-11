"""Remove the Operations & Audit Center module (decision 2026-10-05).

The owner asked for «مرکز عملیات و حسابرسی» to be deleted outright — it has
no use in a retail storefront. The code is archived under
``_archived/ops-center-2026-10-05/``.

What the module was:

- **Exception Center** — an in-memory registry (``exception_center_service``)
  with zero writers in the whole codebase: ``record_exception`` had no caller,
  so the "خطاهای عملیاتی" tab could never show anything. Its three write
  endpoints (assign/resolve/dismiss) operated on records that never existed.
- **Reconciliation scanner** — the read-only payment/order sweep
  (``reconciliation_service``), its cross-axis order lifecycle auditor
  (``lifecycle_auditor``), the two Beat entries that ran them
  (``reconcile-payments`` every 30 min, ``audit-order-lifecycle`` every 2 h),
  and their admin endpoints.

Verified at removal time (live probe 2026-10-05):
- ``reconciliation_findings`` = 54 rows, all **derived** evidence rows the
  scanner rebuilds on its next pass (the creating migration itself documents
  them as "derived, not authoritative"). They reference payments/orders by
  text, never by foreign key — dropping the table breaks nothing.
- The exception registry had no rows anywhere: it was in-process and nothing
  ever wrote to it.

``downgrade()`` recreates ``reconciliation_findings`` exactly as
``b7d3e5f9a1c4`` defined it **including** the ``c8e1f4a7b2d6`` widening
(``finding_type`` VARCHAR(64)), so the removal is schema-reversible. The 54
finding rows are *not* restored — they were derived data, and the removed
scanner was the only thing that could ever write them.

Not touched on purpose: the audit log (``audit_logs``), the field-level change
log (``entity_change_log``), their endpoints, and the ``audit:read`` /
``audit:write`` permissions — the "گزارش رویدادها" admin page keeps working.

Revision ID: rmopscenter1
Revises: rmaccount1
Create Date: 2026-10-05
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "rmopscenter1"
down_revision = "rmaccount1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Children first: indexes, then the table. The findings are derived
    # evidence the scanner would rebuild; the scanner is gone, so they go.
    op.drop_index(
        "ix_reconciliation_findings_entity", table_name="reconciliation_findings"
    )
    op.drop_index(
        "ix_reconciliation_findings_last_detected_at",
        table_name="reconciliation_findings",
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


def downgrade() -> None:
    """Recreate the table as ``b7d3e5f9a1c4`` + ``c8e1f4a7b2d6`` defined it.

    The ``finding_type`` column carries the widened length (64), matching the
    schema the live database had at removal time.
    """
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
                length=64,
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
