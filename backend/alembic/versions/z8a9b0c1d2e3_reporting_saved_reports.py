"""Reporting layer v1: saved report definitions and run history.

Revision ID: z8a9b0c1d2e3
Revises: y7z8a9b0c1d2
Create Date: 2026-09-24 23:59:30

Additive-only migration: two new tables (``saved_reports``, ``report_runs``)
with their indexes. No existing table, column, or dashboard metric is
touched. Money stays integer Rials — no money columns are added here at all
(report outputs are computed, not stored).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "z8a9b0c1d2e3"
down_revision = "y7z8a9b0c1d2"
branch_labels = None
depends_on = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "saved_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column(
            "report_type",
            sa.Enum(
                "SALES", "STOCK", "VENDOR_SETTLEMENT", "TAX_VAT",
                name="report_type_enum", native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "filters", postgresql.JSONB(astext_type=sa.Text()), nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("schedule_cron", sa.String(length=100), nullable=True),
        sa.Column(
            "delivery_channels", postgresql.JSONB(astext_type=sa.Text()), nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "recipients", postgresql.JSONB(astext_type=sa.Text()), nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_saved_reports_owner_id", "saved_reports", ["owner_id"])
    op.create_index("ix_saved_reports_report_type", "saved_reports", ["report_type"])
    op.create_index("ix_saved_reports_next_run_at", "saved_reports", ["next_run_at"])

    op.create_table(
        "report_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("saved_report_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING", "RUNNING", "SUCCEEDED", "FAILED", "COMPLETED_NO_DELIVERY",
                name="report_run_status_enum", native_enum=False,
            ),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("artifact_path", sa.String(length=500), nullable=True),
        sa.Column("html_path", sa.String(length=500), nullable=True),
        sa.Column("error_message", sa.String(length=2000), nullable=True),
        sa.Column("row_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("delivery_result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["saved_report_id"], ["saved_reports.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_report_runs_saved_report_id", "report_runs", ["saved_report_id"])
    op.create_index("ix_report_runs_status", "report_runs", ["status"])
    op.create_index("ix_report_runs_started_at", "report_runs", ["started_at"])


def downgrade() -> None:
    op.drop_index("ix_report_runs_started_at", table_name="report_runs")
    op.drop_index("ix_report_runs_status", table_name="report_runs")
    op.drop_index("ix_report_runs_saved_report_id", table_name="report_runs")
    op.drop_table("report_runs")
    op.drop_index("ix_saved_reports_next_run_at", table_name="saved_reports")
    op.drop_index("ix_saved_reports_report_type", table_name="saved_reports")
    op.drop_index("ix_saved_reports_owner_id", table_name="saved_reports")
    op.drop_table("saved_reports")
