"""Audit log Pydantic v2 schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class AuditLogResponse(BaseModel):
    """Single audit-log entry returned to admin callers."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    actor_id: uuid.UUID | None = None
    #: Human-readable actor identity, resolved by the route (not a column).
    #: The raw ``actor_id`` alone made every row read "کاربر عامل: <uuid>";
    #: the reviewer's actual question is "who is this person?".
    actor_name: str | None = None
    actor_phone: str | None = None
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


# ── Field-level change log schemas (ERP feature #9) ───────────────────────


class FieldChange(BaseModel):
    """One field's before/after pair inside a change-log row."""

    field: str
    old_value: Any = None
    new_value: Any = None


class EntityChangeResponse(BaseModel):
    """Single field-level change row."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    entity_type: str
    entity_id: str
    operation: str
    changed_fields: list[dict[str, Any]]
    actor_id: uuid.UUID | None = None
    #: Human-readable actor identity, resolved by the route (not a column).
    actor_name: str | None = None
    actor_phone: str | None = None
    actor_type: str
    request_id: str | None = None
    source: str
    occurred_at: datetime
    truncated: bool = False
    created_at: datetime


class EntityChangeListResponse(BaseModel):
    """Paginated change-log list."""

    items: list[EntityChangeResponse]
    total: int
    page: int
    page_size: int
    pages: int


class EntityHistoryResponse(BaseModel):
    """Per-record change timeline."""

    entity_type: str
    entity_id: str
    items: list[EntityChangeResponse]


class TrackedEntitySummary(BaseModel):
    """An entity type that has captured changes, with counts."""

    entity_type: str
    row_count: int
    last_change_at: datetime | None = None
