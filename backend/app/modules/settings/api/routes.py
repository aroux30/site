"""Settings API routes."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.security.dependencies import RequirePermissions
from app.modules.settings.application.settings_service import SettingsService
from app.modules.settings.schemas.settings import (
    PublicSettingResponse,
    SettingCreateRequest,
    SettingResponse,
    SettingUpdateRequest,
)

router = APIRouter()


@router.get(
    "/public",
    response_model=list[PublicSettingResponse],
    summary="List public site settings",
)
async def get_public_settings(
    group: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
) -> list[PublicSettingResponse]:
    """Return publicly exposed site configuration (logos, title, footer, etc.)."""
    settings = await SettingsService.get_all(db, group=group, public_only=True)
    return [PublicSettingResponse(key=s.key, value=s.value) for s in settings]


@router.get(
    "",
    response_model=list[SettingResponse],
    summary="List all site settings (admin)",
    dependencies=[Depends(RequirePermissions("settings:read"))],
)
async def get_all_settings(
    group: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
) -> list[SettingResponse]:
    """List all site settings with full metadata."""
    settings = await SettingsService.get_all(db, group=group, public_only=False)
    return [SettingResponse.model_validate(s) for s in settings]


@router.get(
    "/{key}",
    response_model=SettingResponse,
    summary="Get setting by key (admin)",
    dependencies=[Depends(RequirePermissions("settings:read"))],
)
async def get_setting(
    key: str,
    db: AsyncSession = Depends(get_db),
) -> SettingResponse:
    """Get a single setting."""
    setting = await SettingsService.get_by_key(db, key)
    return SettingResponse.model_validate(setting)


@router.post(
    "",
    response_model=SettingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create setting (admin)",
    dependencies=[Depends(RequirePermissions("settings:write"))],
)
async def create_setting(
    payload: SettingCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> SettingResponse:
    """Create a new setting key-value pair."""
    setting = await SettingsService.create(db, payload)
    await db.commit()
    return SettingResponse.model_validate(setting)


@router.patch(
    "/{key}",
    response_model=SettingResponse,
    summary="Update setting (admin)",
    dependencies=[Depends(RequirePermissions("settings:write"))],
)
async def update_setting(
    key: str,
    payload: SettingUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> SettingResponse:
    """Update an existing setting."""
    setting = await SettingsService.update(db, key, payload)
    await db.commit()
    return SettingResponse.model_validate(setting)
