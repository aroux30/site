"""API routes for the Telegram order-notification module.

``router``       — public: the Telegram webhook endpoint
``admin_router`` — staff: config CRUD + test message
"""

from __future__ import annotations

import secrets
from typing import Any

import structlog
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.settings import get_settings
from app.core.database.session import get_db
from app.core.security.dependencies import get_current_user_id
from app.core.security.rate_limiter import limiter

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# ── Public router — webhook only ──────────────────────────────────────────

router = APIRouter()

# ── Admin router ──────────────────────────────────────────────────────────

admin_router = APIRouter(
    prefix="/admin/telegram-notify",
    tags=["admin-tgnotif"],
)


# ── Webhook endpoint ──────────────────────────────────────────────────────


@router.post(
    "/tgnotif/webhook",
    summary="Telegram bot webhook for order-action inline buttons",
)
@limiter.limit("120/minute")
async def tgnotif_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Receive Telegram callback_query updates when admins press inline buttons.

    Secured by Telegram's ``X-Telegram-Bot-Api-Secret-Token`` header. Pattern
    matches the chat module's webhook (compare_digest, production-requires-secret).
    """
    from app.core.exceptions.handlers import ForbiddenError
    from app.modules.tgnotif.application.tgnotif_config import get_config
    from app.modules.tgnotif.application.tgnotif_ingest import handle_update

    config = await get_config(db)
    expected = str(config.get("webhook_secret", "") or "").strip()
    if not expected:
        if get_settings().ENVIRONMENT == "production":
            raise ForbiddenError(detail="tgnotif webhook secret is not configured")
    else:
        presented = request.headers.get("x-telegram-bot-api-secret-token", "")
        if not secrets.compare_digest(presented, expected):
            raise ForbiddenError(detail="invalid webhook secret")

    try:
        update = await request.json()
    except (ValueError, UnicodeDecodeError):
        return {"status": "ignored"}
    if not isinstance(update, dict):
        return {"status": "ignored"}
    return await handle_update(db, update)


# ── Admin: get config ─────────────────────────────────────────────────────


@admin_router.get(
    "",
    summary="Get tgnotif config (bot_token masked)",
)
async def get_tgnotif_config(
    _admin_id: Any = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Return current configuration with private keys masked."""
    from app.modules.tgnotif.application.tgnotif_config import get_config, public_config

    config = await get_config(db)
    return {"config": public_config(config)}


# ── Admin: update config ──────────────────────────────────────────────────


@admin_router.put(
    "",
    summary="Update tgnotif config",
)
async def update_tgnotif_config(
    body: dict[str, Any],
    _admin_id: Any = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Update (partial) configuration. Masked secrets are preserved."""
    from app.modules.tgnotif.application.tgnotif_config import (
        public_config,
        set_config,
    )

    config = await set_config(db, body)
    await db.commit()
    return {"config": public_config(config)}


# ── Admin: register webhook ──────────────────────────────────────────────


@admin_router.post(
    "/register-webhook",
    summary="Register Telegram webhook URL for tgnotif bot",
)
async def register_tgnotif_webhook(
    _admin_id: Any = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Register/update the Telegram webhook URL using setWebhook API.

    Automatically builds the URL from SITE_URL/BACKEND_URL and sets the
    webhook_secret as X-Telegram-Bot-Api-Secret-Token.
    """
    import httpx

    from app.modules.tgnotif.application.tgnotif_config import get_config

    config = await get_config(db)
    bot_token = str(config.get("bot_token", "") or "").strip()
    if not bot_token:
        return {"ok": False, "error": "bot_token is not configured"}

    settings = get_settings()
    base_url = (
        getattr(settings, "BACKEND_URL", "")
        or getattr(settings, "SITE_URL", "")
        or ""
    )
    if not base_url:
        return {"ok": False, "error": "BACKEND_URL / SITE_URL is not configured"}

    webhook_url = f"{base_url.rstrip('/')}/api/v1/tgnotif/webhook"
    webhook_secret = str(config.get("webhook_secret", "") or "").strip()

    params: dict[str, str] = {"url": webhook_url}
    if webhook_secret:
        params["secret_token"] = webhook_secret

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"https://api.telegram.org/bot{bot_token}/setWebhook",
                params=params,
            )
        data = resp.json()
        ok = resp.status_code == 200 and data.get("ok")
        await logger.ainfo(
            "tgnotif_webhook_registered",
            ok=ok,
            webhook_url=webhook_url,
            description=data.get("description", ""),
        )
        return {"ok": ok, "webhook_url": webhook_url, "telegram_response": data}
    except Exception as exc:
        await logger.aerror("tgnotif_webhook_register_failed", error=str(exc))
        return {"ok": False, "error": str(exc)}


# ── Admin: send test message ─────────────────────────────────────────────


@admin_router.post(
    "/test",
    summary="Send a test notification to Telegram",
)
async def send_test_message(
    _admin_id: Any = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Send a test message to verify the Telegram bot configuration."""
    from app.modules.chat.application.telegram_client import TelegramClient, TelegramConfig
    from app.modules.tgnotif.application.tgnotif_config import get_config, is_ready

    config = await get_config(db)
    if not is_ready(config):
        return {"ok": False, "error": "Bot is not configured (bot_token or enabled missing)"}

    # Find the first configured chat_id
    chat_id = ""
    for key in (
        "chat_id_processing",
        "chat_id_pending",
        "chat_id_doing_verified",
        "chat_id_completed",
        "chat_id_canceled",
    ):
        chat_id = str(config.get(key, "") or "").strip()
        if chat_id:
            break

    if not chat_id:
        return {"ok": False, "error": "No chat_id configured for any status"}

    tg_config = TelegramConfig(
        bot_token=str(config.get("bot_token", "")),
        chat_id=chat_id,
    )
    client = TelegramClient(tg_config)
    result = await client.send_message(
        "🔔 <b>پیام تست اطلاع‌رسانی سفارشات</b>\n\n"
        "✅ اتصال بات تلگرام با موفقیت برقرار شد.\n"
        "از این پس تغییرات وضعیت سفارشات به این چت ارسال خواهد شد.",
    )

    if result.ok:
        return {"ok": True, "message": "پیام تست با موفقیت ارسال شد"}
    return {"ok": False, "error": result.error or "Unknown error"}
