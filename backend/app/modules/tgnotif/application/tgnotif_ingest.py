"""Handle incoming Telegram webhook updates for order-action buttons.

When an admin presses an inline button in the Telegram notification, Telegram
POSTs a callback_query. This module parses it, validates the action, and
updates the order status via the existing order_service — preserving the full
audit trail and state-machine validation.

Pattern mirrors app.modules.chat.application.telegram_ingest.
"""

from __future__ import annotations

import re
import uuid as uuid_mod
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.chat.application.telegram_client import TelegramClient, TelegramConfig
from app.modules.orders.domain.models import OrderStatus

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# callback_data format: "tgn_{status}_{order_uuid}"
_CALLBACK_PATTERN = re.compile(r"^tgn_(pending|processing|doing_verified|completed)_(.+)$")

# Map callback status slug to OrderStatus enum value
_ACTION_TO_STATUS: dict[str, str] = {
    "pending": OrderStatus.PENDING.value,
    "processing": OrderStatus.PROCESSING.value,
    "doing_verified": OrderStatus.DOING_VERIFIED.value,
    "completed": OrderStatus.COMPLETED.value,
}

# A sentinel UUID for bot-initiated status changes (no human admin actor).
# Used in the audit trail so ``changed_by`` is never NULL for tgnotif actions.
_BOT_ACTOR_ID = uuid_mod.UUID("00000000-0000-0000-0000-000000000001")


async def _build_client(bot_token: str) -> TelegramClient:
    """Build a TelegramClient with a dummy chat_id for answer-only calls.

    ``answerCallbackQuery`` does not require ``chat_id`` in the payload — it
    uses the ``callback_query_id`` directly. The TelegramClient's
    ``is_configured`` check requires a non-empty chat_id, so we pass a
    placeholder that is never used in the actual API call.
    """
    tg_config = TelegramConfig(
        bot_token=bot_token,
        chat_id="0",  # placeholder — answerCallbackQuery ignores chat_id
    )
    return TelegramClient(tg_config)


async def _resolve_client(db: AsyncSession) -> TelegramClient | None:
    """Build a TelegramClient from stored config, or None if not configured."""
    from app.modules.tgnotif.application.tgnotif_config import get_config, is_ready

    config = await get_config(db)
    if not is_ready(config):
        return None
    return await _build_client(str(config.get("bot_token", "")))


async def handle_update(db: AsyncSession, update: dict[str, Any]) -> dict[str, str]:
    """Process an incoming Telegram update.

    Returns a status dict — never raises for delivery problems.
    """
    callback = update.get("callback_query")
    if not callback:
        return {"status": "ignored", "reason": "no_callback_query"}

    data = callback.get("data", "")
    callback_id = callback.get("id", "")

    match = _CALLBACK_PATTERN.match(data)
    if not match:
        return {"status": "ignored", "reason": "unknown_callback_data"}

    action_slug = match.group(1)
    order_id_str = match.group(2)

    # Validate order ID
    try:
        order_id = uuid_mod.UUID(order_id_str)
    except (ValueError, TypeError):
        await logger.awarning("tgnotif_invalid_order_id", raw=order_id_str)
        client = await _resolve_client(db)
        if client and callback_id:
            await client.answer_callback_query(callback_id, "شناسه سفارش نامعتبر!")
        return {"status": "error", "reason": "invalid_order_id"}

    # Resolve target status
    target_status_value = _ACTION_TO_STATUS.get(action_slug)
    if not target_status_value:
        await logger.awarning("tgnotif_unknown_action", action=action_slug)
        client = await _resolve_client(db)
        if client and callback_id:
            await client.answer_callback_query(callback_id, "عملیات نامعتبر!")
        return {"status": "error", "reason": "unknown_action"}

    # Update order status via the order_service module function
    try:
        from app.modules.orders.application.order_service import admin_update_status

        await admin_update_status(
            db,
            order_id=order_id,
            new_status=target_status_value,
            actor_id=_BOT_ACTOR_ID,
            reason=f"تغییر وضعیت از بات تلگرام ({action_slug})",
        )
        await db.commit()

        await logger.ainfo(
            "tgnotif_status_changed",
            order_id=str(order_id),
            new_status=target_status_value,
        )

        # Answer the callback query in Telegram
        client = await _resolve_client(db)
        if client and callback_id:
            await client.answer_callback_query(
                callback_id,
                f"✅ وضعیت سفارش به «{_status_label(target_status_value)}» تغییر کرد!",
            )

        return {"status": "ok", "order_id": str(order_id), "new_status": target_status_value}

    except Exception as exc:
        await db.rollback()
        error_msg = str(exc)
        await logger.aerror(
            "tgnotif_status_change_failed",
            order_id=str(order_id),
            target=target_status_value,
            error=error_msg,
        )

        client = await _resolve_client(db)
        if client and callback_id:
            short_error = "تغییر وضعیت ناموفق بود!"
            if "transition" in error_msg.lower() or "valid" in error_msg.lower():
                short_error = "این تغییر وضعیت مجاز نیست!"
            await client.answer_callback_query(callback_id, f"❌ {short_error}")

        return {"status": "error", "reason": error_msg[:200]}


def _status_label(status_value: str) -> str:
    """Persian label for a status value (used in callback answers).

    Synced with frontend/lib/admin/order-domain.ts STATUS_VISUALS.
    """
    labels = {
        "pending": "در حال انجام",
        "processing": "در حال پردازش",
        "doing_verified": "در حال انجام (احراز شده)",
        "completed": "تکمیل شده",
    }
    return labels.get(status_value, status_value)
