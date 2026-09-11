"""Discount and coupon domain models."""

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.base import BaseModel

# ---- Enums ----


class DiscountType(str, enum.Enum):
    FIXED = "fixed"
    PERCENTAGE = "percentage"
    FIRST_ORDER = "first_order"


class DiscountScope(str, enum.Enum):
    GLOBAL = "global"
    PRODUCT = "product"
    CATEGORY = "category"
    BRAND = "brand"
    USER = "user"


# ---- Models ----


class Discount(BaseModel):
    """Discount rules defining promotional pricing logic."""

    __tablename__ = "discounts"
    __table_args__ = (
        Index("ix_discounts_type", "type"),
        Index("ix_discounts_scope", "scope"),
        Index("ix_discounts_is_active", "is_active"),
        Index("ix_discounts_starts_at_ends_at", "starts_at", "ends_at"),
        Index("ix_discounts_priority", "priority"),
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    type: Mapped[DiscountType] = mapped_column(
        Enum(DiscountType, name="discount_type_enum", native_enum=False),
        nullable=False,
    )
    value: Mapped[int] = mapped_column(BigInteger, nullable=False)
    min_cart_amount: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    max_discount: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    scope: Mapped[DiscountScope] = mapped_column(
        Enum(DiscountScope, name="discount_scope_enum", native_enum=False),
        default=DiscountScope.GLOBAL,
        nullable=False,
    )
    scope_ids: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_stackable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    usage_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    usage_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Relationships
    coupons: Mapped[list["Coupon"]] = relationship(
        "Coupon", back_populates="discount", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<Discount(id={self.id}, name={self.name}, type={self.type})>"


class Coupon(BaseModel):
    """Redeemable coupon codes tied to discount rules."""

    __tablename__ = "coupons"
    __table_args__ = (
        Index("ix_coupons_code", "code"),
        Index("ix_coupons_discount_id", "discount_id"),
        Index("ix_coupons_is_active", "is_active"),
    )

    discount_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("discounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    usage_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    usage_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Relationships
    discount: Mapped["Discount"] = relationship("Discount", back_populates="coupons")
    redemptions: Mapped[list["CouponRedemption"]] = relationship(
        "CouponRedemption", back_populates="coupon", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<Coupon(id={self.id}, code={self.code})>"


class CouponRedemption(BaseModel):
    """Record of coupon usage per user per order."""

    __tablename__ = "coupon_redemptions"
    __table_args__ = (
        Index("ix_coupon_redemptions_coupon_id", "coupon_id"),
        Index("ix_coupon_redemptions_user_id", "user_id"),
        Index("ix_coupon_redemptions_order_id", "order_id"),
        UniqueConstraint(
            "coupon_id",
            "order_id",
            name="uq_coupon_redemptions_coupon_order",
        ),
    )

    coupon_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("coupons.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
    )
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # Relationships
    coupon: Mapped["Coupon"] = relationship("Coupon", back_populates="redemptions")

    def __repr__(self) -> str:
        return (
            f"<CouponRedemption(id={self.id}, coupon_id={self.coupon_id}, user_id={self.user_id})>"
        )
