"""Approval workflow API routes."""

from __future__ import annotations

import uuid
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.security.dependencies import (
    RequirePermissions,
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
    ApprovalPolicyCreate,
    ApprovalPolicyResponse,
    ApprovalRequestCreate,
    ApprovalRequestListResponse,
    ApprovalRequestResponse,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger()

# Reviewing approvals executes privileged side effects (refunds, price changes,
# product publishing) — restricted to staff with the review permission, matching
# the RequirePermissions convention used by the other admin modules.
_require_review = Depends(RequirePermissions("approvals:review", "admin:access"))

router = APIRouter()


@router.get(
    "",
    response_model=ApprovalRequestListResponse,
    summary="List approval requests",
    description="List all or filtered approval requests for admins and managers.",
    dependencies=[_require_review],
)
@router.get(
    "/",
    response_model=ApprovalRequestListResponse,
    include_in_schema=False,
    dependencies=[_require_review],
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


# ══════════════════════════════════════════════════════════════════════════
# Approval policies — money-flow chains (ERP feature #23)
# ══════════════════════════════════════════════════════════════════════════
#
# Static paths are declared before the parameterized ones below so FastAPI
# never parses "policies" as a UUID.


@router.get(
    "/policies",
    response_model=list[ApprovalPolicyResponse],
    summary="List approval policies (admin)",
    dependencies=[_require_review],
)
async def list_approval_policies(
    db: AsyncSession = Depends(get_db),
    resource: str | None = Query(None, description="Filter by resource"),
    active_only: bool = Query(True, description="Only active policies"),
) -> list[ApprovalPolicyResponse]:
    """Return the policy table that decides how many signatures a flow needs."""
    from sqlalchemy import select as _select

    from app.modules.approvals.domain.models import ApprovalPolicy

    stmt = _select(ApprovalPolicy).order_by(
        ApprovalPolicy.resource, ApprovalPolicy.min_amount_rial
    )
    if resource:
        stmt = stmt.where(ApprovalPolicy.resource == resource)
    if active_only:
        stmt = stmt.where(ApprovalPolicy.is_active.is_(True))
    rows = (await db.execute(stmt)).scalars().all()
    return [ApprovalPolicyResponse.model_validate(r) for r in rows]


@router.post(
    "/policies",
    response_model=ApprovalPolicyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an approval policy (admin)",
    dependencies=[_require_review],
)
async def create_approval_policy(
    body: ApprovalPolicyCreate,
    db: AsyncSession = Depends(get_db),
) -> ApprovalPolicyResponse:
    """Create a policy. Steps are validated before insert — a malformed chain
    would deadlock a money flow, so it is rejected at the door."""
    from app.modules.approvals.application import policy_service
    from app.modules.approvals.domain.models import ApprovalPolicy

    try:
        normalised = policy_service.build_steps([s.model_dump() for s in body.steps])
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"زنجیره تایید نامعتبر است: {exc}",
        ) from exc

    policy = ApprovalPolicy(
        resource=body.resource,
        min_amount_rial=body.min_amount_rial,
        max_amount_rial=body.max_amount_rial,
        steps=normalised,
        priority=body.priority,
        is_active=body.is_active,
        description=body.description,
    )
    db.add(policy)
    await db.commit()
    await db.refresh(policy)
    return ApprovalPolicyResponse.model_validate(policy)


@router.patch(
    "/policies/{policy_id}",
    response_model=ApprovalPolicyResponse,
    summary="Update an approval policy (admin)",
    dependencies=[_require_review],
)
async def update_approval_policy(
    policy_id: uuid.UUID,
    body: ApprovalPolicyCreate,
    db: AsyncSession = Depends(get_db),
) -> ApprovalPolicyResponse:
    """Update a policy in place. Requests already in flight keep the chain
    they were created with — editing a policy never rewrites live chains."""
    from app.modules.approvals.application import policy_service
    from app.modules.approvals.domain.models import ApprovalPolicy

    policy = await db.get(ApprovalPolicy, policy_id)
    if policy is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="پالیسی یافت نشد")
    try:
        normalised = policy_service.build_steps([s.model_dump() for s in body.steps])
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"زنجیره تایید نامعتبر است: {exc}",
        ) from exc

    policy.resource = body.resource
    policy.min_amount_rial = body.min_amount_rial
    policy.max_amount_rial = body.max_amount_rial
    policy.steps = normalised
    policy.priority = body.priority
    policy.is_active = body.is_active
    policy.description = body.description
    await db.commit()
    await db.refresh(policy)
    return ApprovalPolicyResponse.model_validate(policy)


@router.delete(
    "/policies/{policy_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deactivate an approval policy (admin)",
    dependencies=[_require_review],
)
async def deactivate_approval_policy(
    policy_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Soft-delete: the row is deactivated, never removed. A deleted policy's
    history is the only record of why past chains demanded what they did."""
    from app.modules.approvals.domain.models import ApprovalPolicy

    policy = await db.get(ApprovalPolicy, policy_id)
    if policy is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="پالیسی یافت نشد")
    policy.is_active = False
    await db.commit()

@router.get(
    "/{id}",
    response_model=ApprovalRequestResponse,
    summary="Get approval request details",
    description="Retrieve details of a specific approval request with action history and requester info.",  # noqa: E501
    dependencies=[_require_review],
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
    dependencies=[_require_review],
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
