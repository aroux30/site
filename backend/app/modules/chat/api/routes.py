"""Chat API routes.

Two surfaces, mirroring the WordPress plugin's split:

* ``router`` (mounted ``/api/v1/chat``) — the **public widget**. A guest must be
  able to read its config, start a session, send/poll messages and heartbeat
  without logging in. Every route is rate-limited; identity is optional via
  ``get_current_user_optional``.
* ``admin_router`` (mounted ``/api/v1/admin/chat``) — the **staff console**,
  behind ``chat:read`` / ``chat:write``.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from fastapi import APIRouter, Depends, File, Request, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.security.dependencies import (
    RequirePermissions,
    get_current_user_id,
    get_current_user_optional,
)
from app.core.security.rate_limiter import get_real_client_ip, limiter
from app.modules.chat.application import chat_config
from app.modules.chat.application.chat_service import ChatService
from app.modules.chat.application.n8n_client import N8nClient
from app.modules.chat.domain.models import ChatRole
from app.modules.chat.schemas.chat import (
    ChatAdminMessageCreate,
    ChatConfigResponse,
    ChatConfigUpdateRequest,
    ChatConversationRow,
    ChatFlowCompleteRequest,
    ChatFlowCompleteResponse,
    ChatHandoffRequest,
    ChatHandoffResponse,
    ChatHandoffToggleRequest,
    ChatHeartbeatRequest,
    ChatHistoryResponse,
    ChatIdResponse,
    ChatMessageCreate,
    ChatMessageCreatedResponse,
    ChatMessageResponse,
    ChatOnlineUser,
    ChatOnlineUsersResponse,
    ChatPollRequest,
    ChatPollResponse,
    ChatPublicConfig,
    ChatReadRequest,
    ChatSessionInfoField,
    ChatSessionInfoResponse,
    ChatSessionResponse,
    ChatSessionStartRequest,
    ChatUnreadCountsRequest,
    ChatValidateSessionsRequest,
)

router = APIRouter()
admin_router = APIRouter(prefix="/admin/chat", tags=["admin-chat"])

# The SSE stream lives in its own module (it needs StreamingResponse + a
# generator) but is mounted on the same public router so it shares the /chat
# prefix and the loader's single `router` export.
from app.modules.chat.api.stream import router as _stream_router  # noqa: E402

router.include_router(_stream_router)

# WP-plugin bridge — serves the plugin's verbatim frontend JS (owner directive:
# copy the plugin UI, don't rebuild it in React).
from app.modules.chat.api.bridge import router as _bridge_router  # noqa: E402

router.include_router(_bridge_router)

logger = structlog.get_logger(__name__)

_require_chat_read = Depends(RequirePermissions("chat:read"))
_require_chat_write = Depends(RequirePermissions("chat:write"))

#: Guest attachment ceiling (mirrors the media module's customer cap).
_GUEST_UPLOAD_MAX_BYTES = 10 * 1024 * 1024


def _row(m: Any) -> ChatMessageResponse:
    return ChatMessageResponse(
        id=m.id,
        role=str(m.role),
        message=m.body,
        time=_time_of(m.created_at),
        is_read=bool(m.is_read),
        sender_name=m.sender_name or "",
    )


def _time_of(dt: datetime | None) -> str:
    if dt is None:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    local = dt.astimezone(UTC) + timedelta(hours=3, minutes=30)
    return local.strftime("%H:%M")


# ── Public widget ────────────────────────────────────────────────────────


@router.get(
    "/config",
    response_model=ChatPublicConfig,
    summary="Read the widget config (public)",
)
async def get_widget_config(db: AsyncSession = Depends(get_db)) -> ChatPublicConfig:
    """Browser-safe widget config: colors, fields, quick replies, no secrets."""
    config = await chat_config.get_config(db)
    config["enabled"] = config.get("enabled", True) and await chat_config.is_enabled(db)
    return chat_config.public_config(config)


@router.post(
    "/session",
    response_model=ChatSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start or update a chat session (public)",
)
@limiter.limit("30/minute")
async def start_session(
    request: Request,
    body: ChatSessionStartRequest,
    user: dict[str, Any] | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> ChatSessionResponse:
    """Create/refresh a session and persist the pre-chat form values."""
    user_id = uuid.UUID(user["sub"]) if user and user.get("sub") else None
    session = await ChatService.start_session(
        db,
        session_key=body.session_key,
        user_name=body.user_name,
        user_email=body.user_email,
        user_phone=body.user_phone,
        user_data=body.user_data,
        user_id=user_id,
    )
    # Send the automatic welcome message once, on first creation.
    if not await ChatService.list_all_messages(db, body.session_key):
        config = await chat_config.get_config(db)
        welcome = (config.get("welcome_message") or "").strip()
        if welcome:
            await ChatService.add_message(
                db, session_key=body.session_key, role=ChatRole.AI, body=welcome
            )
    await db.commit()
    return ChatSessionResponse(
        session_key=session.session_key,
        user_name=session.user_name,
        handoff_until=session.handoff_until,
    )


@router.post(
    "/message",
    response_model=ChatMessageCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Send a message (public) — proxied to n8n",
)
@limiter.limit("20/minute")
async def send_message(
    request: Request,
    body: ChatMessageCreate,
    db: AsyncSession = Depends(get_db),
) -> ChatMessageCreatedResponse:
    """Save the user's message, then (unless a human owns the thread) ask n8n."""
    message = await ChatService.add_message(
        db, session_key=body.session_key, role=ChatRole.USER, body=body.message
    )
    await db.commit()

    session = await ChatService.get_session_by_key(db, body.session_key)
    if session is not None:
        if ChatService.handoff_active(session):
            # A human owns the thread — forward the visitor's message to the
            # Telegram topic so the operator can actually see and answer it
            # (G1). The AI stays muted.
            from app.modules.chat.application.telegram_notify import (
                forward_user_message,
            )

            await forward_user_message(
                db, session_key=body.session_key, message=body.message
            )
        else:
            config = await chat_config.get_config(db)
            extra = {
                "userName": session.user_name,
                **(session.user_data or {}),
            }
            reply = await N8nClient().ask(
                webhook_url=config.get("webhook_url", ""),
                message=body.message,
                session_key=body.session_key,
                role="user",
                extra=extra,
            )
            if reply:
                await ChatService.add_message(
                    db, session_key=body.session_key, role=ChatRole.AI, body=reply
                )
                await db.commit()

    return ChatMessageCreatedResponse(id=message.id)


