"""REST API routes for the Multi-Vendor / Marketplace module.

Provides public storefront endpoints, seller self-service actions (registration, earnings),
and back-office administration endpoints for seller verification and settlements.
"""

from __future__ import annotations

import math
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.exceptions.handlers import NotFoundError
from app.core.security.dependencies import RequirePermissions, get_current_user_id
from app.modules.vendors.application.vendor_service import (
    VendorService,
    admin_verify_vendor,
    calculate_vendor_earnings,
    create_settlement,
    get_vendor,
    get_vendor_by_slug,
    get_vendor_by_user_id,
    list_vendor_settlements,
    list_vendors,
    register_vendor,
    update_vendor,
)
from app.modules.vendors.schemas.vendor import (
    VendorAdminUpdateRequest,
    VendorEarningsResponse,
    VendorListResponse,
    VendorRegisterRequest,
    VendorResponse,
    VendorSettlementCreate,
    VendorSettlementListResponse,
    VendorSettlementResponse,
    VendorUpdateRequest,
    VendorVerifyRequest,
)

# Public / Seller router mounted at /api/v1/vendors
router = APIRouter()

# Admin router mounted at /api/v1/admin/vendors
admin_router = APIRouter(
    prefix="/admin/vendors",
    tags=["admin-vendors"],
)

_require_vendor_read = Depends(RequirePermissions("vendors:read", "admin:access"))
_require_vendor_write = Depends(RequirePermissions("vendors:write", "admin:access"))


# ============================================================================
# Seller / Public Endpoints (on router)
# ============================================================================


