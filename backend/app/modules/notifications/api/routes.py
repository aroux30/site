"""Notifications API routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.security.dependencies import RequirePermissions, get_current_user_id
from app.modules.notifications.api.notice_routes import router as notice_router
from app.modules.notifications.application import (
    preferences_service,
    push_service,
    telegram_service,
)
from app.modules.notifications.application.notification_service import (
    NotificationService,
)
from app.modules.notifications.schemas.notification import (
    MarkReadResponse,
    NotificationListResponse,
    NotificationPreferencesResponse,
    NotificationPreferencesUpdate,
    NotificationResponse,
    PushPublicKeyResponse,
    PushSubscribeRequest,
    PushSubscriptionResponse,
    PushUnsubscribeRequest,
    TelegramAdminLinkRequest,
    TelegramAdminLinkResponse,
    TelegramLinkCodeResponse,
    TelegramLinkStatusResponse,
)

router = APIRouter()


def _mask_chat_id(chat_id: str | None) -> str | None:
    """Display-safe chat_id: keep the last 3 digits only."""
    if not chat_id:
        return None
    tail = chat_id[-3:]
    return f"•••{tail}"


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


# ── Per-user Preferences ──────────────────────────────────────────────────


@router.get(
    "/preferences",
    response_model=NotificationPreferencesResponse,
    summary="Get notification preferences",
)
async def get_preferences(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> NotificationPreferencesResponse:
    """Return the resolved channel/category opt-in matrix (default: all on).

    The row is created lazily on first access so the account page always has
    a concrete matrix to render.
    """
    pref = await preferences_service.get_or_create_preferences(db, user_id)
    await db.commit()
    return NotificationPreferencesResponse(
        channels=preferences_service.effective_channel_matrix(pref),
        categories=preferences_service.effective_category_matrix(pref),
        telegram_linked=bool(pref.telegram_chat_id),
        telegram_chat_id_masked=_mask_chat_id(pref.telegram_chat_id),
    )


@router.put(
    "/preferences",
    response_model=NotificationPreferencesResponse,
    summary="Update notification preferences",
)
async def put_preferences(
    payload: NotificationPreferencesUpdate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> NotificationPreferencesResponse:
    """Merge channel/category opt-in updates (unknown keys are dropped)."""
    pref = await preferences_service.update_preferences(
        db, user_id, channels=payload.channels, categories=payload.categories
    )
    await db.commit()
    return NotificationPreferencesResponse(
        channels=preferences_service.effective_channel_matrix(pref),
        categories=preferences_service.effective_category_matrix(pref),
        telegram_linked=bool(pref.telegram_chat_id),
        telegram_chat_id_masked=_mask_chat_id(pref.telegram_chat_id),
    )


# ── Telegram Account Linking ──────────────────────────────────────────────


@router.post(
    "/telegram/link-code",
    response_model=TelegramLinkCodeResponse,
    summary="Generate a Telegram account link code",
)
async def create_telegram_link_code(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> TelegramLinkCodeResponse:
    """Create a single-use link code (10-minute TTL) for the Telegram bot flow.

    The user sends this code to the bot; the deferred webhook (or, in v1, an
    admin via the manual-link endpoint) binds the sender's chat_id through
    ``telegram_service.confirm_telegram_link``.
    """
    code, expires_at = await telegram_service.generate_link_code(db, user_id)
    await db.commit()
    config = telegram_service.get_telegram_config()
    deep_link = (
        f"https://t.me/{config.bot_username.lstrip('@')}" if config.bot_username.strip() else None
    )
    return TelegramLinkCodeResponse(code=code, expires_at=expires_at, bot_deep_link=deep_link)


@router.get(
    "/telegram/link-status",
    response_model=TelegramLinkStatusResponse,
    summary="Get Telegram link status",
)
async def get_telegram_link_status(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> TelegramLinkStatusResponse:
    """Whether the authenticated user has a linked Telegram chat."""
    from sqlalchemy import select

    from app.modules.notifications.domain.models import NotificationPreference

    pref = (
        await db.execute(
            select(NotificationPreference).where(NotificationPreference.user_id == user_id)
        )
    ).scalar_one_or_none()
    chat_id = pref.telegram_chat_id if pref else None
    return TelegramLinkStatusResponse(
        linked=bool(chat_id), telegram_chat_id_masked=_mask_chat_id(chat_id)
    )


@router.delete(
    "/telegram/link",
    response_model=TelegramLinkStatusResponse,
    summary="Unlink Telegram account",
)
async def delete_telegram_link(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> TelegramLinkStatusResponse:
    """Clear the stored chat_id so no further Telegram sends are attempted."""
    await telegram_service.unlink_telegram(db, user_id)
    await db.commit()
    return TelegramLinkStatusResponse(linked=False, telegram_chat_id_masked=None)


@router.post(
    "/admin/telegram/link",
    response_model=TelegramAdminLinkResponse,
    summary="Manually link a Telegram chat_id via a user's code (admin)",
    dependencies=[Depends(RequirePermissions("settings:write"))],
)
async def admin_telegram_link(
    payload: TelegramAdminLinkRequest,
    db: AsyncSession = Depends(get_db),
) -> TelegramAdminLinkResponse:
    """Bind a chat_id to the user holding ``code`` (interim for the bot webhook).

    v1 flow: the user generates a code in their account page and sends it to
    the bot; an operator reads the code + sender chat_id from the bot inbox
    and binds them here. The future webhook endpoint calls the same
    ``confirm_telegram_link`` service function — no service changes needed.
    """
    linked, linked_user_id = await telegram_service.confirm_telegram_link(
        db, code=payload.code, chat_id=payload.chat_id
    )
    await db.commit()
    return TelegramAdminLinkResponse(linked=linked, user_id=linked_user_id)


# ── Web Push Subscriptions ────────────────────────────────────────────────


@router.get(
    "/push/public-key",
    response_model=PushPublicKeyResponse,
    summary="Get the VAPID public key for browser push subscription",
)
async def get_push_public_key() -> PushPublicKeyResponse:
    """Return the VAPID public key the browser needs to subscribe.

    Empty (with ``configured=false``) until VAPID keys are set — and note the
    deferred ``pywebpush`` dependency gap documented in push_service.py.
    """
    config = push_service.get_push_config()
    return PushPublicKeyResponse(
        public_key=config.vapid_public_key if config.has_keys else "",
        configured=config.is_configured,
    )


@router.post(
    "/push/subscribe",
    response_model=PushSubscriptionResponse,
    summary="Register a browser push subscription",
)
async def push_subscribe(
    payload: PushSubscribeRequest,
    request: Request,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> PushSubscriptionResponse:
    """Store (or refresh) the browser's push subscription for this user."""
    user_agent = request.headers.get("user-agent")
    await push_service.save_subscription(
        db,
        user_id=user_id,
        endpoint=payload.endpoint,
        keys=payload.keys.model_dump(),
        user_agent=user_agent[:500] if user_agent else None,
    )
    await db.commit()
    return PushSubscriptionResponse(success=True)


@router.post(
    "/push/unsubscribe",
    response_model=PushSubscriptionResponse,
    summary="Remove a browser push subscription",
)
async def push_unsubscribe(
    payload: PushUnsubscribeRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> PushSubscriptionResponse:
    """Delete the subscription for the given endpoint (owned by this user)."""
    await push_service.delete_subscription(db, user_id=user_id, endpoint=payload.endpoint)
    await db.commit()
    return PushSubscriptionResponse(success=True)


# NOTE: this parameterized route is declared AFTER every static /preferences,
# /telegram/* and /push/* route. FastAPI matches in declaration order and
# "telegram"/"preferences" would otherwise hit this path shape first and fail
# UUID parsing with a 422 instead of reaching the static route.
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


# ── Time-bounded Notices & SMS sub-router (Karta Phase 6/8) ────────────────
router.include_router(notice_router)
