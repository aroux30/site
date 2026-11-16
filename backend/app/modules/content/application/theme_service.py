"""Site theme management service (Phase P2.0).

Handles creation, retrieval, updates, revision snapshotting, and atomic activation of site themes.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from app.core.exceptions.handlers import NotFoundError, ValidationError
from app.modules.content.domain.theme_models import SiteTheme, ThemeRevision
from app.modules.content.schemas.theme import (
    DesignTokensSchema,
    SiteThemeCreateRequest,
    SiteThemeUpdateRequest,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


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
    return target