@router.post(
    "/flow-complete",
    response_model=ChatFlowCompleteResponse,
    summary="Complete a quick-reply flow (public) — saves each entry, then asks n8n",
)
@limiter.limit("20/minute")
async def flow_complete(
    request: Request,
    body: ChatFlowCompleteRequest,
    db: AsyncSession = Depends(get_db),
) -> ChatFlowCompleteResponse:
    """Save each flow entry as its own message, then send the transcript to n8n.

    Plugin parity (``n8n_chat_flow_complete``): the visitor's Q/A flow is stored
    as individual bubbles (so the history keeps its structure and survives a
    reload), NOT as one joined wall of text; the joined transcript is what goes
    to the AI. A short idempotency lock stops a double-submit storing twice.
    """
    # Idempotency: the SAME flow submitted twice within 5s stores once. The key
    # must digest the full CONTENT, not a length or Python's `hash()`:
    #   - `hash()` is salted per process (PYTHONHASHSEED), so two uvicorn
    #     workers compute different keys and the lock silently stops locking;
    #   - a length-only key collides for two DIFFERENT same-length flows, so the
    #     second flow returns empty and its messages are never stored (silent
    #     data loss). The plugin keyed on md5(sid . flow_context) — the content.
    import hashlib
    import json

    digest = hashlib.sha256(
        json.dumps(
            [body.final_msg, [e.model_dump() for e in body.flow_context]],
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    from app.modules.chat.application.chat_service import flow_lock_acquired

    if not await flow_lock_acquired(body.session_key, digest):
        return ChatFlowCompleteResponse(last_id=0, saved_ids=[])

    saved_ids: list[int] = []
    last_id = 0
    for entry in body.flow_context:
        role = entry.role if entry.role in ("user", "ai", "admin") else "ai"
        text = entry.message.strip()
        if not text:
            continue
        msg = await ChatService.add_message(
            db,
            session_key=body.session_key,
            role=ChatRole(role),
            body=text,
            sender_name=entry.sender_name,
        )
        saved_ids.append(msg.id)
        if role == "user":
            last_id = msg.id
    if body.final_msg.strip():
        msg = await ChatService.add_message(
            db, session_key=body.session_key, role=ChatRole.USER, body=body.final_msg.strip()
        )
        saved_ids.append(msg.id)
        last_id = msg.id
    await db.commit()

    # Build the transcript for the AI (plugin parity: labelled lines).
    lines = [
        f"{'👤 کاربر' if e.role == 'user' else '🤖 بات'}: {e.message}"
        for e in body.flow_context
        if e.message.strip()
    ]
    if body.final_msg.strip():
        lines.append(f"👤 کاربر: {body.final_msg.strip()}")
    transcript = "\n".join(lines)

    session = await ChatService.get_session_by_key(db, body.session_key)
    if session is not None and not ChatService.handoff_active(session) and transcript:
        config = await chat_config.get_config(db)
        reply = await N8nClient().ask(
            webhook_url=config.get("webhook_url", ""),
            message=transcript,
            session_key=body.session_key,
            role="user",
            extra={"userName": session.user_name, **(session.user_data or {})},
        )
        if reply:
            await ChatService.add_message(
                db, session_key=body.session_key, role=ChatRole.AI, body=reply
            )
            await db.commit()

    return ChatFlowCompleteResponse(last_id=last_id, saved_ids=saved_ids)


@router.post(
    "/messages",
    response_model=ChatPollResponse,
    summary="Poll new messages since an id (public)",
)
@limiter.limit("120/minute")
async def poll_messages(
    request: Request,
    body: ChatPollRequest,
    db: AsyncSession = Depends(get_db),
) -> ChatPollResponse:
    """Return messages newer than ``last_id`` plus read-receipt updates."""
    await ChatService.mark_read(db, body.session_key, by_user=True)
    messages = await ChatService.list_messages_since(db, body.session_key, body.last_id)
    updates = await ChatService.read_updates(db, body.session_key)
    session = await ChatService.get_session_by_key(db, body.session_key)
    handoff_until = _epoch(session.handoff_until) if session else 0
    await db.commit()
    return ChatPollResponse(
        messages=[_row(m) for m in messages],
        updates=updates,
        handoff_until=handoff_until,
    )


@router.post(
    "/history",
    response_model=ChatHistoryResponse,
    summary="Full message history for a session (public)",
)
@limiter.limit("60/minute")
async def history(
    request: Request,
    body: ChatReadRequest,
    db: AsyncSession = Depends(get_db),
) -> ChatHistoryResponse:
    await ChatService.mark_read(db, body.session_key, by_user=True)
    messages = await ChatService.list_all_messages(db, body.session_key)
    session = await ChatService.get_session_by_key(db, body.session_key)
    handoff_until = _epoch(session.handoff_until) if session else 0
    await db.commit()
    return ChatHistoryResponse(
        messages=[_row(m) for m in messages], handoff_until=handoff_until
    )


@router.post(
    "/unread-counts",
    summary="Unread counts per session (public badge poller)",
)
@limiter.limit("120/minute")
async def unread_counts(
    request: Request,
    body: ChatUnreadCountsRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    counts = await ChatService.unread_counts_for(db, body.session_keys, for_admin=False)
    await db.commit()
    return counts


@router.post(
    "/validate-sessions",
    summary="Which session keys still exist (public client dedup)",
)
@limiter.limit("120/minute")
async def validate_sessions(
    request: Request,
    body: ChatValidateSessionsRequest,
    db: AsyncSession = Depends(get_db),
) -> list[str]:
    return await ChatService.valid_session_keys(db, body.session_keys)


@router.post(
    "/heartbeat",
    response_model=ChatIdResponse,
    summary="Presence heartbeat (public online monitor)",
)
@limiter.limit("120/minute")
async def heartbeat(
    request: Request,
    body: ChatHeartbeatRequest,
    user: dict[str, Any] | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> ChatIdResponse:
    """Record this tab's presence. Runs for every visitor, chat open or not.

    For a signed-in visitor the authenticated identity is the TRUSTED source
    (G8): the session's name is synced from it and a guest-only placeholder is
    upgraded — never the reverse, so a logged-in user's real name lands on the
    session and shows on the online card.
    """
    user_id = uuid.UUID(user["sub"]) if user and user.get("sub") else None
    session = await ChatService.get_session_by_key(db, body.session_key)
    name = ""
    if session is not None:
        name = session.user_name or ""
    if user_id is not None and session is not None:
        synced = await ChatService.sync_session_identity(db, session, user_id)
        if synced:
            name = synced
    await ChatService.heartbeat(
        db,
        session_key=body.session_key,
        tab_id=body.tab_id or "def",
        user_name=name,
        user_ip=get_real_client_ip(request),
        user_agent=(request.headers.get("user-agent") or "")[:500],
        page_url=body.page_url,
        page_title=body.page_title,
        user_id=user_id,
    )
    await db.commit()
    return ChatIdResponse(id=0)


@router.post(
    "/handoff",
    response_model=ChatHandoffResponse,
    summary="Visitor requests a human (public)",
)
@limiter.limit("5/minute")
async def request_handoff(
    request: Request,
    body: ChatHandoffRequest,
    db: AsyncSession = Depends(get_db),
) -> ChatHandoffResponse:
    """Mute the AI for N minutes and post a system notice in the thread."""
    config = await chat_config.get_config(db)
    duration = int(config.get("handoff_duration", 60) or 60)
    if duration < 1:
        duration = 60
    until = datetime.now(UTC) + timedelta(minutes=duration)
    await ChatService.set_handoff(db, body.session_key, until=until)
    # B1: plugin parity (php:1510) — a blank handoff_system_message falls back to
    # the default notice, so the visitor ALWAYS sees "support requested".
    sys_msg = chat_config.handoff_system_message(config)
    support_name = config.get("default_support_name") or "پشتیبان"
    await ChatService.add_message(
        db,
        session_key=body.session_key,
        # B2: plugin parity — handoff notice is role=admin (php:1513), so it
        # is unread to the visitor (badge/beep). SYSTEM is never read-marked.
        role=ChatRole.ADMIN,
        body=sys_msg,
        sender_name=f"{support_name}|سیستم",
    )
    await db.commit()
    # Push the conversation to the operator's Telegram group (best-effort).
    from app.modules.chat.application.telegram_notify import notify_handoff

    await notify_handoff(db, session_key=body.session_key)
    return ChatHandoffResponse(handoff_until=_epoch(until))


@router.post(
    "/upload",
    summary="Upload a chat attachment or voice note (public, rate-limited)",
)
@limiter.limit("10/minute")
async def upload_attachment(
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Guest file/voice upload, capped and MIME-sniffed by the media service."""
    from app.modules.media.application.media_service import MediaService

    asset = await MediaService.upload_file(
        db, file, uploader_id=None, folder="chat", max_bytes=_GUEST_UPLOAD_MAX_BYTES
    )
    await db.commit()
    return {"url": asset.file_url, "name": file.filename or ""}


@router.post(
    "/telegram/webhook",
    summary="Telegram bot webhook (operator replies + inline callbacks)",
)
@limiter.limit("120/minute")
async def telegram_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Receive Telegram updates.

    Secured by Telegram's ``X-Telegram-Bot-Api-Secret-Token`` header. This route
    is NOT public: with a known session key, an unauthenticated caller could
    delete a session or forge an admin reply. So the secret is mandatory —
    production refuses the request outright when it is unset, and a mismatch is
    rejected with a timing-safe compare (``compare_digest``, same as the metrics
    endpoint). Rate-limited because every call costs a config read + JSON parse.
    """
    import secrets

    from app.core.config.settings import get_settings
    from app.core.exceptions.handlers import ForbiddenError
    from app.modules.chat.application.telegram_ingest import handle_update

    config = await chat_config.get_config(db)
    expected = (config.get("telegram_webhook_secret") or "").strip()
    if not expected:
        # No secret configured: allow only outside production (local dev / a
        # bot registered without a secret). In production this endpoint must be
        # closed — "open by default" is the hole the metrics endpoint rejects.
        if get_settings().ENVIRONMENT == "production":
            raise ForbiddenError(detail="telegram webhook secret is not configured")
    else:
        presented = request.headers.get("x-telegram-bot-api-secret-token", "")
        # compare_digest: a plain == leaks the secret prefix through timing.
        if not secrets.compare_digest(presented, expected):
            raise ForbiddenError(detail="invalid webhook secret")

    try:
        update = await request.json()
    except (ValueError, UnicodeDecodeError):
        # A malformed body must not 500: Telegram can retry, and the ingest
        # contract is "never raises on bad input" (the docstring above).
        return {"status": "ignored"}
    if not isinstance(update, dict):
        return {"status": "ignored"}
    return await handle_update(db, update)


# ── Admin console ────────────────────────────────────────────────────────


@admin_router.get(
    "/conversations",
    response_model=list[ChatConversationRow],
    summary="List conversations (admin)",
    dependencies=[_require_chat_read],
)
async def admin_conversations(db: AsyncSession = Depends(get_db)) -> list[ChatConversationRow]:
    rows = await ChatService.list_conversations(db)
    return [ChatConversationRow.model_validate(r) for r in rows]


@admin_router.post(
    "/history",
    response_model=ChatHistoryResponse,
    summary="Conversation history (admin)",
    dependencies=[_require_chat_read],
)
async def admin_history(
    body: ChatReadRequest, db: AsyncSession = Depends(get_db)
) -> ChatHistoryResponse:
    await ChatService.mark_read(db, body.session_key, by_user=False)
    messages = await ChatService.list_all_messages(db, body.session_key)
    session = await ChatService.get_session_by_key(db, body.session_key)
    handoff_until = _epoch(session.handoff_until) if session else 0
    await db.commit()
    return ChatHistoryResponse(
        messages=[_row(m) for m in messages], handoff_until=handoff_until
    )


@admin_router.post(
    "/poll",
    response_model=ChatPollResponse,
    summary="Poll a conversation (admin)",
    dependencies=[_require_chat_read],
)
async def admin_poll(
    body: ChatPollRequest, db: AsyncSession = Depends(get_db)
) -> ChatPollResponse:
    await ChatService.mark_read(db, body.session_key, by_user=False)
    messages = await ChatService.list_messages_since(db, body.session_key, body.last_id)
    updates = await ChatService.read_updates(db, body.session_key)
    session = await ChatService.get_session_by_key(db, body.session_key)
    handoff_until = _epoch(session.handoff_until) if session else 0
    await db.commit()
    return ChatPollResponse(
        messages=[_row(m) for m in messages], updates=updates, handoff_until=handoff_until
    )


@admin_router.post(
    "/send",
    response_model=ChatMessageCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Reply to a conversation (admin)",
    dependencies=[_require_chat_write],
)
async def admin_send(
    body: ChatAdminMessageCreate,
    admin_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> ChatMessageCreatedResponse:
    """Save a staff reply. Admin replies are never sent to n8n (plugin parity)."""
    from sqlalchemy import select

    from app.modules.users.domain.models import UserProfile

    config = await chat_config.get_config(db)
    # display_name lives on UserProfile (keyed by user_id, not its own PK);
    # fall back to first+last, then the configured default support name.
    profile = (
        await db.execute(select(UserProfile).where(UserProfile.user_id == admin_id))
    ).scalar_one_or_none()
    display = ((profile.display_name if profile else "") or "").strip()
    if not display and profile:
        display = " ".join(filter(None, [profile.first_name, profile.last_name])).strip()
    if not display:
        display = config.get("default_support_name") or "پشتیبان"
    message = await ChatService.add_message(
        db,
        session_key=body.session_key,
        role=ChatRole.ADMIN,
        body=body.message,
        sender_name=display,
    )
    await db.commit()
    return ChatMessageCreatedResponse(id=message.id)


@admin_router.post(
    "/session-info",
    response_model=ChatSessionInfoResponse,
    summary="Pre-chat form values for a session (admin)",
    dependencies=[_require_chat_read],
)
async def admin_session_info(
    body: ChatReadRequest, db: AsyncSession = Depends(get_db)
) -> ChatSessionInfoResponse:
    fields = await ChatService.session_info(db, body.session_key)
    return ChatSessionInfoResponse(
        fields=[ChatSessionInfoField(label=f["label"], value=f["value"]) for f in fields]
    )


@admin_router.post(
    "/delete-session",
    response_model=ChatIdResponse,
    summary="Delete a conversation (admin)",
    dependencies=[_require_chat_write],
)
async def admin_delete_session(
    body: ChatReadRequest, db: AsyncSession = Depends(get_db)
) -> ChatIdResponse:
    await ChatService.delete_session(db, body.session_key)
    await db.commit()
    return ChatIdResponse(id=0)


@admin_router.post(
    "/handoff-toggle",
    response_model=ChatHandoffResponse,
    summary="Toggle human hand-off for a conversation (admin)",
    dependencies=[_require_chat_write],
)
async def admin_handoff_toggle(
    body: ChatHandoffToggleRequest, db: AsyncSession = Depends(get_db)
) -> ChatHandoffResponse:
    if body.state == 1:
        config = await chat_config.get_config(db)
        duration = int(config.get("handoff_duration", 60) or 60)
        until = datetime.now(UTC) + timedelta(minutes=max(1, duration))
        await ChatService.set_handoff(db, body.session_key, until=until)
    else:
        await ChatService.set_handoff(db, body.session_key, until=None)
        until = None
    await db.commit()
    return ChatHandoffResponse(handoff_until=_epoch(until))


@admin_router.get(
    "/online-users",
    response_model=ChatOnlineUsersResponse,
    summary="Live online visitors (admin)",
    dependencies=[_require_chat_read],
)
async def admin_online_users(db: AsyncSession = Depends(get_db)) -> ChatOnlineUsersResponse:
    users = await ChatService.online_users(db)
    config = await chat_config.get_config(db)
    show_fields = config.get("online_show_fields") or ["ip", "ua", "phone"]
    return ChatOnlineUsersResponse(
        users=[ChatOnlineUser.model_validate(u) for u in users],
        show_fields=list(show_fields),
    )


@admin_router.get(
    "/config",
    response_model=ChatConfigResponse,
    summary="Read the full widget config (admin)",
    dependencies=[_require_chat_read],
)
async def admin_get_config(db: AsyncSession = Depends(get_db)) -> ChatConfigResponse:
    # Mask the secrets (telegram token / webhook secret) — the admin form
    # pre-fills from this response, and set_config preserves a masked value, so
    # the live credential never leaves the server and is never overwritten.
    from app.modules.settings.schemas.settings import mask_secrets

    config = await chat_config.get_config(db)
    return ChatConfigResponse(config=mask_secrets(config))


@admin_router.put(
    "/config",
    response_model=ChatConfigResponse,
    summary="Update the widget config (admin)",
    dependencies=[_require_chat_write],
)
async def admin_set_config(
    body: ChatConfigUpdateRequest, db: AsyncSession = Depends(get_db)
) -> ChatConfigResponse:
    from app.modules.settings.schemas.settings import mask_secrets

    merged = await chat_config.set_config(db, body.config)
    await db.commit()
    return ChatConfigResponse(config=mask_secrets(merged))


def _epoch(dt: datetime | None) -> int:
    if dt is None:
        return 0
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return int(dt.timestamp())