@router.post(
    "/register",
    response_model=VendorResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register as a vendor / seller",
    description="Submit vendor profile application. An authenticated user can have one vendor store.",
)
async def api_register_vendor(
    data: VendorRegisterRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> VendorResponse:
    """Register the authenticated user as a marketplace vendor."""
    vendor = await register_vendor(db=db, user_id=user_id, data=data)
    return VendorResponse.model_validate(vendor)


@router.get(
    "",
    response_model=VendorListResponse,
    summary="List verified vendors",
    description="Public list of active and verified marketplace sellers.",
)
async def api_list_vendors(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: AsyncSession = Depends(get_db),
) -> VendorListResponse:
    """Retrieve public paginated list of active, verified vendors."""
    vendors, total = await list_vendors(
        db=db,
        is_active=True,
        is_verified=True,
        page=page,
        page_size=page_size,
    )
    total_pages = math.ceil(total / page_size) if total > 0 else 0
    return VendorListResponse(
        items=[VendorResponse.model_validate(v) for v in vendors],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get(
    "/me",
    response_model=VendorEarningsResponse,
    summary="Vendor self-service: sales and earnings",
    description="Retrieve financial metrics, gross sales, platform commissions, and pending settlements for the current vendor.",
)
async def api_get_vendor_me(
    period_start: Optional[datetime] = Query(None, description="Start date for earnings window"),
    period_end: Optional[datetime] = Query(None, description="End date for earnings window"),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> VendorEarningsResponse:
    """View sales metrics and balance for authenticated seller."""
    vendor = await get_vendor_by_user_id(db, user_id)
    if vendor is None:
        raise NotFoundError(
            resource="Vendor",
            detail="Authenticated user does not have a registered vendor profile",
        )

    earnings = await calculate_vendor_earnings(
        db=db,
        vendor_id=vendor.id,
        period_start=period_start,
        period_end=period_end,
    )
    return VendorEarningsResponse.model_validate(earnings)


@router.get(
    "/{slug}",
    response_model=VendorResponse,
    summary="Vendor storefront profile",
    description="Retrieve public profile of a vendor by store slug.",
)
async def api_get_vendor_by_slug(
    slug: str,
    db: AsyncSession = Depends(get_db),
) -> VendorResponse:
    """Public storefront profile lookup."""
    vendor = await get_vendor_by_slug(db=db, slug=slug)
    return VendorResponse.model_validate(vendor)


@router.patch(
    "/me/profile",
    response_model=VendorResponse,
    summary="Update own vendor profile",
    description="Update seller contact info, description, logo, and banner.",
)
async def api_update_vendor_me(
    data: VendorUpdateRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> VendorResponse:
    """Seller self-updates their storefront details."""
    vendor = await get_vendor_by_user_id(db, user_id)
    if vendor is None:
        raise NotFoundError(
            resource="Vendor",
            detail="Authenticated user does not have a registered vendor profile",
        )
    updated = await update_vendor(db=db, vendor_id=vendor.id, data=data)
    return VendorResponse.model_validate(updated)


# ============================================================================
# Admin Endpoints (on admin_router)
# ============================================================================


@admin_router.get(
    "",
    response_model=VendorListResponse,
    dependencies=[_require_vendor_read],
    summary="Admin list vendors",
    description="List all vendors with optional filtering by active and verified flags.",
)
async def admin_list_vendors(
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    is_verified: Optional[bool] = Query(None, description="Filter by verification status"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: AsyncSession = Depends(get_db),
) -> VendorListResponse:
    """Admin vendor listing with full status filters."""
    vendors, total = await list_vendors(
        db=db,
        is_active=is_active,
        is_verified=is_verified,
        page=page,
        page_size=page_size,
    )
    total_pages = math.ceil(total / page_size) if total > 0 else 0
    return VendorListResponse(
        items=[VendorResponse.model_validate(v) for v in vendors],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@admin_router.get(
    "/{id}",
    response_model=VendorResponse,
    dependencies=[_require_vendor_read],
    summary="Admin get vendor details",
    description="Retrieve vendor by ID including verification and commission rates.",
)
async def admin_get_vendor(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> VendorResponse:
    """Admin inspect specific vendor."""
    vendor = await get_vendor(db=db, vendor_id=id)
    return VendorResponse.model_validate(vendor)


@admin_router.patch(
    "/{id}/verify",
    response_model=VendorResponse,
    dependencies=[_require_vendor_write],
    summary="Admin verify / approve vendor",
    description="Approve or revoke vendor verification status.",
)
async def admin_patch_verify_vendor(
    id: uuid.UUID,
    payload: Optional[VendorVerifyRequest] = None,
    verified: bool = Query(True, description="Verification status if payload body is not provided"),
    db: AsyncSession = Depends(get_db),
) -> VendorResponse:
    """Approve or reject vendor verification."""
    is_verified = payload.verified if payload is not None else verified
    vendor = await admin_verify_vendor(db=db, vendor_id=id, verified=is_verified)
    return VendorResponse.model_validate(vendor)


@admin_router.patch(
    "/{id}",
    response_model=VendorResponse,
    dependencies=[_require_vendor_write],
    summary="Admin update vendor attributes",
    description="Modify vendor commission rate, status, rating, or storefront metadata.",
)
async def admin_update_vendor_details(
    id: uuid.UUID,
    data: VendorAdminUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> VendorResponse:
    """Update vendor configuration."""
    vendor = await update_vendor(db=db, vendor_id=id, data=data)
    return VendorResponse.model_validate(vendor)


@admin_router.get(
    "/{id}/earnings",
    response_model=VendorEarningsResponse,
    dependencies=[_require_vendor_read],
    summary="Admin view vendor earnings",
    description="Financial breakdown for a specific vendor across an optional timeframe.",
)
async def admin_vendor_earnings(
    id: uuid.UUID,
    period_start: Optional[datetime] = Query(None, description="Start date"),
    period_end: Optional[datetime] = Query(None, description="End date"),
    db: AsyncSession = Depends(get_db),
) -> VendorEarningsResponse:
    """Admin inspection of vendor sales and earnings."""
    earnings = await calculate_vendor_earnings(
        db=db,
        vendor_id=id,
        period_start=period_start,
        period_end=period_end,
    )
    return VendorEarningsResponse.model_validate(earnings)


@admin_router.get(
    "/{id}/settlements",
    response_model=VendorSettlementListResponse,
    dependencies=[_require_vendor_read],
    summary="Admin list vendor settlements",
    description="List all payout / settlement records for a vendor.",
)
async def admin_get_vendor_settlements(
    id: uuid.UUID,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: AsyncSession = Depends(get_db),
) -> VendorSettlementListResponse:
    """List settlements for a specific vendor."""
    # Ensure vendor exists
    await get_vendor(db=db, vendor_id=id)

    settlements, total = await list_vendor_settlements(
        db=db,
        vendor_id=id,
        page=page,
        page_size=page_size,
    )
    total_pages = math.ceil(total / page_size) if total > 0 else 0
    return VendorSettlementListResponse(
        items=[VendorSettlementResponse.model_validate(s) for s in settlements],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@admin_router.post(
    "/{id}/settlements",
    response_model=VendorSettlementResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[_require_vendor_write],
    summary="Admin create vendor settlement",
    description="Generate a payout settlement record for a vendor.",
)
async def admin_create_vendor_settlement(
    id: uuid.UUID,
    data: VendorSettlementCreate,
    db: AsyncSession = Depends(get_db),
) -> VendorSettlementResponse:
    """Create settlement payout record for a vendor."""
    settlement = await create_settlement(
        db=db,
        vendor_id=id,
        amount=data.amount,
        period_start=data.period_start,
        period_end=data.period_end,
        payment_reference=data.payment_reference,
    )
    return VendorSettlementResponse.model_validate(settlement)
