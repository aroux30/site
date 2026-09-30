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
    UniqueConstraint,
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
    #: Cancelled before carrier pickup. Terminal — a cancelled shipment is
    #: never revived; a new one is created for a re-dispatch.
    CANCELLED = "cancelled"


class DeliveryType(str, enum.Enum):
    """How the customer receives the parcel.

    ``CASH_ON_DELIVERY`` is a distinct *payment* mode, not just a handling
    option: the courier collects the order total at the door, so the order
    must not be marked paid at checkout and the shipment carries the amount
    to collect. Iranian carriers (Tipax/Post) support it on most routes.
    """

    HOME = "home"
    PICKUP_POINT = "pickup_point"
    CASH_ON_DELIVERY = "cash_on_delivery"


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

    # ── Delivery mode, cash-on-delivery, pickup point (ERP feature #32) ──
    delivery_type: Mapped[DeliveryType] = mapped_column(
        Enum(DeliveryType, name="delivery_type_enum", native_enum=False),
        default=DeliveryType.HOME,
        nullable=False,
        # Must be the enum member NAME, not the lowercase value: this column
        # stores names (Enum(...) without values_callable), so a server default
        # of 'home' would write a value the ORM cannot map back to
        # DeliveryType.HOME on read. Any row created outside the ORM (raw SQL,
        # a bulk insert, a restore) would then fail to load.
        server_default="HOME",
    )
    #: Amount the courier must collect at the door, integer Rials. Non-zero
    #: only for CASH_ON_DELIVERY shipments; set at creation from the order's
    #: unpaid balance and never edited afterwards (the courier holds a copy).
    cod_amount_rial: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    #: Set when the courier has remitted the collected cash to us.
    cod_collected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    pickup_point_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pickup_points.id", ondelete="SET NULL"),
        nullable=True,
    )
    #: Who cancelled and why — a cancelled shipment is an operational event
    #: support needs to explain, not just a status flip.
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cancelled_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    #: Waybill / label URL from the carrier, when it provides one.
    label_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Relationships
    method: Mapped["ShippingMethod"] = relationship("ShippingMethod", back_populates="shipments")
    items: Mapped[list["ShipmentItem"]] = relationship(
        "ShipmentItem", back_populates="shipment", lazy="select"
    )
    tracking_events: Mapped[list["ShipmentTrackingEvent"]] = relationship(
        "ShipmentTrackingEvent",
        back_populates="shipment",
        cascade="all, delete-orphan",
        order_by="ShipmentTrackingEvent.created_at.asc()",
        lazy="select",
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


class ShipmentTrackingEvent(BaseModel):
    """Audit timeline event for shipment tracking lifecycle (GAP-18)."""

    __tablename__ = "shipment_tracking_events"
    __table_args__ = (
        Index("ix_tracking_events_shipment_id", "shipment_id"),
        Index("ix_tracking_events_status", "status"),
        Index("ix_tracking_events_created_at", "created_at"),
    )

    shipment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("shipments.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[ShipmentStatus] = mapped_column(
        Enum(ShipmentStatus, name="shipment_status_enum", native_enum=False),
        nullable=False,
    )
    location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    shipment: Mapped["Shipment"] = relationship("Shipment", back_populates="tracking_events")

    def __repr__(self) -> str:
        return (
            f"<ShipmentTrackingEvent(id={self.id}, shipment_id={self.shipment_id}, "
            f"status={self.status})>"
        )


class PickupPoint(BaseModel):
    """A carrier pickup location a customer can collect from.

    Iranian carriers (Tipax, Post) publish networks of agents/shops; this
    table caches the ones we offer per city so checkout can list them without
    a carrier round-trip per page view. ``external_id`` is the carrier's own
    identifier, used when creating the shipment.
    """

    __tablename__ = "pickup_points"
    __table_args__ = (
        Index("ix_pickup_points_city", "city"),
        Index("ix_pickup_points_provider", "provider"),
        UniqueConstraint(
            "provider",
            "external_id",
            name="uq_pickup_points_provider_external",
        ),
    )

    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    #: Carrier-side identifier (agent code / branch number).
    external_id: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    province: Mapped[str | None] = mapped_column(String(100), nullable=True)
    address: Mapped[str] = mapped_column(Text, nullable=False)
    postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False, server_default="true"
    )

    def __repr__(self) -> str:
        return f"<PickupPoint(id={self.id}, provider={self.provider}, name={self.name!r})>"
