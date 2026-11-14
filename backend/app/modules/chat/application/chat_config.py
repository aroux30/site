"""Widget configuration: one ``SiteSetting`` row holding the whole widget config.

Mirrors the WordPress plugin's ``n8n_chat_*`` options, collapsed into a single
JSONB row (key ``chat.widget``, group ``chat``). The public subset served to the
storefront is derived here so the n8n URL and Telegram credentials never leave
the server.
"""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import select

from app.modules.chat.schemas.chat import ChatPublicConfig
from app.modules.settings.domain.models import SiteSetting

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger()

CONFIG_KEY = "chat.widget"
CONFIG_GROUP = "chat"

#: Plugin parity (php:1510): when ``handoff_system_message`` is blank the plugin
#: substitutes this exact text before saving the notice — the visitor must always
#: see a "support requested" system message. The port previously skipped the
#: notice entirely when the operator cleared the field.
DEFAULT_HANDOFF_SYSTEM_MESSAGE = (
    "⏳ درخواست پشتیبانی انسانی ثبت شد. تیم پشتیبانی به‌زودی پاسخگو خواهد بود."
)


def handoff_system_message(config: dict[str, Any]) -> str:
    """The handoff notice body, with the plugin's blank-fallback applied."""
    text = str(config.get("handoff_system_message") or "").strip()
    return text or DEFAULT_HANDOFF_SYSTEM_MESSAGE


#: Keys that must never be serialized to the public config endpoint.
_PRIVATE_KEYS = frozenset({"n8n_webhook_url", "telegram_bot_token", "telegram_chat_id"})

#: Default widget config — identical defaults to the plugin's ``defaults()``.
DEFAULT_CONFIG: dict[str, Any] = {
    "enabled": True,
    "lang": "fa",
    "color_primary": "#007ACC",
    "color_header": "#007ACC",
    "color_button": "#007ACC",
    "color_chatbg": "#EEEEEE",
    "color_viewbg": "#EEEEEE",
    "welcome_title": "",
    "welcome_sub": "",
    "welcome_message": "",
    "webhook_url": "",
    "telegram_bot_token": "",
    "telegram_chat_id": "",
    # Shared secret the Telegram webhook must present (X-Telegram-Bot-Api-Secret-Token),
    # set by the operator when registering the webhook. Blank = accept any
    # (dev only); the route refuses when configured and the header mismatches.
    "telegram_webhook_secret": "",
    "auto_delete_days": 60,
    "date_format": "shamsi",
    "widget_width": 394,
    "widget_height": 650,
    "btn_bottom_desktop": 20,
    "btn_side_desktop": 20,
    "btn_bottom_mobile": 70,
    "btn_side_mobile": 12,
    "widget_icon_url": "",
    "user_avatar_url": "",
    "ai_avatar_url": "",
    "admin_avatar_url": "",
    "handoff_duration": 60,
    "default_support_name": "پشتیبان",
    "handoff_button_text": "انتقال به انسان",
    "handoff_success_text": "✅ وصل شد",
    "handoff_system_message": "⏳ درخواست پشتیبانی انسانی ثبت شد. تیم پشتیبانی به‌زودی پاسخگو خواهد بود.",
    "quick_replies": [],
    "quick_flow": [],
    "prechat_fields": [],
    "faqs": [],
    "news": [],
    "proactive_enabled": False,
    "proactive_delay": 5,
    "proactive_text": "سلام! راهنمایی نیاز دارید؟",
    "proactive_cooldown": 6,
    # Owner (2026-10-13): the proactive bubble's default background must match
    # the widget icon's button color, with white text (mirrors the live WP site,
    # where color_proactive_bg = C.button). Both keys stay editable from the
    # admin panel («محتوا» → «پاپ‌آپ هوشمند») — this is only the default.
    "color_proactive_bg": "#007ACC",
    "color_proactive_text": "#ffffff",
    "online_show_fields": ["ip", "ua", "phone"],
    # NOTE: the WordPress plugin's `custom_sound_url` (upload an MP3) is
    # deliberately NOT ported. The widget plays a built-in two-tone Web Audio
    # beep instead — no file to host, no upload surface, no autoplay policy
    # surprise. If an operator later wants a custom sound, add the key here and
    # branch on it in the widget's `playBeep`/notification path.
}


def _merged(stored: dict[str, Any] | None) -> dict[str, Any]:
    """Stored config on top of the defaults (missing keys keep their default)."""
    merged = dict(DEFAULT_CONFIG)
    if isinstance(stored, dict):
        merged.update(stored)
    return merged


async def get_config(db: AsyncSession) -> dict[str, Any]:
    """Return the full private config (defaults + stored)."""
    row = (
        await db.execute(select(SiteSetting).where(SiteSetting.key == CONFIG_KEY))
    ).scalar_one_or_none()
    return _merged(row.value if row else None)


async def set_config(db: AsyncSession, incoming: dict[str, Any]) -> dict[str, Any]:
    """Upsert the config. Only known keys are accepted; secrets survive a masked
    round-trip via the same rule the settings service uses."""
    current = await get_config(db)
    from app.modules.settings.schemas.settings import _MASK

    merged = dict(current)
    for key, value in incoming.items():
        if key not in DEFAULT_CONFIG:
            continue
        # A secret posted back as the mask marker was not retyped — keep it.
        if value == _MASK and isinstance(current.get(key), str) and current.get(key):
            continue
        merged[key] = value

    row = (
        await db.execute(select(SiteSetting).where(SiteSetting.key == CONFIG_KEY))
    ).scalar_one_or_none()
    if row is None:
        row = SiteSetting(key=CONFIG_KEY, group=CONFIG_GROUP, is_public=False, value=merged)
        db.add(row)
    else:
        row.value = merged
    await db.flush()
    logger.info("chat_config_saved")
    return merged


def config_hash(config: dict[str, Any]) -> str:
    """Stable hash of the public config — the plugin's cache-busting ``config.hash``."""
    safe = {k: v for k, v in config.items() if k not in _PRIVATE_KEYS and k != "webhook_url"}
    payload = json.dumps(safe, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.md5(payload.encode("utf-8")).hexdigest()


def public_config(config: dict[str, Any]) -> ChatPublicConfig:
    """Derive the browser-safe subset (private keys stripped) + a config hash."""
    safe = {k: v for k, v in config.items() if k not in _PRIVATE_KEYS}
    # The widget's fetch key is ``webhook_url`` (plugin naming); map from the
    # private ``webhook_url`` but never expose it — the server proxies instead.
    safe.pop("webhook_url", None)
    safe["proactive_enabled"] = bool(config.get("proactive_enabled"))
    model = ChatPublicConfig.model_validate(safe)
    model.config_hash = config_hash(config)
    return model


async def is_enabled(db: AsyncSession) -> bool:
    """Whether the chat widget is switched on (site option, read live)."""
    from app.modules.settings.application.site_options_service import SiteOptionsService

    raw = await SiteOptionsService.get(db, "chat_enabled", "1")
    return str(raw or "1").strip().lower() in {"1", "true", "yes", "on", "فعال", "بله"}
