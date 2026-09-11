"""Audit log Pydantic v2 schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AuditLogResponse(BaseModel):
    """Single audit-log entry returned to admin callers."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    actor_id: uuid.UUID | None = None
    action: str
    resource: str
    resource_id: uuid.UUID | None = None
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    request_id: str | None = None
    extra_data: dict[str, Any] | None = None
    created_at: datetime


class AuditLogListResponse(BaseModel):
    """Paginated list of audit logs."""

    items: list[AuditLogResponse]
    total: int
    page: int
    page_size: int
    pages: int


# ── Operational Exception Schemas ─────────────────────────────────────────


class OperationalExceptionResponse(BaseModel):
    """Actionable operational anomaly for Admin Exception Center."""

    id: uuid.UUID
    exception_type: str
    severity: str
    status: str
    entity_type: str
    entity_id: str
    details: dict[str, Any]
    created_at: datetime
    owner_id: uuid.UUID | None = None
    resolved_at: datetime | None = None
    resolution_notes: str | None = None


class ExceptionAssignRequest(BaseModel):
    owner_id: uuid.UUID


class ExceptionResolveRequest(BaseModel):
    resolution_notes: str = Field(..., min_length=3, max_length=2000)
