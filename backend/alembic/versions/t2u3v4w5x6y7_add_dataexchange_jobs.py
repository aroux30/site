"""Add import/export job tables for the data-exchange framework.

Merges the two existing heads (s1t2u3v4w5x6 and d4e5f6a7b8c9) into one so the
tree has a single head again.

Revision ID: t2u3v4w5x6y7
Revises: s1t2u3v4w5x6, d4e5f6a7b8c9
Create Date: 2026-09-24 18:30:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "t2u3v4w5x6y7"
down_revision = ("s1t2u3v4w5x6", "d4e5f6a7b8c9")
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "import_jobs",
        sa.Column("entity_type", sa.String(length=60), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "DRAFT", "MAPPING", "VALIDATING", "READY", "IMPORTING", "COMPLETED", "FAILED",
                name="import_job_status_enum",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("original_filename", sa.String(length=500), nullable=False),
        sa.Column("stored_file_path", sa.String(length=1000), nullable=False),
        sa.Column("column_mapping", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("detected_headers", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("stats", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_report_path", sa.String(length=1000), nullable=True),
        sa.Column("idempotency_key", sa.String(length=120), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", name="uq_import_jobs_idempotency_key"),
    )
    op.create_index("ix_import_jobs_entity_type", "import_jobs", ["entity_type"], unique=False)
    op.create_index("ix_import_jobs_status", "import_jobs", ["status"], unique=False)
    op.create_index("ix_import_jobs_created_by", "import_jobs", ["created_by"], unique=False)
    op.create_index("ix_import_jobs_created_at", "import_jobs", ["created_at"], unique=False)

    op.create_table(
        "export_jobs",
        sa.Column("entity_type", sa.String(length=60), nullable=False),
        sa.Column(
            "status",
            sa.Enum("PENDING", "PROCESSING", "COMPLETED", "FAILED", name="export_job_status_enum", native_enum=False),
            nullable=False,
        ),
        sa.Column("filters", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("result_path", sa.String(length=1000), nullable=True),
        sa.Column("row_count", sa.Integer(), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_export_jobs_entity_type", "export_jobs", ["entity_type"], unique=False)
    op.create_index("ix_export_jobs_status", "export_jobs", ["status"], unique=False)
    op.create_index("ix_export_jobs_created_by", "export_jobs", ["created_by"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_export_jobs_created_by", table_name="export_jobs")
    op.drop_index("ix_export_jobs_status", table_name="export_jobs")
    op.drop_index("ix_export_jobs_entity_type", table_name="export_jobs")
    op.drop_table("export_jobs")
    op.drop_index("ix_import_jobs_created_at", table_name="import_jobs")
    op.drop_index("ix_import_jobs_created_by", table_name="import_jobs")
    op.drop_index("ix_import_jobs_status", table_name="import_jobs")
    op.drop_index("ix_import_jobs_entity_type", table_name="import_jobs")
    op.drop_table("import_jobs")
