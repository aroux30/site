"""REST API routes for the SEO module.

Provides endpoints for fetching and managing per-resource SEO metadata.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.security.dependencies import RequirePermissions
from app.modules.seo.application.seo_service import SEOService
from app.modules.seo.schemas.seo import (
    SEOMetadataCreate,
    SEOMetadataResponse,
)

router = APIRouter()

admin_router = APIRouter(
    prefix="/admin/seo",
    tags=["admin-seo"],
)

_require_seo_write = Depends(RequirePermissions("seo:write"))


# ============================================================================
# Public Endpoints (on router: /api/v1/seo/...)
# ============================================================================


@router.get(
    "/{resource_type}/{resource_id}",
    response_model=SEOMetadataResponse,
    summary="Get SEO metadata for a resource",
    description="Retrieve SEO, Open Graph tags, and JSON-LD schema for a specific product, category, or blog post.",
)
async def get_seo_metadata(
    resource_type: str,
    resource_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> SEOMetadataResponse:
    svc = SEOService(db)
    return await svc.get_by_resource(resource_type=resource_type, resource_id=resource_id)


# ============================================================================
# Admin Endpoints (on admin_router: /api/v1/admin/seo/...)
# ============================================================================


@admin_router.put(
    "/{resource_type}/{resource_id}",
    response_model=SEOMetadataResponse,
    summary="Upsert SEO metadata for a resource (Admin)",
    dependencies=[_require_seo_write],
)
async def admin_upsert_seo_metadata(
    resource_type: str,
    resource_id: uuid.UUID,
    data: SEOMetadataCreate,
    db: AsyncSession = Depends(get_db),
) -> SEOMetadataResponse:
    svc = SEOService(db)
    return await svc.upsert_for_resource(
        resource_type=resource_type,
        resource_id=resource_id,
        data=data,
    )


@admin_router.delete(
    "/{resource_type}/{resource_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete SEO metadata for a resource (Admin)",
    dependencies=[_require_seo_write],
)
async def admin_delete_seo_metadata(
    resource_type: str,
    resource_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    svc = SEOService(db)
    await svc.delete_for_resource(resource_type=resource_type, resource_id=resource_id)


# ── Also mount on router directly as aliases ───────────────────────────────────


@router.put(
    "/{resource_type}/{resource_id}",
    response_model=SEOMetadataResponse,
    summary="Upsert SEO metadata for a resource",
    dependencies=[_require_seo_write],
)
async def router_upsert_seo_metadata(
    resource_type: str,
    resource_id: uuid.UUID,
    data: SEOMetadataCreate,
    db: AsyncSession = Depends(get_db),
) -> SEOMetadataResponse:
    return await admin_upsert_seo_metadata(
        resource_type=resource_type,
        resource_id=resource_id,
        data=data,
        db=db,
    )


@router.put(
    "/admin/{resource_type}/{resource_id}",
    response_model=SEOMetadataResponse,
    include_in_schema=False,
    dependencies=[_require_seo_write],
)
async def router_alias_admin_upsert_seo_metadata(
    resource_type: str,
    resource_id: uuid.UUID,
    data: SEOMetadataCreate,
    db: AsyncSession = Depends(get_db),
) -> SEOMetadataResponse:
    return await admin_upsert_seo_metadata(
        resource_type=resource_type,
        resource_id=resource_id,
        data=data,
        db=db,
    )
