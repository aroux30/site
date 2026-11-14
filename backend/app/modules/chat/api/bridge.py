"""WordPress-plugin bridge — runs the plugin's verbatim frontend JS unchanged.

The owner's directive: ship the plugin's ``assets/js/script.js`` as-is (it builds
the whole widget as inline-styled HTML) and give it ONE endpoint that speaks the
plugin's `admin-ajax.php` protocol, so no UI is ever re-built in React.

The plugin JS POSTs ``{action: 'n8n_chat_*', nonce, ...fields}`` and reads a
WordPress envelope ``{success: bool, data: ...}``. This module maps each action
to the SAME service logic the public REST routes use (imported, not duplicated),
and wraps the result in that envelope.

Mounted at ``/api/v1/chat/plugin-bridge`` on the public ``router``.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.datastructures import UploadFile

from app.core.database.session import get_db
from app.core.security.dependencies import get_current_user_optional
from app.core.security.rate_limiter import get_real_client_ip, limiter
from app.modules.chat.application import chat_config
from app.modules.chat.application.chat_service import ChatService
from app.modules.chat.application.n8n_client import N8nClient
from app.modules.chat.domain.models import ChatRole

logger = structlog.get_logger(__name__)

router = APIRouter()

#: Guest attachment ceiling (mirrors the media module's customer cap).
_GUEST_UPLOAD_MAX_BYTES = 10 * 1024 * 1024

_MESSAGES = {
    "start_session": "n8n_chat_start_session",
    "send": "n8n_chat_send",
    "history": "n8n_chat_history",
    "poll": "n8n_chat_poll",
    "unread": "n8n_chat_unread_counts",
    "heartbeat": "n8n_chat_heartbeat",
    "validate": "n8n_chat_validate_sessions",
    "handoff": "n8n_chat_user_handoff",
    "flow": "n8n_chat_flow_complete",
    "upload": "n8n_chat_upload",
}


def _ok(data: Any) -> JSONResponse:
    return JSONResponse({"success": True, "data": data})


def _err(message: str) -> JSONResponse:
    return JSONResponse({"success": False, "data": message})


def _row(m: Any) -> dict[str, Any]:
    """Plugin message row shape (mirrors routes._row / admin-chat.js fields)."""
    dt = m.created_at
    time_str = ""
    if dt is not None:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        local = dt.astimezone(UTC) + timedelta(hours=3, minutes=30)
        time_str = local.strftime("%H:%M")
    return {
        "id": m.id,
        "role": str(m.role),
        "message": m.body,
        "time": time_str,
        "is_read": 1 if m.is_read else 0,
        "sender_name": m.sender_name or "",
    }


def _epoch(dt: datetime | None) -> int:
    if dt is None:
        return 0
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return int(dt.timestamp())


async def _form(request: Request) -> dict[str, Any]:
    """Read the POST body as a dict — plugin sends form-encoded, we also accept
    JSON. Multipart (upload) is handled by FastAPI's UploadFile separately.

    jQuery serializes a JS array ``{session_ids:[sid]}`` as ``session_ids[]=sid``
    (repeated for multiple). ``dict(form)`` would keep the literal key
    ``"session_ids[]"`` (and only the LAST of a repeated plain key) — so
    normalize: strip the ``[]`` suffix and collect ALL values via ``getlist``.
    """
    ctype = request.headers.get("content-type", "")
    if "application/json" in ctype:
        try:
            return await request.json()
        except Exception:  # noqa: BLE001
            return {}
    try:
        form = await request.form()
    except Exception:  # noqa: BLE001
        return {}
    out: dict[str, Any] = {}
    for key in form.keys():
        name = key[:-2] if key.endswith("[]") else key
        values = form.getlist(key)
        if len(values) > 1 or key.endswith("[]"):
            out[name] = [str(v) for v in values]
        else:
            out[name] = values[0]
    return out


def _as_list(value: Any) -> list[str]:
    """Plugin sends arrays as ``session_ids[]`` (form) or a JSON list."""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value]
    if isinstance(value, str):
        v = value.strip()
        if v.startswith("["):
            try:
                return [str(x) for x in json.loads(v)]
            except Exception:  # noqa: BLE001
                return []
        return [v] if v else []
    return [str(value)]


@router.post("/plugin-bridge", summary="WP-plugin AJAX bridge (public)")
@limiter.limit("300/minute")
async def plugin_bridge(
    request: Request,
    user: dict[str, Any] | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Dispatch one plugin action to the existing chat service logic."""
    action = request.query_params.get("action") or ""
    file: UploadFile | None = None

    ctype = request.headers.get("content-type", "")
    if "multipart/form-data" in ctype:
        form = await request.form()
        action = action or str(form.get("action") or "")
        up = form.get("file")
        if isinstance(up, UploadFile):
            file = up
        fields: dict[str, Any] = dict(form)
    else:
        fields = await _form(request)
        action = action or str(fields.get("action") or "")

    try:
        if action == _MESSAGES["start_session"]:
            return await _start_session(db, fields, user)
        if action == _MESSAGES["send"]:
            return await _send(db, fields)
        if action == _MESSAGES["history"]:
            return await _history(db, fields)
        if action == _MESSAGES["poll"]:
            return await _poll(db, fields)
        if action == _MESSAGES["unread"]:
            return await _unread(db, fields)
        if action == _MESSAGES["heartbeat"]:
            return await _heartbeat(request, db, fields, user)
        if action == _MESSAGES["validate"]:
            return await _validate(db, fields)
        if action == _MESSAGES["handoff"]:
            return await _handoff(db, fields)
        if action == _MESSAGES["flow"]:
            return await _flow(db, fields)
        if action == _MESSAGES["upload"]:
            return await _upload(db, file)
    except Exception as exc:  # noqa: BLE001 — the plugin expects an envelope, never a 500
        logger.warning("plugin_bridge_error", action=action, error=str(exc))
        return _err("خطا در ارتباط با سرور. لطفاً دوباره تلاش کنید.")

    return _err("unknown action")


