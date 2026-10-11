"""API routes for Time-bounded Notices and SMS Hub (Karta Phase 6/8)."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.security.dependencies import (
    RequirePermissions,
    get_current_user_id,
    get_current_user_optional,
)
from app.modules.messaging.application import sms_hub_service
from app.modules.notifications.application import notice_service
from app.modules.notifications.schemas.notices import (
    MarkNoticeSeenResponse,
    NoticeCreateRequest,
    NoticeResponse,
    SmsDispatchRequest,
    SmsDispatchResponse,
)

router = APIRouter(prefix="/notices", tags=["notifications-notices"])


# ── Customer Notice Endpoints ─────────────────────────────────────────────


@router.get(
    "/active",
    response_model=list[NoticeResponse],
    summary=(
        "Get active in-window notices, omitting popups already seen by user (Karta seen_notices)"
    ),
)
async def get_active_notices(
    target_page: str = Query(
        "all",
        description="Current page context: all, home, checkout, dashboard",
    ),
    payload: dict[str, Any] | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> list[NoticeResponse]:
    """Public notices for the current visitor.

    Anonymous by design: the storefront banner (``NoticeBanner``) renders
    site-wide announcements for every visitor, and the service already models
    the guest case (``user_id=None`` returns the full active set, skipping
    only the per-user "seen" filter). The previous mandatory-auth guard made
    the endpoint 401 for every guest, so an announcement targeted at
    ``all``/``home``/``checkout`` was never visible to the audience it was
    written for — and each storefront page load logged a console error.

    Identity stays optional enrichment, not a gate: a valid token still
    filters out notices the user has already dismissed; a missing one returns
    the unfiltered active set. A *present-and-invalid* token still fails
    loudly (``_extract_optional_token``), so a forged credential cannot
    silently downgrade.
    """
    user_id: uuid.UUID | None = None
    if payload:
        try:
            user_id = uuid.UUID(payload["sub"])
        except (KeyError, ValueError):
            user_id = None
    notices = await notice_service.get_active_notices_for_user(
        db, user_id=user_id, target_page=target_page
    )
    return [NoticeResponse.model_validate(n) for n in notices]


@router.post(
    "/{notice_id}/seen",
    response_model=MarkNoticeSeenResponse,
    summary="Mark notice or popup as seen/dismissed by user",
)
async def mark_seen(
    notice_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> MarkNoticeSeenResponse:
    seen = await notice_service.mark_notice_as_seen(db, user_id=user_id, notice_id=notice_id)
    return MarkNoticeSeenResponse(
        user_id=seen.user_id,
        notice_id=seen.notice_id,
        seen_at=seen.seen_at,
    )


# ── Admin Notice Endpoints ────────────────────────────────────────────────


@router.post(
    "/admin",
    response_model=NoticeResponse,
    summary="Create a scheduled system notice or banner (admin)",
    dependencies=[Depends(RequirePermissions("notifications:write"))],
)
async def create_notice(
    body: NoticeCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> NoticeResponse:
    notice = await notice_service.create_notice(
        db,
        title=body.title,
        content_html=body.content_html,
        notice_type=body.notice_type,
        target_page=body.target_page,
        start_at=body.start_at,
        end_at=body.end_at,
    )
    return NoticeResponse.model_validate(notice)


@router.get(
    "/admin/all",
    response_model=list[NoticeResponse],
    summary="List all scheduled system notices (admin)",
    dependencies=[Depends(RequirePermissions("notifications:read"))],
)
async def list_all_notices(
    db: AsyncSession = Depends(get_db),
) -> list[NoticeResponse]:
    notices = await notice_service.list_all_notices(db)
    return [NoticeResponse.model_validate(n) for n in notices]


# ── Multi-Provider SMS Dispatch ───────────────────────────────────────────


@router.post(
    "/sms/dispatch",
    response_model=SmsDispatchResponse,
    summary="Dispatch SMS with automatic multi-provider failover (admin)",
    dependencies=[Depends(RequirePermissions("notifications:write"))],
)
async def dispatch_sms(
    body: SmsDispatchRequest,
) -> SmsDispatchResponse:
    res = await sms_hub_service.send_sms_with_failover(
        mobile=body.mobile,
        text=body.text,
        pattern=body.pattern,
    )
    return SmsDispatchResponse(
        success=res.get("success", False),
        provider=res.get("provider"),
        to=res.get("to"),
        error=res.get("error"),
    )
