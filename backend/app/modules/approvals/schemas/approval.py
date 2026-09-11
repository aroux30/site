"""Approval workflow Pydantic v2 schemas."""

from __future__ import annotations

import math
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.modules.approvals.domain.models import (
    ApprovalActionType,
    ApprovalLevel,
    ApprovalStatus,
)

# ── Action Schemas ────────────────────────────────────────────────────────────


class ApprovalActionCreate(BaseModel):
    """Schema for submitting an approval or rejection action."""

    action: ApprovalActionType = Field(
        ...,
        description="Action to take: approve or reject",
    )
    comment: str | None = Field(
        None,
        max_length=2000,
        description="Optional comment or justification",
    )


class ApprovalActionResponse(BaseModel):
    """Schema for an approval action response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    request_id: uuid.UUID
    actor_id: uuid.UUID
    actor_name: str | None = None
    actor_email: str | None = None
    action: ApprovalActionType
    comment: str | None = None
    created_at: datetime


# ── Request Schemas ───────────────────────────────────────────────────────────


class ApprovalRequestCreate(BaseModel):
    """Schema for creating a new approval request."""

    type: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Type of approval request (e.g. price_change, big_refund, product_publish)",
    )
    resource: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Resource being modified (e.g. product_price, refund, product_publish)",
    )
    resource_id: uuid.UUID | None = Field(
        None,
        description="Identifier of the resource being modified",
    )
    level: ApprovalLevel = Field(
        default=ApprovalLevel.LOW,
        description="Risk level of the approval request (low, medium, high)",
    )
    data: dict[str, Any] | None = Field(
        None,
        description="JSON payload containing changes or parameters",
    )
    reason: str | None = Field(
        None,
        max_length=2000,
        description="Requester reason / justification",
    )


class ApprovalRequestResponse(BaseModel):
    """Schema for an approval request response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    requester_id: uuid.UUID
    requester_name: str | None = None
    requester_email: str | None = None
    requester_phone: str | None = None
    type: str
    resource: str
    resource_id: uuid.UUID | None = None
    level: ApprovalLevel
    status: ApprovalStatus
    data: dict[str, Any] | None = None
    reason: str | None = None
    actions: list[ApprovalActionResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class ApprovalRequestListResponse(BaseModel):
    """Paginated list of approval requests."""

    model_config = ConfigDict(from_attributes=True)

    items: list[ApprovalRequestResponse]
    total: int
    page: int
    page_size: int
    pages: int

    @classmethod
    def create(
        cls,
        items: list[ApprovalRequestResponse],
        total: int,
        page: int,
        page_size: int,
    ) -> ApprovalRequestListResponse:
        pages = math.ceil(total / page_size) if page_size > 0 else 0
        return cls(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            pages=pages,
        )


class ApprovalFilterParams(BaseModel):
    """Filter parameters for listing approval requests."""

    status: ApprovalStatus | None = Field(None, description="Filter by status")
    level: ApprovalLevel | None = Field(None, description="Filter by risk level")
    resource: str | None = Field(None, description="Filter by resource type")
    page: int = Field(1, ge=1, description="Page number")
    page_size: int = Field(20, ge=1, le=100, description="Items per page")
