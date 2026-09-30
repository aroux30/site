"""Pydantic schemas for the data-exchange admin API."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ColumnInfo(BaseModel):
    key: str
    label: str
    required: bool
    type: str
    aliases: list[str] = Field(default_factory=list)


class EntityInfo(BaseModel):
    entity_type: str
    label: str
    columns: list[ColumnInfo]


class ImportJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    entity_type: str
    status: str
    original_filename: str
    detected_headers: list[str] | None = None
    column_mapping: dict[str, Any] | None = None
    stats: dict[str, Any] | None = None
    has_error_report: bool = False
    created_by: uuid.UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @classmethod
    def from_job(cls, job: Any) -> "ImportJobResponse":
        return cls(
            id=job.id,
            entity_type=job.entity_type,
            status=job.status.value if hasattr(job.status, "value") else str(job.status),
            original_filename=job.original_filename,
            detected_headers=job.detected_headers,
            column_mapping=job.column_mapping,
            stats=job.stats,
            has_error_report=bool(job.error_report_path),
            created_by=job.created_by,
            created_at=job.created_at,
            updated_at=job.updated_at,
        )


class ImportJobListResponse(BaseModel):
    items: list[ImportJobResponse]
    total: int
    page: int
    page_size: int


class SetMappingRequest(BaseModel):
    mapping: dict[str, str] = Field(
        ..., description="source header -> column key (empty string = ignore column)"
    )


class SetMappingResponse(BaseModel):
    job: ImportJobResponse


class AutoMappingResponse(BaseModel):
    mapping: dict[str, str]


class ExecuteImportRequest(BaseModel):
    idempotency_key: str | None = Field(None, max_length=120)


class ExportJobCreateRequest(BaseModel):
    entity_type: str = Field(..., max_length=60)
    filters: dict[str, Any] = Field(default_factory=dict)


class ExportJobResponse(BaseModel):
    id: uuid.UUID
    entity_type: str
    status: str
    filters: dict[str, Any] | None = None
    row_count: int | None = None
    created_by: uuid.UUID | None = None
    created_at: datetime | None = None

    @classmethod
    def from_job(cls, job: Any) -> "ExportJobResponse":
        return cls(
            id=job.id,
            entity_type=job.entity_type,
            status=job.status.value if hasattr(job.status, "value") else str(job.status),
            filters=job.filters,
            row_count=job.row_count,
            created_by=job.created_by,
            created_at=job.created_at,
        )


class ExportJobListResponse(BaseModel):
    items: list[ExportJobResponse]
    total: int
    page: int
    page_size: int