# ── action handlers ─────────────────────────────────────────────────────


def _sid(fields: dict[str, Any]) -> str:
    return str(fields.get("session_id") or fields.get("session_key") or "")


def _user_data(fields: dict[str, Any]) -> dict[str, Any]:
    raw = fields.get("user_data")
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip().startswith("{"):
        try:
            return json.loads(raw)
        except Exception:  # noqa: BLE001
            return {}
    return {}


async def _start_session(
    db: AsyncSession, fields: dict[str, Any], user: dict[str, Any] | None
) -> JSONResponse:
    key = _sid(fields)
    user_id = uuid.UUID(user["sub"]) if user and user.get("sub") else None
    session = await ChatService.start_session(
        db,
        session_key=key,
        user_name=str(fields.get("user_name") or ""),
        user_email=str(fields.get("user_email") or ""),
        user_phone=str(fields.get("user_phone") or ""),
        user_data=_user_data(fields),
        user_id=user_id,
    )
    if not await ChatService.list_all_messages(db, key):
        config = await chat_config.get_config(db)
        welcome = (config.get("welcome_message") or "").strip()
        if welcome:
            await ChatService.add_message(
                db, session_key=key, role=ChatRole.AI, body=welcome
            )
    await db.commit()
    return _ok({"session_id": session.session_key, "user_name": session.user_name})


async def _send(db: AsyncSession, fields: dict[str, Any]) -> JSONResponse:
    key = _sid(fields)
    message = str(fields.get("message") or "")
    if not message:
        return _err("empty message")
    msg = await ChatService.add_message(
        db, session_key=key, role=ChatRole.USER, body=message
    )
    await db.commit()
    session = await ChatService.get_session_by_key(db, key)
    if session is not None:
        if ChatService.handoff_active(session):
            from app.modules.chat.application.telegram_notify import forward_user_message

            await forward_user_message(db, session_key=key, message=message)
        else:
            config = await chat_config.get_config(db)
            extra = {"userName": session.user_name, **(session.user_data or {})}
            reply = await N8nClient().ask(
                webhook_url=config.get("webhook_url", ""),
                message=message,
                session_key=key,
                role="user",
                extra=extra,
            )
            if reply:
                await ChatService.add_message(
                    db, session_key=key, role=ChatRole.AI, body=reply
                )
                await db.commit()
    return _ok({"id": msg.id})


async def _history(db: AsyncSession, fields: dict[str, Any]) -> JSONResponse:
    key = _sid(fields)
    await ChatService.mark_read(db, key, by_user=True)
    messages = await ChatService.list_all_messages(db, key)
    session = await ChatService.get_session_by_key(db, key)
    handoff_until = _epoch(session.handoff_until) if session else 0
    await db.commit()
    return _ok(
        {"messages": [_row(m) for m in messages], "handoff_until": handoff_until}
    )


async def _poll(db: AsyncSession, fields: dict[str, Any]) -> JSONResponse:
    key = _sid(fields)
    last_id = int(fields.get("last_id") or 0)
    await ChatService.mark_read(db, key, by_user=True)
    messages = await ChatService.list_messages_since(db, key, last_id)
    updates = await ChatService.read_updates(db, key)
    session = await ChatService.get_session_by_key(db, key)
    handoff_until = _epoch(session.handoff_until) if session else 0
    await db.commit()
    return _ok(
        {
            "messages": [_row(m) for m in messages],
            "updates": updates,
            "handoff_until": handoff_until,
        }
    )


async def _unread(db: AsyncSession, fields: dict[str, Any]) -> JSONResponse:
    keys = _as_list(fields.get("session_ids"))
    counts = await ChatService.unread_counts_for(db, keys, for_admin=False)
    await db.commit()
    return _ok(counts)


async def _validate(db: AsyncSession, fields: dict[str, Any]) -> JSONResponse:
    keys = _as_list(fields.get("session_ids"))
    return _ok(await ChatService.valid_session_keys(db, keys))


