"""Approval workflow API routes."""

from __future__ import annotations

import uuid
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.security.dependencies import (
    get_current_active_user,
    get_current_user_id,
)
from app.modules.approvals.application.approval_service import (
    create_request,
    get_request,
    list_requests,
    review_request,
)
from app.modules.approvals.domain.models import ApprovalLevel, ApprovalStatus
from app.modules.approvals.schemas.approval import (
    ApprovalActionCreate,
    ApprovalRequestCreate,
    ApprovalRequestListResponse,
    ApprovalRequestResponse,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger()

router = APIRouter()


@router.get(
    "",
    response_model=ApprovalRequestListResponse,
    summary="List approval requests",
    description="List all or filtered approval requests for admins and managers.",
)
@router.get(
    "/",
    response_model=ApprovalRequestListResponse,
    include_in_schema=False,
)
async def get_approvals(
    status: ApprovalStatus | None = Query(None, description="Filter by approval status"),
    level: ApprovalLevel | None = Query(None, description="Filter by risk level"),
    resource: str | None = Query(None, description="Filter by resource type"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
    db: AsyncSession = Depends(get_db),
    _user: dict[str, Any] = Depends(get_current_active_user),
) -> ApprovalRequestListResponse:
    """Retrieve a paginated list of approval requests."""
    items, total = await list_requests(
        db=db,
        status=status,
        level=level,
        resource=resource,
        page=page,
        page_size=page_size,
    )
    return ApprovalRequestListResponse.create(
        items=[ApprovalRequestResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{id}",
    response_model=ApprovalRequestResponse,
    summary="Get approval request details",
    description="Retrieve details of a specific approval request with action history and requester info.",  # noqa: E501
)
async def get_approval_detail(
    id: uuid.UUID,  # noqa: A002  # API parameter name is the public contract
    db: AsyncSession = Depends(get_db),
    _user: dict[str, Any] = Depends(get_current_active_user),
) -> ApprovalRequestResponse:
    """Get approval request details by ID."""
    request = await get_request(db=db, request_id=id)
    if not request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Approval request {id} not found",
        )
    return ApprovalRequestResponse.model_validate(request)


@router.post(
    "",
    response_model=ApprovalRequestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit approval request",
    description="Submit a new request that requires human approval before execution.",
)
@router.post(
    "/",
    response_model=ApprovalRequestResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
async def submit_approval(
    body: ApprovalRequestCreate,
    db: AsyncSession = Depends(get_db),
    requester_id: uuid.UUID = Depends(get_current_user_id),
) -> ApprovalRequestResponse:
    """Submit a new approval request."""
    request = await create_request(
        db=db,
        requester_id=requester_id,
        type=body.type,
        resource=body.resource,
        resource_id=body.resource_id,
        level=body.level,
        data=body.data,
        reason=body.reason,
    )
    return ApprovalRequestResponse.model_validate(request)


@router.post(
    "/{id}/action",
    response_model=ApprovalRequestResponse,
    summary="Review approval request",
    description="Approve or reject an approval request with an optional comment.",
)
async def process_approval_action(
    id: uuid.UUID,  # noqa: A002  # API parameter name is the public contract
    body: ApprovalActionCreate,
    db: AsyncSession = Depends(get_db),
    actor_id: uuid.UUID = Depends(get_current_user_id),
) -> ApprovalRequestResponse:
    """Execute approval or rejection on an approval request."""
    request = await review_request(
        db=db,
        request_id=id,
        actor_id=actor_id,
        action=body.action,
        comment=body.comment,
    )
    return ApprovalRequestResponse.model_validate(request)
