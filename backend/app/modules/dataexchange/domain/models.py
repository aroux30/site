"""Data-exchange domain models: ImportJob and ExportJob."""

import enum
import uuid
from typing import Any

from sqlalchemy import Enum, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import BaseModel


class ImportJobStatus(str, enum.Enum):
    DRAFT = "draft"
    MAPPING = "mapping"
    VALIDATING = "validating"
    READY = "ready"
    IMPORTING = "importing"
    COMPLETED = "completed"
    FAILED = "failed"


class ExportJobStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ImportJob(BaseModel):
    """One admin-driven file import run (upload -> mapping -> validate -> execute)."""

    __tablename__ = "import_jobs"
    __table_args__ = (
        Index("ix_import_jobs_entity_type", "entity_type"),
        Index("ix_import_jobs_status", "status"),
        Index("ix_import_jobs_created_by", "created_by"),
        Index("ix_import_jobs_created_at", "created_at"),
    )

    entity_type: Mapped[str] = mapped_column(String(60), nullable=False)
    status: Mapped[ImportJobStatus] = mapped_column(
        Enum(ImportJobStatus, name="import_job_status_enum", native_enum=False),
        default=ImportJobStatus.DRAFT,
        nullable=False,
    )
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    # Server-side stored location of the uploaded file (never exposed raw to clients).
    stored_file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    # {source_header: adapter_column_key} — None until the mapping step.
    column_mapping: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    # Discovered column headers of the uploaded file (for the mapping UI).
    detected_headers: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    # {total, valid, invalid, imported, skipped} populated after validate/execute.
    stats: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    # Path to the generated row-level error CSV, if any.
    error_report_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    # Idempotency key for the execute step (unique per job).
    idempotency_key: Mapped[str | None] = mapped_column(String(120), nullable=True, unique=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    def __repr__(self) -> str:
        return f"<ImportJob(id={self.id}, entity={self.entity_type}, status={self.status})>"


class ExportJob(BaseModel):
    """One admin-driven export run (entity + filters -> downloadable CSV)."""

    __tablename__ = "export_jobs"
    __table_args__ = (
        Index("ix_export_jobs_entity_type", "entity_type"),
        Index("ix_export_jobs_status", "status"),
        Index("ix_export_jobs_created_by", "created_by"),
    )

    entity_type: Mapped[str] = mapped_column(String(60), nullable=False)
    status: Mapped[ExportJobStatus] = mapped_column(
        Enum(ExportJobStatus, name="export_job_status_enum", native_enum=False),
        default=ExportJobStatus.PENDING,
        nullable=False,
    )
    filters: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    result_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    row_count: Mapped[int | None] = mapped_column(nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    def __repr__(self) -> str:
        return f"<ExportJob(id={self.id}, entity={self.entity_type}, status={self.status})>"
