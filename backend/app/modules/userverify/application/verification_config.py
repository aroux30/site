"""Verification config: one ``SiteSetting`` row (key ``userverify.config``).

Ports the plugin's ``uv_telegram_token`` / ``uv_telegram_chat_id`` options plus
two switches the plugin hard-coded:

- ``enabled`` — the whole verified-lane behaviour. When off, paid orders take
  the normal ``pending`` lane regardless of the buyer's badge.
- ``telegram_notifications`` — send the "status changed" message to Telegram
  on every verify/unverify flip (plugin always sent when credentials existed).

Credentials fall back to the chat module's Telegram bot
(``chat.widget.telegram_bot_token`` / ``telegram_chat_id``) when blank here, so
a shop that already wired the chat hand-off needs no second bot.
"""

from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy import select

from app.modules.settings.domain.models import SiteSetting

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

CONFIG_KEY = "userverify.config"
CONFIG_GROUP = "userverify"

DEFAULT_CONFIG: dict[str, Any] = {
    "enabled": True,
    "telegram_notifications": True,
    "telegram_bot_token": "",
    "telegram_chat_id": "",
}


def _merged(stored: dict[str, Any] | None) -> dict[str, Any]:
    merged = dict(DEFAULT_CONFIG)
    if isinstance(stored, dict):
        merged.update({k: v for k, v in stored.items() if k in DEFAULT_CONFIG})
    merged["enabled"] = bool(merged.get("enabled", True))
    merged["telegram_notifications"] = bool(merged.get("telegram_notifications", True))
    merged["telegram_bot_token"] = str(merged.get("telegram_bot_token") or "").strip()
    merged["telegram_chat_id"] = str(merged.get("telegram_chat_id") or "").strip()
    return merged


async def get_config(db) -> dict[str, Any]:
    row = (
        await db.execute(select(SiteSetting).where(SiteSetting.key == CONFIG_KEY))
    ).scalar_one_or_none()
    return _merged(row.value if row else None)


async def set_config(db, incoming: dict[str, Any]) -> dict[str, Any]:
    """Upsert; only known keys. Masked secrets survive a round-trip."""
    from app.modules.settings.schemas.settings import _MASK

    current = await get_config(db)
    merged = dict(current)
    for key, value in incoming.items():
        if key not in DEFAULT_CONFIG:
            continue
        if value == _MASK and isinstance(current.get(key), str) and current.get(key):
            continue
        merged[key] = value

    row = (
        await db.execute(select(SiteSetting).where(SiteSetting.key == CONFIG_KEY))
    ).scalar_one_or_none()
    clean = _merged(merged)
    if row is None:
        row = SiteSetting(key=CONFIG_KEY, group=CONFIG_GROUP, is_public=False, value=clean)
        db.add(row)
    else:
        row.value = clean
    from sqlalchemy.orm import attributes

    attributes.flag_modified(row, "value")
    await db.flush()
    logger.info("userverify_config_saved")
    return clean


def public_view(config: dict[str, Any]) -> dict[str, Any]:
    """Admin-safe view: secrets masked, never returned raw."""
    from app.modules.settings.schemas.settings import _MASK

    return {
        "enabled": bool(config.get("enabled", True)),
        "telegram_notifications": bool(config.get("telegram_notifications", True)),
        "telegram_bot_token": _MASK if config.get("telegram_bot_token") else "",
        "telegram_chat_id": str(config.get("telegram_chat_id") or ""),
    }
