"""Telegram order-notification config — stored as a single SiteSetting JSONB row.

Pattern mirrors app.modules.chat.application.chat_config exactly:
- One row in site_settings (key="tgnotif.config", group="tgnotif")
- Private keys never reach the browser
- Masked secrets (•••) are preserved on save, never overwritten
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.settings.domain.models import SiteSetting

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

CONFIG_KEY = "tgnotif.config"
CONFIG_GROUP = "tgnotif"
_MASK = "•" * 8

_PRIVATE_KEYS: frozenset[str] = frozenset({"bot_token", "webhook_secret"})

DEFAULT_CONFIG: dict[str, Any] = {
    # Connection
    "bot_token": "",
    "enabled": True,
    # Per-status routing — chat_id + optional topic_id (forum thread)
    "chat_id_pending": "",
    "chat_id_processing": "",
    "chat_id_doing_verified": "",
    "chat_id_completed": "",
    "chat_id_canceled": "",
    "topic_id_pending": "",
    "topic_id_processing": "",
    "topic_id_doing_verified": "",
    "topic_id_completed": "",
    "topic_id_canceled": "",
    # Webhook secret (X-Telegram-Bot-Api-Secret-Token)
    "webhook_secret": "",
    # Field toggles — which data fields appear in the notification message
    "show_order_id": True,
    "show_status": True,
    "show_items": True,
    "show_variant_info": True,
    "show_sku": False,
    "show_total": True,
    "show_subtotal": False,
    "show_shipping": False,
    "show_tax": False,
    "show_payment_method": True,
    "show_payment_status": False,
    "show_payment_ref": False,
    "show_coupon": True,
    "show_order_link": True,
    "show_date": True,
    "show_customer_name": True,
    "show_phone": True,
    "show_national_code": False,
    "show_verified": True,
    "show_ip": False,
    "show_address": False,
    "show_notes": False,
    "show_custom_fields": True,
}

_KNOWN_KEYS: frozenset[str] = frozenset(DEFAULT_CONFIG.keys())


def _merge(stored: dict[str, Any] | None) -> dict[str, Any]:
    """Return defaults overridden by stored values (unknown stored keys dropped)."""
    base = dict(DEFAULT_CONFIG)
    if stored:
        for k, v in stored.items():
            if k in _KNOWN_KEYS:
                base[k] = v
    return base


async def get_config(db: AsyncSession) -> dict[str, Any]:
    """Read config from DB, falling back to defaults for missing keys."""
    result = await db.execute(
        select(SiteSetting).where(SiteSetting.key == CONFIG_KEY)
    )
    row = result.scalar_one_or_none()
    stored = row.value if row and isinstance(row.value, dict) else None
    return _merge(stored)


async def set_config(db: AsyncSession, incoming: dict[str, Any]) -> dict[str, Any]:
    """Upsert config. Masked secrets (•••) are preserved — never overwritten."""
    current = await get_config(db)

    merged: dict[str, Any] = {}
    for k in _KNOWN_KEYS:
        if k not in incoming:
            merged[k] = current.get(k, DEFAULT_CONFIG[k])
            continue
        v = incoming[k]
        # Preserve the stored secret if the caller sent back the mask
        # (non-empty string consisting only of • characters).
        # An empty string means the user explicitly cleared the field.
        if k in _PRIVATE_KEYS and isinstance(v, str) and v and set(v) <= {"•"}:
            merged[k] = current.get(k, "")
        else:
            merged[k] = v

    result = await db.execute(
        select(SiteSetting).where(SiteSetting.key == CONFIG_KEY)
    )
    row = result.scalar_one_or_none()
    if row is None:
        row = SiteSetting(
            key=CONFIG_KEY,
            group=CONFIG_GROUP,
            value=merged,
            is_public=False,
            description="Telegram order-notification bot configuration",
        )
        db.add(row)
    else:
        row.value = merged

    await db.flush()
    await logger.ainfo("tgnotif_config_updated")
    return merged


def public_config(config: dict[str, Any]) -> dict[str, Any]:
    """Strip private keys and mask secrets for the browser."""
    out: dict[str, Any] = {}
    for k, v in config.items():
        if k in _PRIVATE_KEYS:
            out[k] = _MASK if v else ""
        else:
            out[k] = v
    return out


def config_hash(config: dict[str, Any]) -> str:
    """MD5 of the public config for cache-busting."""
    pub = public_config(config)
    raw = json.dumps(pub, sort_keys=True, ensure_ascii=False)
    return hashlib.md5(raw.encode()).hexdigest()  # noqa: S324


def is_ready(config: dict[str, Any]) -> bool:
    """True when at minimum the bot token is set and the feature is enabled."""
    return bool(config.get("enabled")) and bool(str(config.get("bot_token", "")).strip())
