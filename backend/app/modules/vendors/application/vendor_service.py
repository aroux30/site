"""Vendor application service for the multi-vendor marketplace module.

Contains business logic for vendor registration, verification, storefront management,
financial calculations (commissions, gross/net sales, settlements), and admin operations.
"""

from __future__ import annotations

import math
import re
import unicodedata
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import structlog
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions.handlers import ConflictError, NotFoundError, ValidationError
from app.modules.catalog.domain.models import (
    Product,
    ProductVariant,
    SettlementStatus,
    Vendor,
    VendorSettlement,
)
from app.modules.orders.domain.models import Order, OrderItem, OrderStatus
from app.modules.vendors.schemas.vendor import (
    VendorAdminUpdateRequest,
    VendorRegisterRequest,
    VendorUpdateRequest,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


# ── Slug Helper ────────────────────────────────────────────────────────────

_PERSIAN_TO_LATIN: dict[str, str] = {
    "آ": "a", "ا": "a", "ب": "b", "پ": "p", "ت": "t", "ث": "s",
    "ج": "j", "چ": "ch", "ح": "h", "خ": "kh", "د": "d", "ذ": "z",
    "ر": "r", "ز": "z", "ژ": "zh", "س": "s", "ش": "sh", "ص": "s",
    "ض": "z", "ط": "t", "ظ": "z", "ع": "a", "غ": "gh", "ف": "f",
    "ق": "gh", "ک": "k", "گ": "g", "ل": "l", "م": "m", "ن": "n",
    "و": "v", "ه": "h", "ی": "y", "ئ": "y", "ي": "y", "ك": "k",
    "ة": "h", "إ": "e", "أ": "a", "ؤ": "v",
    "۰": "0", "۱": "1", "۲": "2", "۳": "3", "۴": "4",
    "۵": "5", "۶": "6", "۷": "7", "۸": "8", "۹": "9",
    "٠": "0", "١": "1", "٢": "2", "٣": "3", "٤": "4",
    "٥": "5", "٦": "6", "٧": "7", "٨": "8", "٩": "9",
}

_DIACRITICS_RE = re.compile(
    r"[\u064B-\u065F\u0670\u06D6-\u06ED\u200B-\u200F\u202A-\u202E\uFEFF]"
)


def generate_vendor_slug(text: str) -> str:
    """Generate a clean URL slug from text supporting Persian and English characters."""
    if not text:
        return f"vendor-{uuid.uuid4().hex[:8]}"

    text = _DIACRITICS_RE.sub("", text)
    text = text.replace("\u200c", "-")

    transliterated = [_PERSIAN_TO_LATIN.get(ch, ch) for ch in text]
    text = "".join(transliterated)

    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")

    return text or f"vendor-{uuid.uuid4().hex[:8]}"


# ── Functional Service API ─────────────────────────────────────────────────


async def register_vendor(
    db: AsyncSession,
    user_id: uuid.UUID,
    data: VendorRegisterRequest,
) -> Vendor:
    """Register a new vendor application for the given user."""
    # Ensure user has no existing vendor profile
    existing_user_stmt = select(Vendor).where(Vendor.user_id == user_id)
    existing_user = (await db.execute(existing_user_stmt)).scalar_one_or_none()
    if existing_user is not None:
        raise ConflictError(detail="User is already registered as a vendor")

    # Generate and validate unique slug
    if data.slug:
        slug = re.sub(r"[^a-z0-9\-]+", "-", data.slug.strip().lower()).strip("-")
        if not slug:
            slug = generate_vendor_slug(data.store_name)
    else:
        slug = generate_vendor_slug(data.store_name)

    # Check slug collision
    existing_slug_stmt = select(Vendor).where(Vendor.slug == slug)
    if (await db.execute(existing_slug_stmt)).scalar_one_or_none() is not None:
        if data.slug:
            raise ConflictError(detail=f"Store slug '{slug}' is already in use")
        slug = f"{slug}-{uuid.uuid4().hex[:6]}"

    vendor = Vendor(
        id=uuid.uuid4(),
        user_id=user_id,
        store_name=data.store_name,
        slug=slug,
        logo_url=data.logo_url,
        banner_url=data.banner_url,
        description=data.description,
        commission_rate=1000,  # 10% default
        is_verified=False,
        is_active=True,
        national_id=data.national_id,
        iban_number=data.iban_number,
        contact_phone=data.contact_phone,
        rating=5.0,
        total_sales_count=0,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    db.add(vendor)
    await db.commit()
    await db.refresh(vendor)

    await logger.ainfo("vendor_registered", vendor_id=str(vendor.id), store_name=vendor.store_name)
    return vendor


async def get_vendor(db: AsyncSession, vendor_id: uuid.UUID) -> Vendor:
    """Retrieve vendor by primary key."""
    stmt = select(Vendor).where(Vendor.id == vendor_id)
    vendor = (await db.execute(stmt)).scalar_one_or_none()
    if vendor is None:
        raise NotFoundError(resource="Vendor", detail=f"Vendor '{vendor_id}' not found")
    return vendor


async def get_vendor_by_slug(db: AsyncSession, slug: str) -> Vendor:
    """Retrieve vendor by unique URL slug."""
    stmt = select(Vendor).where(Vendor.slug == slug)
    vendor = (await db.execute(stmt)).scalar_one_or_none()
    if vendor is None:
        raise NotFoundError(resource="Vendor", detail=f"Vendor with slug '{slug}' not found")
    return vendor


async def get_vendor_by_user_id(db: AsyncSession, user_id: uuid.UUID) -> Optional[Vendor]:
    """Retrieve vendor profile belonging to a user."""
    stmt = select(Vendor).where(Vendor.user_id == user_id)
    return (await db.execute(stmt)).scalar_one_or_none()


async def list_vendors(
    db: AsyncSession,
    is_active: Optional[bool] = True,
    is_verified: Optional[bool] = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Vendor], int]:
    """List vendors with filtering and pagination."""
    if page < 1:
        page = 1
    if page_size < 1:
        page_size = 20
    if page_size > 100:
        page_size = 100

    query = select(Vendor)
    count_query = select(func.count(Vendor.id))

    if is_active is not None:
        query = query.where(Vendor.is_active == is_active)
        count_query = count_query.where(Vendor.is_active == is_active)

    if is_verified is not None:
        query = query.where(Vendor.is_verified == is_verified)
        count_query = count_query.where(Vendor.is_verified == is_verified)

    total = (await db.execute(count_query)).scalar_one()

    offset = (page - 1) * page_size
    query = query.order_by(Vendor.created_at.desc()).offset(offset).limit(page_size)
    result = await db.execute(query)
    vendors = list(result.scalars().all())

    return vendors, total


async def admin_verify_vendor(
    db: AsyncSession,
    vendor_id: uuid.UUID,
    verified: bool = True,
) -> Vendor:
    """Admin action to approve or revoke vendor verification."""
    vendor = await get_vendor(db, vendor_id)
    vendor.is_verified = verified
    if verified:
        vendor.is_active = True
    await db.commit()
    await db.refresh(vendor)

    await logger.ainfo("vendor_verification_updated", vendor_id=str(vendor.id), verified=verified)
    return vendor


async def update_vendor(
    db: AsyncSession,
    vendor_id: uuid.UUID,
    data: VendorUpdateRequest | VendorAdminUpdateRequest,
) -> Vendor:
    """Update vendor information."""
    vendor = await get_vendor(db, vendor_id)

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(vendor, field, value)

    await db.commit()
    await db.refresh(vendor)
    return vendor


async def calculate_vendor_earnings(
    db: AsyncSession,
    vendor_id: uuid.UUID,
    period_start: Optional[datetime] = None,
    period_end: Optional[datetime] = None,
) -> dict[str, Any]:
    """Calculate gross sales, platform commission, net earnings, and settlement status."""
    vendor = await get_vendor(db, vendor_id)

    # Exclude canceled and refunded orders from revenue calculations
    excluded_statuses = [
        OrderStatus.CANCELED,
        OrderStatus.REFUNDED,
    ]

    # Query items linked to vendor via Product or ProductVariant
    query = (
        select(OrderItem)
        .join(Order, OrderItem.order_id == Order.id)
        .join(ProductVariant, OrderItem.variant_id == ProductVariant.id)
        .join(Product, ProductVariant.product_id == Product.id)
        .where(
            or_(
                ProductVariant.vendor_id == vendor_id,
                Product.vendor_id == vendor_id,
            ),
            Order.status.notin_(excluded_statuses),
        )
    )

    if period_start is not None:
        query = query.where(Order.created_at >= period_start)
    if period_end is not None:
        query = query.where(Order.created_at <= period_end)

    result = await db.execute(query)
    items = list(result.scalars().all())

    total_sales = sum(item.total_price for item in items)
    total_items = sum(item.quantity for item in items)
    distinct_orders = len({item.order_id for item in items})

    # Commission rate basis points (e.g. 1000 = 10%)
    commission_rate = vendor.commission_rate
    commission_amount = (total_sales * commission_rate) // 10000
    net_earnings = total_sales - commission_amount

    # Sum of settlements marked paid or approved
    settlement_query = select(
        func.coalesce(func.sum(VendorSettlement.amount), 0)
    ).where(
        VendorSettlement.vendor_id == vendor_id,
        VendorSettlement.status.in_([SettlementStatus.PAID, SettlementStatus.APPROVED]),
    )
    settled_amount = (await db.execute(settlement_query)).scalar_one()
    pending_settlement = max(0, net_earnings - settled_amount)

    return {
        "vendor_id": vendor.id,
        "store_name": vendor.store_name,
        "period_start": period_start,
        "period_end": period_end,
        "total_sales": total_sales,
        "total_orders": distinct_orders,
        "total_items": total_items,
        "commission_rate": commission_rate,
        "commission_amount": commission_amount,
        "net_earnings": net_earnings,
        "settled_amount": settled_amount,
        "pending_settlement": pending_settlement,
    }


async def create_settlement(
    db: AsyncSession,
    vendor_id: uuid.UUID,
    amount: int,
    period_start: Optional[datetime] = None,
    period_end: Optional[datetime] = None,
    payment_reference: Optional[str] = None,
) -> VendorSettlement:
    """Generate a payout settlement record for a vendor."""
    vendor = await get_vendor(db, vendor_id)
    if amount <= 0:
        raise ValidationError(detail="Settlement amount must be greater than zero")

    settlement = VendorSettlement(
        id=uuid.uuid4(),
        vendor_id=vendor.id,
        amount=amount,
        period_start=period_start,
        period_end=period_end,
        status=SettlementStatus.PENDING,
        payment_reference=payment_reference,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(settlement)
    await db.commit()
    await db.refresh(settlement)

    await logger.ainfo(
        "vendor_settlement_created",
        settlement_id=str(settlement.id),
        vendor_id=str(vendor.id),
        amount=amount,
    )
    return settlement


async def list_vendor_settlements(
    db: AsyncSession,
    vendor_id: Optional[uuid.UUID] = None,
    status: Optional[SettlementStatus] = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[VendorSettlement], int]:
    """Retrieve settlements with pagination and optional filters."""
    if page < 1:
        page = 1
    if page_size < 1:
        page_size = 20
    if page_size > 100:
        page_size = 100

    query = select(VendorSettlement)
    count_query = select(func.count(VendorSettlement.id))

    if vendor_id is not None:
        query = query.where(VendorSettlement.vendor_id == vendor_id)
        count_query = count_query.where(VendorSettlement.vendor_id == vendor_id)

    if status is not None:
        query = query.where(VendorSettlement.status == status)
        count_query = count_query.where(VendorSettlement.status == status)

    total = (await db.execute(count_query)).scalar_one()

    offset = (page - 1) * page_size
    query = query.order_by(VendorSettlement.created_at.desc()).offset(offset).limit(page_size)
    result = await db.execute(query)
    settlements = list(result.scalars().all())

    return settlements, total


async def update_settlement_status(
    db: AsyncSession,
    settlement_id: uuid.UUID,
    status: SettlementStatus,
    payment_reference: Optional[str] = None,
) -> VendorSettlement:
    """Update status of a settlement (e.g. approve or mark as paid)."""
    stmt = select(VendorSettlement).where(VendorSettlement.id == settlement_id)
    settlement = (await db.execute(stmt)).scalar_one_or_none()
    if settlement is None:
        raise NotFoundError(resource="VendorSettlement", detail=f"Settlement '{settlement_id}' not found")

    settlement.status = status
    if payment_reference is not None:
        settlement.payment_reference = payment_reference
    if status == SettlementStatus.PAID and settlement.paid_at is None:
        settlement.paid_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(settlement)
    return settlement


# ── VendorService Object-Oriented Wrapper ─────────────────────────────────


class VendorService:
    """Application service wrapper for vendor operations."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def register_vendor(self, user_id: uuid.UUID, data: VendorRegisterRequest) -> Vendor:
        return await register_vendor(self.db, user_id, data)

    async def get_vendor(self, vendor_id: uuid.UUID) -> Vendor:
        return await get_vendor(self.db, vendor_id)

    async def get_vendor_by_slug(self, slug: str) -> Vendor:
        return await get_vendor_by_slug(self.db, slug)

    async def get_vendor_by_user_id(self, user_id: uuid.UUID) -> Optional[Vendor]:
        return await get_vendor_by_user_id(self.db, user_id)

    async def list_vendors(
        self,
        is_active: Optional[bool] = True,
        is_verified: Optional[bool] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Vendor], int]:
        return await list_vendors(
            self.db,
            is_active=is_active,
            is_verified=is_verified,
            page=page,
            page_size=page_size,
        )

    async def admin_verify_vendor(self, vendor_id: uuid.UUID, verified: bool = True) -> Vendor:
        return await admin_verify_vendor(self.db, vendor_id, verified=verified)

    async def update_vendor(
        self,
        vendor_id: uuid.UUID,
        data: VendorUpdateRequest | VendorAdminUpdateRequest,
    ) -> Vendor:
        return await update_vendor(self.db, vendor_id, data)

    async def calculate_vendor_earnings(
        self,
        vendor_id: uuid.UUID,
        period_start: Optional[datetime] = None,
        period_end: Optional[datetime] = None,
    ) -> dict[str, Any]:
        return await calculate_vendor_earnings(
            self.db,
            vendor_id,
            period_start=period_start,
            period_end=period_end,
        )

    async def create_settlement(
        self,
        vendor_id: uuid.UUID,
        amount: int,
        period_start: Optional[datetime] = None,
        period_end: Optional[datetime] = None,
        payment_reference: Optional[str] = None,
    ) -> VendorSettlement:
        return await create_settlement(
            self.db,
            vendor_id,
            amount,
            period_start=period_start,
            period_end=period_end,
            payment_reference=payment_reference,
        )

    async def list_vendor_settlements(
        self,
        vendor_id: Optional[uuid.UUID] = None,
        status: Optional[SettlementStatus] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[VendorSettlement], int]:
        return await list_vendor_settlements(
            self.db,
            vendor_id=vendor_id,
            status=status,
            page=page,
            page_size=page_size,
        )

    async def update_settlement_status(
        self,
        settlement_id: uuid.UUID,
        status: SettlementStatus,
        payment_reference: Optional[str] = None,
    ) -> VendorSettlement:
        return await update_settlement_status(
            self.db,
            settlement_id,
            status=status,
            payment_reference=payment_reference,
        )
