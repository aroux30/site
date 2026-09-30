"""Support API routes."""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.security.dependencies import (
    RequirePermissions,
    get_current_user_id,
)
from app.core.security.rate_limiter import limiter
from app.modules.support.application.support_service import SupportService
from app.modules.support.domain.models import TicketStatus
from app.modules.support.schemas.support import (
    ContactMessageCreate,
    ContactMessageResponse,
    TicketCreate,
    TicketDetailResponse,
    TicketListResponse,
    TicketMessageCreate,
    TicketMessageResponse,
    TicketResponse,
    TicketUpdateRequest,
)

router = APIRouter()

logger = structlog.get_logger(__name__)


# ── Public Contact Form ───────────────────────────────────────────────────


@router.post(
    "/contact",
    response_model=ContactMessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a message via the public contact form",
)
@limiter.limit("5/minute")
async def submit_contact_message(
    request: Request,
    body: ContactMessageCreate,
    db: AsyncSession = Depends(get_db),
) -> ContactMessageResponse:
    """Persist a public contact-form submission.

    Unauthenticated by design — the contact page is reachable without an
    account. Rate-limited to blunt abuse and stored for admin review.
    """
    contact = await SupportService.create_contact_message(
        db,
        name=body.name,
        email=body.email,
        subject=body.subject,
        message=body.message,
    )
    await db.commit()
    return ContactMessageResponse.model_validate(contact)


@router.get(
    "/tickets",
    response_model=TicketListResponse,
    summary="List support tickets",
)
async def list_tickets(
    ticket_status: TicketStatus | None = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> TicketListResponse:
    """Return paginated support tickets for the authenticated user."""
    items, total = await SupportService.list_tickets(
        db, user_id=user_id, status=ticket_status, skip=skip, limit=limit
    )
    return TicketListResponse(
        items=[TicketResponse.model_validate(t) for t in items],
        total=total,
    )


@router.post(
    "/tickets",
    response_model=TicketResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create support ticket",
)
async def create_ticket(
    payload: TicketCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> TicketResponse:
    """Create a new support ticket."""
    ticket = await SupportService.create_ticket(
        db,
        user_id=user_id,
        subject=payload.subject,
        body=payload.body,
        priority=payload.priority,
    )
    return TicketResponse.model_validate(ticket)


@router.get(
    "/tickets/{ticket_id}",
    response_model=TicketDetailResponse,
    summary="Get ticket detail",
)
async def get_ticket(
    ticket_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> TicketDetailResponse:
    """Get a support ticket with all its messages."""
    ticket = await SupportService.get_ticket(db, ticket_id)
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found.",
        )
    # Ensure the user owns this ticket (or is staff – simplified here)
    if ticket.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this ticket.",
        )
    return TicketDetailResponse.model_validate(ticket)


@router.post(
    "/tickets/{ticket_id}/messages",
    response_model=TicketMessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add message to ticket",
)
async def add_message(
    ticket_id: uuid.UUID,
    payload: TicketMessageCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> TicketMessageResponse:
    """Add a message to an existing support ticket."""
    # Check ticket ownership
    ticket = await SupportService.get_ticket(db, ticket_id)
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found.",
        )

    # Only the ticket owner can post customer messages. Staff replies go
    # through the staff/admin support surface, not this customer route.
    if ticket.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this ticket.",
        )

    try:
        message = await SupportService.add_message(
            db,
            ticket_id=ticket_id,
            sender_id=user_id,
            body=payload.body,
            is_staff=False,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return TicketMessageResponse.model_validate(message)


@router.post(
    "/tickets/{ticket_id}/close",
    response_model=TicketResponse,
    summary="Close ticket",
)
async def close_ticket(
    ticket_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> TicketResponse:
    """Close a support ticket."""
    ticket = await SupportService.get_ticket(db, ticket_id)
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found.",
        )
    if ticket.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this ticket.",
        )
    try:
        ticket = await SupportService.close_ticket(db, ticket_id, user_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return TicketResponse.model_validate(ticket)


@router.post(
    "/tickets/{ticket_id}/reopen",
    response_model=TicketResponse,
    summary="Reopen ticket",
)
async def reopen_ticket(
    ticket_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> TicketResponse:
    """Reopen a closed support ticket."""
    ticket = await SupportService.get_ticket(db, ticket_id)
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found.",
        )
    if ticket.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this ticket.",
        )
    try:
        ticket = await SupportService.reopen_ticket(db, ticket_id, user_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return TicketResponse.model_validate(ticket)


# ── Admin endpoints ──────────────────────────────────────────────────────────


@router.get(
    "/admin/tickets",
    response_model=TicketListResponse,
    summary="List all tickets (admin)",
    dependencies=[Depends(RequirePermissions("support:read"))],
)
async def admin_list_tickets(
    status_filter: TicketStatus | None = Query(None, alias="status"),
    user_id: uuid.UUID | None = Query(None, description="Filter by user ID"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> TicketListResponse:
    """Return paginated support tickets across all users for staff/operators."""
    items, total = await SupportService.list_tickets(
        db, user_id=user_id, status=status_filter, skip=skip, limit=limit
    )
    return TicketListResponse(
        items=[TicketResponse.model_validate(t) for t in items],
        total=total,
    )


@router.get(
    "/admin/tickets/{ticket_id}",
    response_model=TicketDetailResponse,
    summary="Get ticket conversation detail (admin)",
    dependencies=[Depends(RequirePermissions("support:read"))],
)
async def admin_get_ticket(
    ticket_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> TicketDetailResponse:
    """Get full ticket history and messages for staff review."""
    ticket = await SupportService.get_ticket(db, ticket_id)
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found.",
        )
    return TicketDetailResponse.model_validate(ticket)


@router.post(
    "/admin/tickets/{ticket_id}/reply",
    response_model=TicketMessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Reply to ticket as staff/admin",
    dependencies=[Depends(RequirePermissions("support:write"))],
)
async def admin_reply_ticket(
    ticket_id: uuid.UUID,
    payload: TicketMessageCreate,
    admin_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> TicketMessageResponse:
    """Add a staff reply to the ticket and notify customer via SMS."""
    ticket = await SupportService.get_ticket(db, ticket_id)
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found.",
        )

    try:
        message = await SupportService.add_message(
            db,
            ticket_id=ticket_id,
            sender_id=admin_id,
            body=payload.body,
            is_staff=True,
        )
        await db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    # Background or fire-and-forget notification dispatch
    try:
        from app.modules.messaging.application.sms_hub_service import (
            dispatch_ticket_reply_alert_sms,
        )
        from app.modules.users.domain.models import User

        user = await db.get(User, ticket.user_id)
        if user and user.phone:
            await dispatch_ticket_reply_alert_sms(
                mobile=user.phone,
                ticket_id=str(ticket.ticket_number),
                ticket_title=ticket.subject,
            )
    except Exception:
        logger.warning("support_reply_sms_alert_failed", ticket_id=str(ticket.id))

    return TicketMessageResponse.model_validate(message)


@router.patch(
    "/admin/tickets/{ticket_id}",
    response_model=TicketResponse,
    summary="Update ticket status or priority (admin)",
    dependencies=[Depends(RequirePermissions("support:write"))],
)
async def admin_update_ticket(
    ticket_id: uuid.UUID,
    payload: TicketUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> TicketResponse:
    """Update ticket properties such as status, priority, or assignment."""
    try:
        ticket = await SupportService.update_ticket(
            db,
            ticket_id=ticket_id,
            status=payload.status,
            priority=payload.priority,
            assigned_to=payload.assigned_to,
        )
        await db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return TicketResponse.model_validate(ticket)

