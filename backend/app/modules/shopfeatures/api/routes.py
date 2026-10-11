"""Shop feature switch API routes.

Two surfaces:

* ``GET  /api/v1/shop-features`` — PUBLIC read of every switch state. The
  storefront needs this before login (the header renders the compare link for
  guests), so it must not require authentication. It exposes only booleans.
* ``GET/PUT /api/v1/admin/shop-features`` — the admin panel's read/write, behind
  ``settings:manage`` (the same permission the rest of the settings surface uses;
  these are ordinary ``site_options`` rows, not a new permission domain).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.security.dependencies import RequirePermissions
from app.modules.shopfeatures.application import shop_features_service as service

router = APIRouter()

# Mounted at /api/v1/admin/shop-features by app.main, like the wallet's
# admin_router. The prefix is required: main.py mounts admin routers at the bare
# API prefix, so an unprefixed /settings here would collide with the real
# settings routes.
admin_router = APIRouter(prefix="/admin/shop-features", tags=["admin-shop-features"])

_require_settings_manage = Depends(RequirePermissions("settings:manage"))


class ShopFeatureSwitchResponse(BaseModel):
    """One switch after a change.

    A dedicated model rather than a bare dict: an endpoint annotated
    ``-> dict[str, bool`` makes FastAPI infer that as the response_model, so a
    ``{"key": ..., "enabled": ...}`` payload fails validation with
    ``bool_parsing``.
    """

    key: str
    enabled: bool


@router.get("", summary="Read the storefront feature switches (public)")
async def get_shop_features(
    db: AsyncSession = Depends(get_db),
) -> dict[str, bool]:
    """Return every shop feature switch state.

    Public and unauthenticated on purpose: the header renders the wishlist and
    compare links for signed-out visitors, so the client has to know the state
    before it knows who the user is. Only booleans are exposed — no data, no
    user-specific information.
    """
    return await service.feature_state(db)


@admin_router.get("", summary="Read the shop feature switches (admin)")
async def get_shop_features_admin(
    db: AsyncSession = Depends(get_db),
    _: None = _require_settings_manage,
) -> dict[str, bool]:
    """Return every shop feature switch state."""
    return await service.get_switches(db)


@admin_router.put(
    "/{key}",
    response_model=ShopFeatureSwitchResponse,
    summary="Set a shop feature switch (admin)",
)
async def set_shop_feature(
    key: str,
    enabled: bool = Query(..., description="Whether the feature is enabled"),
    db: AsyncSession = Depends(get_db),
    _: None = _require_settings_manage,
) -> ShopFeatureSwitchResponse:
    """Enable/disable a storefront feature (wishlist, compare).

    An unknown key raises the service's Persian ValidationError unchanged.
    """
    value = await service.set_switch(db, key=key, enabled=enabled)
    return ShopFeatureSwitchResponse(key=key, enabled=value)
