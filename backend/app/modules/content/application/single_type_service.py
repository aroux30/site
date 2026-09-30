"""Strapi-style single types: named singleton config documents.

Backed by the ``site_settings`` key-value store (``group='cms'``), so no new
table is needed. Each registered single type has a fixed key, a JSON Schema
its value must validate against on write, and a default document returned
before the first admin save.
"""

from __future__ import annotations

import copy
import re
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import select

from app.core.exceptions.handlers import ValidationError
from app.modules.settings.domain.models import SiteSetting

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

GROUP = "cms"

_SLUG_RE = re.compile(r"^[a-z0-9-]{1,120}$")

# ── Registered single types ────────────────────────────────────────────────
# JSON Schemas are deliberately permissive subsets (type + required + simple
# item shapes) — enough to stop garbage documents without pulling in the
# full jsonschema dependency.

_HOMEPAGE_CONFIG_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "hero_banner": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "maxLength": 200},
                "subtitle": {"type": "string", "maxLength": 300},
                "image_media_id": {"type": "string"},
                "cta_text": {"type": "string", "maxLength": 80},
                "cta_url": {"type": "string", "maxLength": 500},
            },
            "additionalProperties": False,
        },
        "featured_category_slugs": {
            "type": "array",
            "items": {"type": "string", "pattern": _SLUG_RE.pattern},
            "maxItems": 12,
        },
        "announcement_bar": {
            "type": "object",
            "properties": {
                "enabled": {"type": "boolean"},
                "text": {"type": "string", "maxLength": 300},
                "url": {"type": "string", "maxLength": 500},
            },
            "additionalProperties": False,
        },
        "show_recent_blog_posts": {"type": "boolean"},
    },
    "additionalProperties": False,
}

_HOMEPAGE_CONFIG_DEFAULT: dict[str, Any] = {
    "hero_banner": None,
    "featured_category_slugs": [],
    "announcement_bar": {"enabled": False, "text": "", "url": ""},
    "show_recent_blog_posts": True,
}

_HEADER_MENU_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "cta_button": {
            "type": "object",
            "properties": {
                "label": {"type": "string", "maxLength": 60},
                "url": {"type": "string", "maxLength": 500},
                "visible": {"type": "boolean"},
            },
            "additionalProperties": False,
        },
        "top_bar_message": {"type": "string", "maxLength": 200},
        "highlight_menu_item": {"type": "string", "maxLength": 100},
    },
    "additionalProperties": False,
}

_HEADER_MENU_DEFAULT: dict[str, Any] = {
    "cta_button": {"label": "", "url": "", "visible": False},
    "top_bar_message": "",
    "highlight_menu_item": None,
}

# ── Theme tokens (WordPress theme.json parity) ──────────────────────────────
# The storefront reads design tokens from this single type instead of
# hardcoded CSS variables, so brand changes ship without a deploy.

_COLOR_RE = r"^#[0-9a-fA-F]{6}$"

_THEME_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "maxLength": 60},
        "colors": {
            "type": "object",
            "properties": {
                "primary": {"type": "string", "pattern": _COLOR_RE},
                "secondary": {"type": "string", "pattern": _COLOR_RE},
                "accent": {"type": "string", "pattern": _COLOR_RE},
                "background": {"type": "string", "pattern": _COLOR_RE},
                "surface": {"type": "string", "pattern": _COLOR_RE},
                "text": {"type": "string", "pattern": _COLOR_RE},
                "muted": {"type": "string", "pattern": _COLOR_RE},
            },
            "additionalProperties": False,
        },
        "typography": {
            "type": "object",
            "properties": {
                "font_family": {"type": "string", "maxLength": 120},
                "base_size_px": {"type": "number"},
                "heading_weight": {"type": "number"},
            },
            "additionalProperties": False,
        },
        "radius": {"type": "string", "maxLength": 20},
        "dark_mode_default": {"type": "boolean"},
    },
    "additionalProperties": False,
}

_THEME_DEFAULT: dict[str, Any] = {
    "name": "default",
    "colors": {
        "primary": "#0f766e",
        "secondary": "#334155",
        "accent": "#f59e0b",
        "background": "#ffffff",
        "surface": "#f8fafc",
        "text": "#0f172a",
        "muted": "#64748b",
    },
    "typography": {"font_family": "Vazirmatn, system-ui", "base_size_px": 16, "heading_weight": 700},
    "radius": "0.75rem",
    "dark_mode_default": False,
}

