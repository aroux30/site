"""Theme service — switchable storefront themes (WordPress appearance parity).

A theme here is a named token set. Activation copies the tokens into the
``theme`` single type, which the storefront already consumes via
``lib/theme.ts`` — so switching a theme changes the live site with no deploy.
Builtin presets are provisioned lazily and insert-only; operator-created
themes are deletable, builtins are not.

All lookups use primary-key fetches or full-table loads (the themes table is
a handful of rows by design) with plain ORM writes.
"""

from __future__ import annotations

import re
import uuid
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import select

from app.core.exceptions.handlers import ConflictError, NotFoundError, ValidationError
from app.modules.audit.application.audit_service import log_action
from app.modules.settings.domain.models import SiteTheme

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger()

THEME_TOKEN_KEYS = ("primary", "secondary", "accent", "background", "surface", "text", "muted")

BUILTIN_THEMES: tuple[dict[str, Any], ...] = (
    {
        "slug": "default",
        "name": "پیش‌فرض سبزفام",
        "tokens": {
            "colors": {
                "primary": "#0f766e",
                "secondary": "#134e4a",
                "accent": "#f59e0b",
                "background": "#fafaf9",
                "surface": "#ffffff",
                "text": "#1c1917",
                "muted": "#78716c",
            },
            "radius": "0.75rem",
            "dark_mode_default": False,
        },
    },
    {
        "slug": "minimal-light",
        "name": "روشن مینیمال",
        "tokens": {
            "colors": {
                "primary": "#2563eb",
                "secondary": "#1e3a8a",
                "accent": "#06b6d4",
                "background": "#ffffff",
                "surface": "#f8fafc",
                "text": "#0f172a",
                "muted": "#64748b",
            },
            "radius": "0.375rem",
            "dark_mode_default": False,
        },
    },
    {
        "slug": "midnight",
        "name": "شب",
        "tokens": {
            "colors": {
                "primary": "#8b5cf6",
                "secondary": "#6d28d9",
                "accent": "#22d3ee",
                "background": "#0b0f1a",
                "surface": "#141a2b",
                "text": "#e2e8f0",
                "muted": "#94a3b8",
            },
            "radius": "1rem",
            "dark_mode_default": True,
        },
    },
    {
        "slug": "warm-safran",
        "name": "گرم زعفرانی",
        "tokens": {
            "colors": {
                "primary": "#b45309",
                "secondary": "#7c2d12",
                "accent": "#dc2626",
                "background": "#fffbeb",
                "surface": "#fef3c7",
                "text": "#292524",
                "muted": "#a8a29e",
            },
            "radius": "0.5rem",
            "dark_mode_default": False,
        },
    },
)


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or f"theme-{uuid.uuid4().hex[:8]}"


def _validate_tokens(tokens: dict[str, Any]) -> None:
    colors = tokens.get("colors")
    if not isinstance(colors, dict) or not colors:
        raise ValidationError(detail="توکن‌ها باید شامل دیکشنری colors باشند.")
    for key, value in colors.items():
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", str(value)):
            raise ValidationError(detail=f"رنگ «{key}» باید hex شش‌رقمی باشد.")
    radius = tokens.get("radius")
    if radius is not None and not isinstance(radius, str):
        raise ValidationError(detail="شعاع گوشه‌ها باید رشته باشد.")


async def ensure_builtin_themes(db: AsyncSession) -> int:
    """Insert-only provisioning of the factory presets. Returns created count."""
    existing_rows = list((await db.execute(select(SiteTheme))).scalars())
    existing_slugs = {row.slug for row in existing_rows}
    # The "default" preset only claims active status when nothing is active
    # yet (fresh install) — never overriding an operator's choice.
    any_active = any(row.is_active for row in existing_rows)
    created = 0
    for preset in BUILTIN_THEMES:
        if preset["slug"] in existing_slugs:
            continue
        db.add(
            SiteTheme(
                slug=preset["slug"],
                name=preset["name"],
                tokens=preset["tokens"],
                is_builtin=True,
                is_active=preset["slug"] == "default" and not any_active,
            )
        )
        created += 1
    if created:
        await db.flush()
        await logger.ainfo("builtin_themes_provisioned", count=created)
    return created


async def list_themes(db: AsyncSession) -> list[SiteTheme]:
    """All themes, active first."""
    await ensure_builtin_themes(db)
    rows = list((await db.execute(select(SiteTheme))).scalars())
    rows.sort(key=lambda t: (not t.is_active, t.name))
    return rows


async def create_theme(
    db: AsyncSession,
    *,
    name: str,
    tokens: dict[str, Any],
    actor_id: uuid.UUID,
) -> SiteTheme:
    """Save the current look as a reusable, switchable theme."""
    _validate_tokens(tokens)
    slug = _slugify(name)
    existing_slugs = {row.slug for row in (await db.execute(select(SiteTheme))).scalars()}
    if slug in existing_slugs:
        raise ConflictError(detail=f"پوسته‌ای با نامک «{slug}» از قبل وجود دارد.")

    theme = SiteTheme(slug=slug, name=name.strip()[:100], tokens=tokens, is_builtin=False)
    db.add(theme)
    await db.flush()

    await log_action(
        db,
        actor_id=actor_id,
        action="settings.theme_created",
        resource="site_theme",
        resource_id=theme.id,
        after={"slug": slug, "name": name},
    )
    await logger.ainfo("theme_created", theme_id=str(theme.id), slug=slug)
    return theme


async def activate_theme(
    db: AsyncSession,
    *,
    theme_id: uuid.UUID,
    actor_id: uuid.UUID,
) -> SiteTheme:
    """Make one theme live by copying its tokens into the ``theme`` single type."""
    from app.modules.content.application.single_type_service import upsert_single_type

    theme = await db.get(SiteTheme, theme_id)
    if theme is None:
        raise NotFoundError(resource="Theme")

    for row in (await db.execute(select(SiteTheme))).scalars():
        row.is_active = row.id == theme.id
    await upsert_single_type(db, "theme", dict(theme.tokens))
    await db.flush()

    await log_action(
        db,
        actor_id=actor_id,
        action="settings.theme_activated",
        resource="site_theme",
        resource_id=theme.id,
        after={"slug": theme.slug},
    )
    await logger.ainfo("theme_activated", theme_id=str(theme.id), slug=theme.slug)
    return theme


async def delete_theme(
    db: AsyncSession,
    *,
    theme_id: uuid.UUID,
    actor_id: uuid.UUID,
) -> None:
    """Delete an operator-created theme (builtin presets are protected)."""
    theme = await db.get(SiteTheme, theme_id)
    if theme is None:
        raise NotFoundError(resource="Theme")
    if theme.is_builtin:
        raise ValidationError(detail="پوسته‌های پیش‌فرض قابل حذف نیستند.")

    await db.delete(theme)
    await db.flush()

    await log_action(
        db,
        actor_id=actor_id,
        action="settings.theme_deleted",
        resource="site_theme",
        resource_id=theme_id,
        before={"slug": theme.slug},
    )
    await logger.ainfo("theme_deleted", theme_id=str(theme_id))
