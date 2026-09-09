"""Multi-Vendor / Marketplace module for independent sellers."""

from app.modules.vendors.application import (
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
)
from app.modules.vendors.domain.models import (
    SettlementStatus,
    Vendor,
    VendorSettlement,
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

__all__ = [
    "SettlementStatus",
    "Vendor",
    "VendorAdminUpdateRequest",
    "VendorEarningsResponse",
    "VendorListResponse",
    "VendorRegisterRequest",
    "VendorResponse",
    "VendorService",
    "VendorSettlement",
    "VendorSettlementCreate",
    "VendorSettlementListResponse",
    "VendorSettlementResponse",
    "VendorUpdateRequest",
    "VendorVerifyRequest",
    "admin_verify_vendor",
    "calculate_vendor_earnings",
    "create_settlement",
    "get_vendor",
    "get_vendor_by_slug",
    "get_vendor_by_user_id",
    "list_vendor_settlements",
    "list_vendors",
    "register_vendor",
]