async def _heartbeat(
    request: Request,
    db: AsyncSession,
    fields: dict[str, Any],
    user: dict[str, Any] | None,
) -> JSONResponse:
    key = _sid(fields)
    user_id = uuid.UUID(user["sub"]) if user and user.get("sub") else None
    session = await ChatService.get_session_by_key(db, key)
    name = session.user_name or "" if session is not None else ""
    if user_id is not None and session is not None:
        synced = await ChatService.sync_session_identity(db, session, user_id)
        if synced:
            name = synced
    await ChatService.heartbeat(
        db,
        session_key=key,
        tab_id=str(fields.get("tab_id") or "def"),
        user_name=name,
        user_ip=get_real_client_ip(request),
        user_agent=(request.headers.get("user-agent") or "")[:500],
        page_url=str(fields.get("page_url") or ""),
        page_title=str(fields.get("page_title") or ""),
        user_id=user_id,
    )
    await db.commit()
    return _ok({"id": 0})


async def _handoff(db: AsyncSession, fields: dict[str, Any]) -> JSONResponse:
    key = _sid(fields)
    config = await chat_config.get_config(db)
    duration = int(config.get("handoff_duration", 60) or 60)
    if duration < 1:
        duration = 60
    until = datetime.now(UTC) + timedelta(minutes=duration)
    await ChatService.set_handoff(db, key, until=until)
    # B1: plugin parity (php:1510) — a blank handoff_system_message falls back to
    # the default notice, so the visitor ALWAYS sees "support requested".
    sys_msg = chat_config.handoff_system_message(config)
    support_name = config.get("default_support_name") or "پشتیبان"
    await ChatService.add_message(
        db,
        session_key=key,
        # B2: plugin parity — the handoff system notice is role=admin
        # (php:1513 `save_msg($sid, 'admin', …)`), so it shows as unread to
        # the visitor and their badge/beep fires. A SYSTEM role is never
        # read-marked (mark_read only touches ADMIN/AI) and never unread.
        role=ChatRole.ADMIN,
        body=sys_msg,
        sender_name=f"{support_name}|سیستم",
    )
    await db.commit()
    from app.modules.chat.application.telegram_notify import notify_handoff

    await notify_handoff(db, session_key=key)
    return _ok({"handoff_until": _epoch(until)})


async def _flow(db: AsyncSession, fields: dict[str, Any]) -> JSONResponse:
    import hashlib

    key = _sid(fields)
    raw = fields.get("flow_context")
    try:
        entries = json.loads(raw) if isinstance(raw, str) else (raw or [])
    except Exception:  # noqa: BLE001
        entries = []
    final_msg = str(fields.get("final_msg") or "")

    # B3: the same 5s content-hash idempotency lock the REST route uses (plugin
    # parity — php:1142 transient). Without it a double-click on the last flow
    # button stored duplicate messages and re-asked n8n.
    digest = hashlib.sha256(
        json.dumps([final_msg, entries], ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    from app.modules.chat.application.chat_service import flow_lock_acquired

    if not await flow_lock_acquired(key, digest):
        return _ok({"last_id": 0, "saved_ids": []})

    saved_ids: list[int] = []
    last_id = 0
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        role = entry.get("role") if entry.get("role") in ("user", "ai", "admin") else "ai"
        text = str(entry.get("message") or "").strip()
        if not text:
            continue
        msg = await ChatService.add_message(
            db,
            session_key=key,
            role=ChatRole(role),
            body=text,
            sender_name=str(entry.get("sender_name") or ""),
        )
        saved_ids.append(msg.id)
        if role == "user":
            last_id = msg.id
    if final_msg.strip():
        msg = await ChatService.add_message(
            db, session_key=key, role=ChatRole.USER, body=final_msg.strip()
        )
        saved_ids.append(msg.id)
        last_id = msg.id
    await db.commit()

    lines = [
        f"{'👤 کاربر' if e.get('role') == 'user' else '🤖 بات'}: {e.get('message')}"
        for e in entries
        if isinstance(e, dict) and str(e.get("message") or "").strip()
    ]
    if final_msg.strip():
        lines.append(f"👤 کاربر: {final_msg.strip()}")
    transcript = "\n".join(lines)
    config = await chat_config.get_config(db)
    session = await ChatService.get_session_by_key(db, key)
    if transcript and session is not None and not ChatService.handoff_active(session):
        reply = await N8nClient().ask(
            webhook_url=config.get("webhook_url", ""),
            message=transcript,
            session_key=key,
            role="user",
            extra={"userName": session.user_name, **(session.user_data or {})},
        )
        if reply:
            await ChatService.add_message(db, session_key=key, role=ChatRole.AI, body=reply)
            await db.commit()
    return _ok({"last_id": last_id, "saved_ids": saved_ids})


async def _upload(db: AsyncSession, file: UploadFile | None) -> JSONResponse:
    if file is None:
        return _err("no file")
    from app.modules.media.application.media_service import MediaService

    asset = await MediaService.upload_file(
        db, file, uploader_id=None, folder="chat", max_bytes=_GUEST_UPLOAD_MAX_BYTES
    )
    await db.commit()
    return _ok({"url": asset.file_url, "name": file.filename or ""})
