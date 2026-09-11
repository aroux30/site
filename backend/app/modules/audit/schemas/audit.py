"""Audit log Pydantic v2 schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class AuditLogResponse(BaseModel):
    """Single audit-log entry returned to admin callers."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    actor_id: Optional[uuid.UUID] = None
    action: str
    resource: str
    resource_id: Optional[uuid.UUID] = None
    before: Optional[dict[str, Any]] = None
    after: Optional[dict[str, Any]] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    request_id: Optional[str] = None
    extra_data: Optional[dict[str, Any]] = None
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
    owner_id: Optional[uuid.UUID] = None
    resolved_at: Optional[datetime] = None
    resolution_notes: Optional[str] = None


class ExceptionAssignRequest(BaseModel):
    owner_id: uuid.UUID


class ExceptionResolveRequest(BaseModel):
    resolution_notes: str = Field(..., min_length=3, max_length=2000)
