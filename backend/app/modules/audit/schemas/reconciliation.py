"""Pydantic v2 schemas for durable reconciliation findings."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ReconciliationFindingResponse(BaseModel):
    """One operator-facing reconciliation finding."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    dedupe_key: str
    finding_type: str
    severity: str
    status: str
    entity_type: str
    entity_id: str
    expected_amount: int | None = None
    actual_amount: int | None = None
    details: dict[str, Any]
    first_detected_at: datetime
    last_detected_at: datetime
    occurrence_count: int
    resolved_at: datetime | None = None
    resolved_by: uuid.UUID | None = None
    resolution_notes: str | None = None
    created_at: datetime


class ReconciliationFindingListResponse(BaseModel):
    """Paginated finding list."""

    items: list[ReconciliationFindingResponse]
    total: int
    page: int
    page_size: int
    pages: int


class ReconciliationSummaryResponse(BaseModel):
    """Aggregate finding counts for the admin dashboard."""

    total: int
    open: int
    by_status: dict[str, int]
    by_severity: dict[str, int]
    by_type: dict[str, int]
    last_detected_at: datetime | None = None


class ReconciliationRunResponse(BaseModel):
    """Outcome of an operator-triggered scanner pass."""

    detected: int
    created: int
    updated: int
    truncated: bool
    scanned_at: datetime


class LifecycleAuditRunResponse(BaseModel):
    """Outcome of an operator-triggered order lifecycle audit."""

    detected: int
    created: int
    updated: int
    truncated: bool
    audited_at: datetime


class FindingResolveRequest(BaseModel):
    """Operator resolution/dismissal note. Notes are mandatory and non-empty.

    The field validator strips the note and rejects anything shorter than 3
    characters afterwards, so a whitespace-only note cannot be recorded as a
    resolution — ``min_length`` alone would accept ``"   "``.
    """

    resolution_notes: str = Field(..., min_length=3, max_length=2000)

    @field_validator("resolution_notes")
    @classmethod
    def _require_meaningful_notes(cls, value: str) -> str:
        notes = value.strip()
        if len(notes) < 3:
            raise ValueError(
                "resolution_notes must contain at least 3 non-whitespace characters"
            )
        return notes
