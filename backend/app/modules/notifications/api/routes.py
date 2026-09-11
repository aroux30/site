"""Notifications API routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.security.dependencies import get_current_user_id
from app.modules.notifications.application.notification_service import (
    NotificationService,
)
from app.modules.notifications.schemas.notification import (
    MarkReadResponse,
    NotificationListResponse,
    NotificationResponse,
)

router = APIRouter()


@router.get(
    "",
    response_model=NotificationListResponse,
    summary="List notifications",
)
async def list_notifications(
    is_read: bool | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> NotificationListResponse:
    """Return paginated notifications for the authenticated user."""
    items, total, unread_count = await NotificationService.get_notifications(
        db, user_id, is_read=is_read, skip=skip, limit=limit
    )
    return NotificationListResponse(
        items=[NotificationResponse.model_validate(n) for n in items],
        total=total,
        unread_count=unread_count,
    )


@router.post(
    "/{notification_id}/read",
    response_model=MarkReadResponse,
    summary="Mark notification as read",
)
async def mark_as_read(
    notification_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> MarkReadResponse:
    """Mark a single notification as read."""
    success = await NotificationService.mark_as_read(db, user_id, notification_id)
    return MarkReadResponse(marked_count=1 if success else 0)


@router.post(
    "/read-all",
    response_model=MarkReadResponse,
    summary="Mark all notifications as read",
)
async def mark_all_read(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> MarkReadResponse:
    """Mark all unread notifications as read for the authenticated user."""
    count = await NotificationService.mark_all_read(db, user_id)
    return MarkReadResponse(marked_count=count)
