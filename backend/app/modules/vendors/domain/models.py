"""Domain models for the multi-vendor marketplace module."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.base import BaseModel

if TYPE_CHECKING:
    from app.modules.catalog.domain.models import Product


class SettlementStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    PAID = "paid"
    REJECTED = "rejected"


class Vendor(BaseModel):
    """Marketplace vendor / independent seller entity."""

    __tablename__ = "vendors"
    __table_args__ = (
        Index("ix_vendors_user_id", "user_id"),
        Index("ix_vendors_slug", "slug"),
        Index("ix_vendors_is_active", "is_active"),
        Index("ix_vendors_is_verified", "is_verified"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    store_name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(250), unique=True, nullable=False)
    logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    banner_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    commission_rate: Mapped[int] = mapped_column(Integer, default=1000, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    national_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    iban_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    rating: Mapped[float] = mapped_column(Float, default=5.0, nullable=False)
    total_sales_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Relationships
    products: Mapped[list[Product]] = relationship(
        "Product", back_populates="vendor", lazy="select"
    )
    settlements: Mapped[list[VendorSettlement]] = relationship(
        "VendorSettlement", back_populates="vendor", cascade="all, delete-orphan", lazy="select"
    )

    def __init__(self, **kw: Any) -> None:
        kw.setdefault("commission_rate", 1000)
        kw.setdefault("is_verified", False)
        kw.setdefault("is_active", True)
        kw.setdefault("rating", 5.0)
        kw.setdefault("total_sales_count", 0)
        super().__init__(**kw)

    def __repr__(self) -> str:
        return f"<Vendor(id={self.id}, store_name={self.store_name}, slug={self.slug})>"


class VendorSettlement(BaseModel):
    """Vendor payout / settlement record."""

    __tablename__ = "vendor_settlements"
    __table_args__ = (
        Index("ix_vendor_settlements_vendor_id", "vendor_id"),
        Index("ix_vendor_settlements_status", "status"),
        Index("ix_vendor_settlements_created_at", "created_at"),
    )

    vendor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("vendors.id", ondelete="CASCADE"),
        nullable=False,
    )
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[SettlementStatus] = mapped_column(
        Enum(SettlementStatus, name="settlement_status_enum", native_enum=False),
        default=SettlementStatus.PENDING,
        nullable=False,
    )
    payment_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    vendor: Mapped[Vendor] = relationship("Vendor", back_populates="settlements")

    def __init__(self, **kw: Any) -> None:
        kw.setdefault("status", SettlementStatus.PENDING)
        super().__init__(**kw)

    def __repr__(self) -> str:
        return f"<VendorSettlement(id={self.id}, vendor_id={self.vendor_id}, amount={self.amount}, status={self.status})>"


__all__ = [
    "SettlementStatus",
    "Vendor",
    "VendorSettlement",
]
