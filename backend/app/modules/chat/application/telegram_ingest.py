"""Telegram webhook ingest: operator replies and inline-button callbacks.

Ports the plugin's ``telegram_webhook_handler``. Two paths:

* **Reply** — the operator replies to a hand-off message in the group; the
  session key is recovered from the quoted text and the reply is saved as an
  admin message, extending the hand-off window so the AI does not barge in.
* **Callback** — the "🗑 حذف سشن" inline button is pressed; the session is
  deleted and the topic removed.

The route calls these with the raw update dict; both return a small status
dict for logging. Nothing here raises on malformed input.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

import structlog

from app.modules.chat.application import chat_config
from app.modules.chat.application.telegram_client import TelegramClient, TelegramConfig

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

#: A loose fallback for a bare key with no ``<code>`` wrapper. The plugin used
#: 20+ chars here for exactly this reason: an 8-char floor matches ordinary
#: words ("operator"), so the generic path is deliberately long. Session keys
#: are a UUID (36) or ``sess_<ms>_<rand>`` (~25), both comfortably over 20.
_SESSION_RE = re.compile(r"\b([A-Za-z0-9_\-]{20,120})\b")


def _extract_session_key(text: str) -> str | None:
    """Recover the session key from a quoted hand-off message.

    Prefer the ``<code>`` block (the message always wraps the key in one), else
    fall back to the first 20+ char token — the same two-step the plugin used.
    """
    code = re.search(r"<code>([A-Za-z0-9_\-]{8,120})</code>", text)
    if code:
        return code.group(1)
    match = _SESSION_RE.search(text)
    return match.group(1) if match else None


async def _resolve_client(db: AsyncSession) -> TelegramClient | None:
    config = await chat_config.get_config(db)
    tg = TelegramConfig(
        bot_token=(config.get("telegram_bot_token") or "").strip(),
        chat_id=(config.get("telegram_chat_id") or "").strip(),
    )
    return TelegramClient(tg) if tg.is_configured else None


async def handle_update(db: AsyncSession, update: dict[str, Any]) -> dict[str, Any]:
    """Process one Telegram update. Returns a status dict (never raises)."""
    callback = update.get("callback_query")
    if isinstance(callback, dict):
        return await _handle_callback(db, callback)

    message = update.get("message")
    if isinstance(message, dict) and message.get("reply_to_message"):
        return await _handle_reply(db, message)

    return {"status": "ignored"}


async def _handle_callback(db: AsyncSession, callback: dict[str, Any]) -> dict[str, Any]:
    data = str(callback.get("data") or "")
    if not data.startswith("del_sess_"):
        return {"status": "ignored"}

    from app.modules.chat.application.chat_service import ChatService

    session_key = data[len("del_sess_") :]
    session = await ChatService.get_session_by_key(db, session_key)
    if session is None:
        return {"status": "no_session"}

    client = await _resolve_client(db)
    if client is not None and session.tg_topic_id:
        await client.delete_forum_topic(session.tg_topic_id)
    await ChatService.delete_session(db, session_key)
    await db.commit()

    if client is not None:
        await client.answer_callback_query(
            str(callback.get("id") or ""), "✅ سشن با موفقیت حذف شد."
        )
    logger.info("chat_telegram_session_deleted", session_key=session_key)
    return {"status": "callback_processed", "session": session_key}


async def _handle_reply(db: AsyncSession, message: dict[str, Any]) -> dict[str, Any]:
    from app.modules.chat.application.chat_service import ChatService
    from app.modules.chat.domain.models import ChatRole

    reply_text = str(message.get("text") or "")
    if not reply_text:
        return {"status": "no_text"}

    quoted = message.get("reply_to_message") or {}
    original_text = str(quoted.get("text") or quoted.get("caption") or "")
    session_key = _extract_session_key(original_text)
    if not session_key:
        return {"status": "no_session_in_quote"}

    session = await ChatService.get_session_by_key(db, session_key)
    if session is None:
        return {"status": "unknown_session"}

    sender = message.get("from") or {}
    # Backend attribution: username > first name > id (plugin priority).
    backend = (
        f"@{sender['username']}"
        if sender.get("username")
        else sender.get("first_name") or str(sender.get("id") or "?")
    )
    backend += " (تلگرام)"
    frontend_name = sender.get("first_name") or "پشتیبان"
    explicit_sender = f"{frontend_name}|{backend}"

    await ChatService.add_message(
        db,
        session_key=session_key,
        role=ChatRole.ADMIN,
        body=reply_text,
        sender_name=explicit_sender,
    )

    # Extend the hand-off so the AI does not immediately answer over the human.
    from datetime import UTC, datetime, timedelta

    config = await chat_config.get_config(db)
    duration = int(config.get("handoff_duration", 60) or 60)
    await ChatService.set_handoff(
        db, session_key, until=datetime.now(UTC) + timedelta(minutes=max(1, duration))
    )
    await db.commit()
    logger.info("chat_telegram_reply_ingested", session_key=session_key)
    return {"status": "replied", "session": session_key}
