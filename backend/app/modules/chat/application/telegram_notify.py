"""Telegram hand-off notifications.

When a visitor asks for a human, push the conversation to the operator's
Telegram forum group: create (or reuse) a topic per session, post the user's
form info and recent history, and attach a "delete session" inline button. The
operator replies to a message in the topic and the reply lands back in the chat
(handled in ``telegram_ingest``).

Every function is best-effort and never raises: a shop without a bot token, or
a Telegram outage, must leave the in-app hand-off working.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from app.modules.chat.application import chat_config
from app.modules.chat.application.telegram_client import (
    TelegramClient,
    TelegramConfig,
    topic_thread_id,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_HISTORY_LIMIT = 100
_TG_MESSAGE_CAP = 4096


def _esc(value: object) -> str:
    """HTML-escape for Telegram ``parse_mode=HTML``."""
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


async def _resolve_client(db: AsyncSession) -> TelegramClient | None:
    config = await chat_config.get_config(db)
    tg = TelegramConfig(
        bot_token=(config.get("telegram_bot_token") or "").strip(),
        chat_id=(config.get("telegram_chat_id") or "").strip(),
    )
    if not tg.is_configured:
        return None
    return TelegramClient(tg)


async def forward_user_message(
    db: AsyncSession, *, session_key: str, message: str
) -> None:
    """Forward a visitor message to the session's Telegram topic (G1).

    During a live handoff the AI is muted, so the operator is the only one who
    can answer — but they can only answer what they can see. The plugin
    forwarded every user message to the topic (``n8n_chat_send`` php:1114-1123);
    without this the human takes over and the visitor's replies go nowhere
    visible. Best-effort: a missing token or a Telegram outage must not fail the
    visitor's send.
    """
    from app.modules.chat.application.chat_service import ChatService

    client = await _resolve_client(db)
    if client is None:
        return
    session = await ChatService.get_session_by_key(db, session_key)
    if session is None or not session.tg_topic_id:
        return
    text = (
        f"👤 <b>پیام کاربر:</b>\n{_esc(message)}\n\n"
        f"شناسه: <code>{_esc(session_key)}</code>"
    )
    await client.send_message(text, thread_id=session.tg_topic_id)
    logger.info("chat_user_message_forwarded", session_key=session_key)


async def notify_handoff(db: AsyncSession, *, session_key: str) -> None:
    """Create the topic (once) and post the info + history for a session."""
    from app.modules.chat.application.chat_service import ChatService
    from app.modules.chat.domain.models import ChatRole

    client = await _resolve_client(db)
    if client is None:
        return

    session = await ChatService.get_session_by_key(db, session_key)
    if session is None:
        return

    # Create the forum topic once, then remember its id on the session.
    thread_id = session.tg_topic_id
    if not thread_id:
        name = f"👤 {session.user_name or 'مهمان'} | #{session_key[-5:]}"
        created = await client.create_forum_topic(name)
        thread_id = topic_thread_id(created)
        if thread_id:
            session.tg_topic_id = thread_id
            await db.flush()

    # Message 1: who + form fields.
    config = await chat_config.get_config(db)
    info_lines = [f"🚨 <b>درخواست پشتیبانی انسانی</b>", "", f"شناسه گفتگو:\n<code>{_esc(session_key)}</code>", ""]
    info_lines.append(f"👤 <b>نام:</b> {_esc(session.user_name or 'مهمان')}")
    extra = session.user_data or {}
    for fd in config.get("prechat_fields", []):
        key, label = fd.get("key"), fd.get("label")
        if not key or not label:
            continue
        value = extra.get(key) or (session.user_phone if key == "phone" else "")
        if value:
            info_lines.append(f"🔹 <b>{_esc(label)}:</b> {_esc(value)}")
    await client.send_message("\n".join(info_lines), thread_id=thread_id)

    # Message 2: recent history + the delete button.
    messages = await ChatService.list_all_messages(db, session_key)
    messages = messages[-_HISTORY_LIMIT:]
    icons = {
        ChatRole.USER: "👤 کاربر",
        ChatRole.AI: "🤖 ربات",
        ChatRole.ADMIN: "👨‍💼 پشتیبان",
        ChatRole.SYSTEM: "⚙️ سیستم",
    }
    body = "\n\n".join(
        f"{icons.get(m.role, '•')}: {_esc(m.body)}" for m in messages
    )
    header = f"💬 <b>تاریخچه (شناسه: <code>{_esc(session_key)}</code>):</b>\n\n"
    footer = "\n<i>برای پاسخ، روی یکی از پیام‌ها Reply کنید.</i>"
    room = _TG_MESSAGE_CAP - len(header) - len(footer) - 16
    if len(body) > room:
        body = "[... پیام‌های قدیمی‌تر خلاصه شدند ...]\n\n" + body[-room:]
    reply_markup = {
        "inline_keyboard": [
            [{"text": "🗑 پایان و حذف سشن", "callback_data": f"del_sess_{session_key}"}]
        ]
    }
    text = (header + body + footer) if body else (
        f"💬 تاریخچه‌ای وجود ندارد.\nشناسه: <code>{_esc(session_key)}</code>{footer}"
    )
    await client.send_message(text, thread_id=thread_id, reply_markup=reply_markup)
    logger.info("chat_handoff_notified", session_key=session_key, thread_id=thread_id)
