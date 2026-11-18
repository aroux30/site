"""Site theme management service (Phase P2.0).

Handles creation, retrieval, updates, revision snapshotting, and atomic activation of site themes.
"""

from __future__ import annotations

import colorsys
import uuid
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from app.core.cache.redis import cache_delete, cache_get, cache_set
from app.core.exceptions.handlers import NotFoundError, ValidationError
from app.modules.content.domain.theme_models import SiteTheme, ThemeRevision
from app.modules.content.schemas.theme import (
    DesignTokensSchema,
    SiteThemeCreateRequest,
    SiteThemeUpdateRequest,
    compile_dtcg_to_css_variables,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

ACTIVE_THEME_CACHE_KEY = "content:theme:active:json"
ACTIVE_THEME_CSS_CACHE_KEY = "content:theme:active:css"


async def invalidate_theme_cache() -> None:
    """Evict active theme and compiled CSS from Redis cache."""
    try:
        await cache_delete(ACTIVE_THEME_CACHE_KEY)
        await cache_delete(ACTIVE_THEME_CSS_CACHE_KEY)
    except Exception as exc:
        logger.warning("theme_cache_invalidation_failed", error=str(exc))


def _snapshot(theme: SiteTheme, *, created_by: uuid.UUID | None, change_summary: str | None = None) -> ThemeRevision:
    """Build an immutable snapshot row for theme history."""
    return ThemeRevision(
        theme_id=theme.id,
        version=theme.version or 1,
        name=theme.name,
        tokens=theme.tokens,
        density_config=theme.density_config,
        change_summary=change_summary,
        created_by=created_by,
    )


async def _audit(
    db: AsyncSession,
    action: str,
    theme: SiteTheme,
    *,
    actor_id: uuid.UUID | None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> None:
    try:
        from app.modules.audit.application.audit_service import log_action

        await log_action(
            db,
            actor_id=actor_id,
            action=action,
            entity_type="site_theme",
            entity_id=theme.id,
            before_state=before,
            after_state=after or {"slug": theme.slug, "is_active": theme.is_active},
        )
    except Exception as exc:
        logger.warning("theme_audit_failed", action=action, theme_id=str(theme.id), error=str(exc))


async def create_theme(
    db: AsyncSession,
    *,
    name: str,
    slug: str,
    tokens: dict[str, Any] | DesignTokensSchema,
    description: str | None = None,
    is_active: bool = False,
    author_id: uuid.UUID | None = None,
) -> SiteTheme:
    """Create a new site theme, persisting initial revision."""
    clean_slug = slug.strip().lower()
    existing = await get_theme_by_slug(db, clean_slug)
    if existing:
        raise ValidationError(f"Theme slug '{clean_slug}' is already in use.")

    tokens_dict = tokens.model_dump(by_alias=True) if isinstance(tokens, DesignTokensSchema) else tokens

    theme = SiteTheme(
        name=name.strip(),
        slug=clean_slug,
        description=description.strip() if description else None,
        is_active=False,
        tokens=tokens_dict,
        version=1,
        created_by=author_id,
    )
    db.add(theme)
    await db.flush()

    # Initial revision snapshot
    rev = _snapshot(theme, created_by=author_id, change_summary="ایجاد اولیه تم")
    db.add(rev)
    await db.flush()

    if is_active:
        await activate_theme(db, theme.id, actor_id=author_id)

    await db.commit()
    await db.refresh(theme)
    if is_active:
        await invalidate_theme_cache()
    return theme


async def get_theme_by_id(db: AsyncSession, theme_id: uuid.UUID) -> SiteTheme | None:
    stmt = select(SiteTheme).where(SiteTheme.id == theme_id)
    res = await db.execute(stmt)
    return res.scalars().first()


async def get_theme_by_slug(db: AsyncSession, slug: str) -> SiteTheme | None:
    stmt = select(SiteTheme).where(SiteTheme.slug == slug.strip().lower())
    res = await db.execute(stmt)
    return res.scalars().first()


async def get_active_theme(db: AsyncSession) -> SiteTheme | None:
    stmt = select(SiteTheme).where(SiteTheme.is_active.is_(True))
    res = await db.execute(stmt)
    return res.scalars().first()


async def list_themes(db: AsyncSession, *, limit: int = 50, offset: int = 0) -> list[SiteTheme]:
    stmt = select(SiteTheme).order_by(SiteTheme.created_at.desc()).limit(limit).offset(offset)
    res = await db.execute(stmt)
    return list(res.scalars().all())


async def update_theme(
    db: AsyncSession,
    theme_id: uuid.UUID,
    data: SiteThemeUpdateRequest,
    *,
    editor_id: uuid.UUID | None = None,
) -> SiteTheme:
    theme = await get_theme_by_id(db, theme_id)
    if not theme:
        raise NotFoundError("Theme not found")

    before_state = {"tokens": theme.tokens, "name": theme.name}
    is_content_edit = False

    if data.name is not None:
        theme.name = data.name.strip()
    if data.description is not None:
        theme.description = data.description.strip()
    if data.tokens is not None:
        theme.tokens = data.tokens.model_dump(by_alias=True)
        is_content_edit = True

    if is_content_edit:
        theme.version = (theme.version or 1) + 1
        await db.flush()
        rev = _snapshot(theme, created_by=editor_id, change_summary="به‌روزرسانی توکن‌های تم")
        db.add(rev)

    if data.is_active is True and not theme.is_active:
        await activate_theme(db, theme.id, actor_id=editor_id)

    await db.flush()
    await _audit(db, "site_theme.updated", theme, actor_id=editor_id, before=before_state)
    await db.commit()
    await db.refresh(theme)
    if theme.is_active:
        await invalidate_theme_cache()
    return theme


async def activate_theme(
    db: AsyncSession,
    theme_id: uuid.UUID,
    *,
    actor_id: uuid.UUID | None = None,
) -> SiteTheme:
    """Atomically activate this theme, deactivating any currently active theme."""
    target = await get_theme_by_id(db, theme_id)
    if not target:
        raise NotFoundError("Theme not found")

    if target.is_active:
        return target

    # Deactivate all active themes first to satisfy partial unique index
    await db.execute(
        update(SiteTheme).where(SiteTheme.is_active.is_(True)).values(is_active=False)
    )
    await db.flush()

    target.is_active = True
    await db.flush()

    await _audit(db, "site_theme.activated", target, actor_id=actor_id)
    await db.commit()
    await db.refresh(target)
    await invalidate_theme_cache()
    return target


TAILWIND_HSL_VARS: frozenset[str] = frozenset({
    "--primary",
    "--secondary",
    "--background",
    "--foreground",
    "--card",
    "--card-foreground",
    "--popover",
    "--popover-foreground",
    "--primary-foreground",
    "--secondary-foreground",
    "--muted",
    "--muted-foreground",
    "--accent",
    "--accent-foreground",
    "--destructive",
    "--destructive-foreground",
    "--success",
    "--success-foreground",
    "--warning",
    "--warning-foreground",
    "--info",
    "--info-foreground",
    "--border",
    "--input",
    "--ring",
})


def hex_to_hsl_channels(hex_str: str) -> str:
    """Convert HEX color like #10b981 to space-separated HSL channels '160 84% 39%' for Tailwind hsl(var(...))."""
    clean = str(hex_str).strip().lstrip("#")
    if len(clean) == 3:
        clean = "".join(c * 2 for c in clean)
    if len(clean) != 6:
        return str(hex_str)
    try:
        r, g, b = (int(clean[i : i + 2], 16) / 255.0 for i in (0, 2, 4))
        h, l, s = colorsys.rgb_to_hls(r, g, b)
        h_deg = round(h * 360) % 360
        s_pct = round(s * 100)
        l_pct = round(l * 100)
        return f"{h_deg} {s_pct}% {l_pct}%"
    except Exception:
        return str(hex_str)


def compile_theme_css_variables(tokens_or_theme: dict[str, Any] | SiteTheme) -> dict[str, str]:
    """Compile and resolve DTCG tokens into a flat dictionary of standard CSS variables via DAG resolver."""
    raw_tokens = tokens_or_theme.tokens if isinstance(tokens_or_theme, SiteTheme) else tokens_or_theme
    schema = DesignTokensSchema.model_validate(raw_tokens)
    return compile_dtcg_to_css_variables(schema)


def compile_theme_css_string(tokens_or_theme: dict[str, Any] | SiteTheme) -> str:
    """Compile DTCG tokens into a valid CSS stylesheet string.

    Tailwind base variables (--primary, --secondary, etc.) are converted to space-separated
    HSL channels so that `hsl(var(--...))` evaluates to valid colors.
    Direct HEX values are also emitted under `--theme-*` prefix.
    Background and foreground are scoped to :root:not(.dark) to preserve dark mode.
    """
    vars_map = compile_theme_css_variables(tokens_or_theme)
    root_lines: list[str] = []
    light_only_lines: list[str] = []

    for k, v in vars_map.items():
        clean_key = k.lstrip("-")
        root_lines.append(f"  --theme-{clean_key}: {v};")

        if k in ("--background", "--foreground", "--card", "--popover"):
            val_out = hex_to_hsl_channels(v) if str(v).startswith("#") else v
            light_only_lines.append(f"  {k}: {val_out};")
        elif k in TAILWIND_HSL_VARS:
            val_out = hex_to_hsl_channels(v) if str(v).startswith("#") else v
            root_lines.append(f"  {k}: {val_out};")
        else:
            root_lines.append(f"  {k}: {v};")

    blocks = [":root {\n" + "\n".join(root_lines) + "\n}"]
    if light_only_lines:
        blocks.append(":root:not(.dark) {\n" + "\n".join(light_only_lines) + "\n}")

    return "\n\n".join(blocks)


async def list_theme_revisions(db: AsyncSession, theme_id: uuid.UUID) -> list[ThemeRevision]:
    """Retrieve full revision history of a site theme."""
    stmt = (
        select(ThemeRevision)
        .where(ThemeRevision.theme_id == theme_id)
        .order_by(ThemeRevision.created_at.desc())
    )
    res = await db.execute(stmt)
    return list(res.scalars().all())


async def restore_theme_revision(
    db: AsyncSession,
    theme_id: uuid.UUID,
    revision_id: uuid.UUID,
    *,
    actor_id: uuid.UUID | None = None,
) -> SiteTheme:
    """Restore a previous revision's design tokens and increment version."""
    theme = await get_theme_by_id(db, theme_id)
    if not theme:
        raise NotFoundError("Theme not found")

    rev_stmt = select(ThemeRevision).where(
        ThemeRevision.id == revision_id, ThemeRevision.theme_id == theme_id
    )
    rev = (await db.execute(rev_stmt)).scalars().first()
    if not rev:
        raise NotFoundError("ThemeRevision not found")

    before_state = {"tokens": theme.tokens, "version": theme.version}
    theme.tokens = rev.tokens
    if rev.density_config is not None:
        theme.density_config = rev.density_config

    theme.version = (theme.version or 1) + 1
    await db.flush()

    new_rev = _snapshot(
        theme,
        created_by=actor_id,
        change_summary=f"بازگردانی به نسخه {rev.version} ({rev.name})",
    )
    db.add(new_rev)
    await db.flush()

    await _audit(
        db,
        "site_theme.revision_restored",
        theme,
        actor_id=actor_id,
        before=before_state,
        after={"restored_revision": str(revision_id), "version": theme.version},
    )
    await db.commit()
    await db.refresh(theme)
    if theme.is_active:
        await invalidate_theme_cache()
    return theme


async def clone_theme(
    db: AsyncSession,
    source_theme_id: uuid.UUID,
    new_name: str,
    new_slug: str,
    *,
    actor_id: uuid.UUID | None = None,
) -> SiteTheme:
    """Clone an existing theme into a new inactive theme."""
    source = await get_theme_by_id(db, source_theme_id)
    if not source:
        raise NotFoundError("Source theme not found")

    clean_slug = new_slug.strip().lower()
    existing = await get_theme_by_slug(db, clean_slug)
    if existing:
        raise ValidationError(f"Theme slug '{clean_slug}' is already in use.")

    cloned = SiteTheme(
        name=new_name.strip(),
        slug=clean_slug,
        description=f"کلون شده از تم «{source.name}»",
        is_active=False,
        tokens=source.tokens,
        density_config=source.density_config,
        version=1,
        created_by=actor_id,
    )
    db.add(cloned)
    await db.flush()

    rev = _snapshot(cloned, created_by=actor_id, change_summary=f"کلون از تم {source.slug}")
    db.add(rev)
    await db.flush()

    await _audit(
        db,
        "site_theme.cloned",
        cloned,
        actor_id=actor_id,
        after={"source_theme": str(source.id), "new_slug": clean_slug},
    )
    await db.commit()
    await db.refresh(cloned)
    return cloned


async def delete_theme(
    db: AsyncSession,
    theme_id: uuid.UUID,
    *,
    actor_id: uuid.UUID | None = None,
) -> None:
    """Delete a theme (refused if currently active)."""
    theme = await get_theme_by_id(db, theme_id)
    if not theme:
        raise NotFoundError("Theme not found")

    if theme.is_active:
        raise ValidationError("امکان حذف تم فعال فعلی وجود ندارد. ابتدا تم دیگری را فعال کنید.")

    await _audit(db, "site_theme.deleted", theme, actor_id=actor_id)
    await db.delete(theme)
    await db.commit()

