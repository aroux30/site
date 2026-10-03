"""Site options service: global key-value settings (WordPress wp_options parity).

Provides a simple get/set/delete API for global site settings stored in the
database. Values are read from Postgres on every call — this module has no
cache layer, so do not read "cached in Redis" anywhere as a promise about this
code.

Usage:
    value = await SiteOptionsService.get(db, "blogname")
    await SiteOptionsService.set(db, "blogname", "My Site")
    all_opts = await SiteOptionsService.get_autoloaded(db)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import select

from app.modules.blog.domain.wp_parity_models import SiteOption

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


async def public_base_url(db: AsyncSession) -> str:
    """The site's public origin, with no trailing slash.

    Feeds, OPML, sitemaps, newsletter links and the routing feed all need it,
    and each used to default to ``https://example.com`` on its own — so a store
    that never set the option published placeholder URLs to every subscriber
    and every crawler. The stored ``home`` wins when an operator has set it;
    otherwise the deployment's own ``STOREFRONT_BASE_URL`` is the answer, and
    that is the same value the storefront itself is served from.
    """
    from app.core.config.settings import get_settings

    configured = await SiteOptionsService.get(db, "home") or await SiteOptionsService.get(
        db, "siteurl"
    )
    return (configured or get_settings().STOREFRONT_BASE_URL or "").strip().rstrip("/")


class SiteOptionsService:
    """CRUD for global site options."""

    @staticmethod
    async def get(db: AsyncSession, key: str, default: str | None = None) -> str | None:
        """Get a single option value by key."""
        stmt = select(SiteOption.option_value).where(SiteOption.option_key == key)
        result = (await db.execute(stmt)).scalar_one_or_none()
        return result if result is not None else default

    @staticmethod
    async def set(db: AsyncSession, key: str, value: str | None, *, autoload: bool = True) -> None:
        """Set an option (upsert)."""
        stmt = select(SiteOption).where(SiteOption.option_key == key)
        existing = (await db.execute(stmt)).scalar_one_or_none()
        if existing:
            existing.option_value = value
            existing.autoload = autoload
        else:
            db.add(SiteOption(option_key=key, option_value=value, autoload=autoload))
        await db.commit()
        logger.info("site_option_set", key=key)

    @staticmethod
    async def delete(db: AsyncSession, key: str) -> bool:
        """Delete an option by key."""
        stmt = select(SiteOption).where(SiteOption.option_key == key)
        option = (await db.execute(stmt)).scalar_one_or_none()
        if option:
            await db.delete(option)
            await db.commit()
            return True
        return False

    @staticmethod
    async def get_autoloaded(db: AsyncSession) -> dict[str, str | None]:
        """Fetch all autoloaded options as a dict."""
        stmt = select(SiteOption).where(SiteOption.autoload.is_(True))
        options = (await db.execute(stmt)).scalars().all()
        return {o.option_key: o.option_value for o in options}

    @staticmethod
    async def get_all(db: AsyncSession) -> dict[str, str | None]:
        """Fetch all options as a dict."""
        stmt = select(SiteOption).order_by(SiteOption.option_key)
        options = (await db.execute(stmt)).scalars().all()
        return {o.option_key: o.option_value for o in options}

    @staticmethod
    async def get_int(
        db: AsyncSession,
        key: str,
        default: int,
        *,
        minimum: int = 1,
        maximum: int | None = None,
    ) -> int:
        """Read an option as a bounded int.

        An option row is operator-editable text, so it can hold anything —
        empty, "ten", "-5", a value past what the caller can serve. Falling
        back to ``default`` (rather than raising) keeps a typo in the settings
        screen from taking the storefront down; the caller's own bounds still
        apply through ``minimum``/``maximum``.
        """
        raw = await SiteOptionsService.get(db, key)
        if raw is None:
            return default
        try:
            value = int(str(raw).strip())
        except (TypeError, ValueError):
            logger.warning("site_option_not_an_int", key=key, value=raw)
            return default
        value = max(minimum, value)
        if maximum is not None:
            value = min(maximum, value)
        return value
