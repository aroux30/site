"""Domain models for the multi-vendor marketplace module.

Re-exports Vendor, VendorSettlement, and SettlementStatus from the catalog domain
to keep table metadata unified while providing clean module encapsulation.
"""

from __future__ import annotations

from app.modules.catalog.domain.models import (
    SettlementStatus,
    Vendor,
    VendorSettlement,
)

__all__ = [
    "SettlementStatus",
    "Vendor",
    "VendorSettlement",
]
