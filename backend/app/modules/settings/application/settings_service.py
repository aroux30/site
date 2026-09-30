"""Settings application service."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from sqlalchemy import select

from app.core.exceptions.handlers import ConflictError, NotFoundError
from app.modules.settings.domain.models import SiteSetting

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.settings.schemas.settings import SettingCreateRequest, SettingUpdateRequest

logger: structlog.stdlib.BoundLogger = structlog.get_logger()


def _preserve_masked(current: object, incoming: object) -> object:
    """Merge a write over the stored value, keeping masked secrets intact.

    ``SettingResponse`` masks credential values on the way out, and the admin
    settings form pre-fills its inputs from that same response. So an admin who
    edits an unrelated field and saves posts the literal mask back for every
    secret they never touched — and ``setting.value = data.value`` then stores
    ``********`` over the live Zarinpal merchant id or SMS API key. Adding the
    mask created that; this is the round-trip half of it.

    The rule is narrow on purpose: only a sub-key whose incoming value is
    *exactly* the mask marker is restored from the stored value. Any other
    incoming value, including an empty string, is a real edit and wins. That
    keeps "clear this secret" expressible while making the common case — save
    the form without retyping the secret — safe.
    """
    from app.modules.settings.schemas.settings import _MASK

    if not isinstance(current, dict) or not isinstance(incoming, dict):
        return incoming
    merged = dict(current)
    for key, new_value in incoming.items():
        if isinstance(new_value, dict) and isinstance(current.get(key), dict):
            merged[key] = _preserve_masked(current[key], new_value)
        elif new_value == _MASK and key in current:
            # Admin did not retype this secret; keep what we already had.
            continue
        else:
            merged[key] = new_value
    return merged


class SettingsService:
    """Manages application site settings."""

    @staticmethod
    async def get_all(
        db: AsyncSession,
        *,
        group: str | None = None,
        public_only: bool = False,
    ) -> list[SiteSetting]:
        """Fetch all settings matching criteria."""
        stmt = select(SiteSetting)
        if group:
            stmt = stmt.where(SiteSetting.group == group)
        if public_only:
            stmt = stmt.where(SiteSetting.is_public.is_(True))
        stmt = stmt.order_by(SiteSetting.key)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_by_key(db: AsyncSession, key: str) -> SiteSetting:
        """Fetch a single setting by key."""
        stmt = select(SiteSetting).where(SiteSetting.key == key)
        result = await db.execute(stmt)
        setting = result.scalar_one_or_none()
        if not setting:
            raise NotFoundError(resource="Setting", detail=f"Setting with key '{key}' not found.")
        return setting

    @staticmethod
    async def create(db: AsyncSession, data: SettingCreateRequest) -> SiteSetting:
        """Create a new setting."""
        stmt = select(SiteSetting).where(SiteSetting.key == data.key)
        existing = (await db.execute(stmt)).scalar_one_or_none()
        if existing:
            raise ConflictError(detail=f"Setting with key '{data.key}' already exists.")

        setting = SiteSetting(
            key=data.key,
            value=data.value,
            group=data.group,
            description=data.description,
            is_public=data.is_public,
        )
        db.add(setting)
        await db.flush()
        await logger.ainfo("setting_created", key=data.key)
        return setting

    @staticmethod
    async def update(db: AsyncSession, key: str, data: SettingUpdateRequest) -> SiteSetting:
        """Update an existing setting."""
        setting = await SettingsService.get_by_key(db, key)
        if data.value is not None:
            setting.value = _preserve_masked(setting.value, data.value)
        if data.group is not None:
            setting.group = data.group
        if data.description is not None:
            setting.description = data.description
        if data.is_public is not None:
            setting.is_public = data.is_public

        await db.flush()
        await logger.ainfo("setting_updated", key=key)
        return setting

    @staticmethod
    async def delete(db: AsyncSession, key: str) -> None:
        """Delete an existing setting by key."""
        setting = await SettingsService.get_by_key(db, key)
        await db.delete(setting)
        await db.flush()
        await logger.ainfo("setting_deleted", key=key)
