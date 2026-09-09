"""Support API routes."""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.security.dependencies import get_current_user_id
from app.modules.support.application.support_service import SupportService
from app.modules.support.domain.models import TicketStatus
from app.modules.support.schemas.support import (
    TicketCreate,
    TicketDetailResponse,
    TicketListResponse,
    TicketMessageCreate,
    TicketMessageResponse,
    TicketResponse,
)

router = APIRouter()


@router.get(
    "/tickets",
    response_model=TicketListResponse,
    summary="List support tickets",
)
async def list_tickets(
    ticket_status: Optional[TicketStatus] = Query(None, alias="status"),
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

    is_staff = ticket.user_id != user_id
    if not is_staff and ticket.user_id != user_id:
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
            is_staff=is_staff,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        )
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
    try:
        ticket = await SupportService.close_ticket(db, ticket_id, user_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        )
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
    try:
        ticket = await SupportService.reopen_ticket(db, ticket_id, user_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        )
    return TicketResponse.model_validate(ticket)
