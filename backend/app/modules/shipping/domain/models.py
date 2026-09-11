"""Shipping and delivery domain models."""

import enum
import uuid
from datetime import datetime

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

# ---- Enums ----


class ShipmentStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    IN_TRANSIT = "in_transit"
    DELIVERED = "delivered"
    RETURNED = "returned"


# ---- Models ----


class ShippingMethod(BaseModel):
    """Available shipping/delivery methods."""

    __tablename__ = "shipping_methods"
    __table_args__ = (
        Index("ix_shipping_methods_slug", "slug"),
        Index("ix_shipping_methods_is_active", "is_active"),
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(220), unique=True, nullable=False)
    provider: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    estimated_days_min: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    estimated_days_max: Mapped[int] = mapped_column(Integer, default=3, nullable=False)

    # Relationships
    rates: Mapped[list["ShippingRate"]] = relationship(
        "ShippingRate", back_populates="method", lazy="select"
    )
    shipments: Mapped[list["Shipment"]] = relationship(
        "Shipment", back_populates="method", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<ShippingMethod(id={self.id}, slug={self.slug})>"


class ShippingRate(BaseModel):
    """Rate rules per shipping method, province, and weight/price thresholds."""

    __tablename__ = "shipping_rates"
    __table_args__ = (
        Index("ix_shipping_rates_method_id", "method_id"),
        Index("ix_shipping_rates_province", "province"),
    )

    method_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("shipping_methods.id", ondelete="CASCADE"),
        nullable=False,
    )
    province: Mapped[str | None] = mapped_column(String(100), nullable=True)
    min_weight: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_weight: Mapped[float | None] = mapped_column(Float, nullable=True)
    min_order_amount: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    price: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # Relationships
    method: Mapped["ShippingMethod"] = relationship("ShippingMethod", back_populates="rates")

    def __repr__(self) -> str:
        return f"<ShippingRate(id={self.id}, method_id={self.method_id}, price={self.price})>"


class Shipment(BaseModel):
    """Physical shipment tracking for an order."""

    __tablename__ = "shipments"
    __table_args__ = (
        Index("ix_shipments_order_id", "order_id"),
        Index("ix_shipments_tracking_code", "tracking_code"),
        Index("ix_shipments_status", "status"),
    )

    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
    )
    method_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("shipping_methods.id", ondelete="RESTRICT"),
        nullable=False,
    )
    tracking_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[ShipmentStatus] = mapped_column(
        Enum(ShipmentStatus, name="shipment_status_enum", native_enum=False),
        default=ShipmentStatus.PENDING,
        nullable=False,
    )
    shipped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    method: Mapped["ShippingMethod"] = relationship("ShippingMethod", back_populates="shipments")
    items: Mapped[list["ShipmentItem"]] = relationship(
        "ShipmentItem", back_populates="shipment", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<Shipment(id={self.id}, order_id={self.order_id}, status={self.status})>"


class ShipmentItem(BaseModel):
    """Individual items in a shipment (supports partial shipments)."""

    __tablename__ = "shipment_items"
    __table_args__ = (
        Index("ix_shipment_items_shipment_id", "shipment_id"),
        Index("ix_shipment_items_order_item_id", "order_item_id"),
    )

    shipment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("shipments.id", ondelete="CASCADE"),
        nullable=False,
    )
    order_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("order_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)

    # Relationships
    shipment: Mapped["Shipment"] = relationship("Shipment", back_populates="items")

    def __repr__(self) -> str:
        return f"<ShipmentItem(id={self.id}, shipment_id={self.shipment_id})>"