SINGLE_TYPES: dict[str, dict[str, Any]] = {
    "homepage_config": {
        "schema": _HOMEPAGE_CONFIG_SCHEMA,
        "default": _HOMEPAGE_CONFIG_DEFAULT,
        "description": "پیکربندی صفحه اصلی فروشگاه (بنر اصلی، دسته‌های ویژه، نوار اطلاع)",
    },
    "header_menu": {
        "schema": _HEADER_MENU_SCHEMA,
        "default": _HEADER_MENU_DEFAULT,
        "description": "تنظیمات تکی هدر (دکمه CTA، پیام نوار بالا، آیتم برجسته)",
    },
    "theme": {
        "schema": _THEME_SCHEMA,
        "default": _THEME_DEFAULT,
        "description": "توکن‌های تم فروشگاه (رنگ‌ها، تایپوگرافی، گردی گوشه‌ها) — بدون دیپلوی قابل تغییر",
    },
}


class UnknownSingleTypeError(ValidationError):
    pass


def _validate_value(schema: dict[str, Any], value: dict[str, Any], *, path: str = "") -> None:
    """Minimal JSON-Schema subset validator (object/array/string/boolean)."""
    if schema.get("type") == "object":
        if not isinstance(value, dict):
            raise ValidationError(f"مقدار {path or 'ریشه'} باید آبجکت باشد")
        props = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            unknown = set(value) - set(props)
            if unknown:
                raise ValidationError(f"کلیدهای نامجاز در {path or 'ریشه'}: {sorted(unknown)}")
        for key, sub_schema in props.items():
            if key in value and value[key] is not None:
                _validate_value(sub_schema, value[key], path=f"{path}.{key}".lstrip("."))
    elif schema.get("type") == "array":
        if not isinstance(value, list):
            raise ValidationError(f"مقدار {path} باید آرایه باشد")
        max_items = schema.get("maxItems")
        if max_items is not None and len(value) > max_items:
            raise ValidationError(f"آرایه {path} حداکثر {max_items} آیتم می‌گیرد")
        item_schema = schema.get("items")
        if item_schema:
            for i, item in enumerate(value):
                _validate_value(item_schema, item, path=f"{path}[{i}]")
    elif schema.get("type") == "string":
        if not isinstance(value, str):
            raise ValidationError(f"مقدار {path} باید رشته باشد")
        max_len = schema.get("maxLength")
        if max_len is not None and len(value) > max_len:
            raise ValidationError(f"رشته {path} حداکثر {max_len} کاراکتر")
        pattern = schema.get("pattern")
        if pattern and not re.fullmatch(pattern, value):
            raise ValidationError(f"رشته {path} با الگوی مجاز نمی‌خواند")
    elif schema.get("type") == "number":
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ValidationError(f"مقدار {path} باید عدد باشد")
    elif schema.get("type") == "boolean":
        if not isinstance(value, bool):
            raise ValidationError(f"مقدار {path} باید بولین باشد")


def list_single_types() -> list[dict[str, Any]]:
    """Registry listing for the admin picker."""
    return [{"key": key, "description": spec["description"]} for key, spec in SINGLE_TYPES.items()]


async def get_single_type(db: AsyncSession, key: str) -> tuple[dict[str, Any], Any]:
    """Return (value, updated_at); falls back to the default document."""
    spec = SINGLE_TYPES.get(key)
    if spec is None:
        raise UnknownSingleTypeError(f"تایپ تکی «{key}» شناخته‌شده نیست")

    stmt = select(SiteSetting).where(SiteSetting.key == key, SiteSetting.group == GROUP)
    setting = (await db.execute(stmt)).scalar_one_or_none()
    if setting is None:
        return copy.deepcopy(spec["default"]), None
    return setting.value, setting.updated_at


async def upsert_single_type(
    db: AsyncSession, key: str, value: dict[str, Any]
) -> tuple[dict[str, Any], Any]:
    """Validate and persist a single-type document."""
    spec = SINGLE_TYPES.get(key)
    if spec is None:
        raise UnknownSingleTypeError(f"تایپ تکی «{key}» شناخته‌شده نیست")

    _validate_value(spec["schema"], value)

    stmt = select(SiteSetting).where(SiteSetting.key == key, SiteSetting.group == GROUP)
    setting = (await db.execute(stmt)).scalar_one_or_none()
    if setting is None:
        setting = SiteSetting(
            key=key,
            value=value,
            group=GROUP,
            description=spec["description"],
            is_public=True,  # single types are storefront-visible config
        )
        db.add(setting)
    else:
        setting.value = value
    await db.flush()

    await logger.ainfo("single_type_upserted", key=key)
    return setting.value, setting.updated_at
