"""Inventory management domain models."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
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


class ReservationStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    RELEASED = "released"
    EXPIRED = "expired"


class TransactionType(str, enum.Enum):
    RECEIVED = "received"
    SOLD = "sold"
    RETURNED = "returned"
    ADJUSTED = "adjusted"
    DAMAGED = "damaged"
    RESERVED = "reserved"
    RELEASED = "released"


# ---- Models ----


class InventoryItem(BaseModel):
    """Tracks stock levels for each product variant."""

    __tablename__ = "inventory_items"
    __table_args__ = (
        Index("ix_inventory_items_variant_id", "variant_id"),
        CheckConstraint("available >= 0", name="ck_inventory_available_non_negative"),
        CheckConstraint("reserved >= 0", name="ck_inventory_reserved_non_negative"),
        CheckConstraint("committed >= 0", name="ck_inventory_committed_non_negative"),
    )

    variant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("product_variants.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    available: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reserved: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    committed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    damaged: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    incoming: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    low_stock_threshold: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    backorder_allowed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    track_inventory: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    reservations: Mapped[list["InventoryReservation"]] = relationship(
        "InventoryReservation", back_populates="inventory_item", lazy="select"
    )
    transactions: Mapped[list["InventoryTransaction"]] = relationship(
        "InventoryTransaction", back_populates="inventory_item", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<InventoryItem(id={self.id}, variant_id={self.variant_id}, available={self.available})>"  # noqa: E501


class InventoryReservation(BaseModel):
    """Temporary stock reservations for carts and orders."""

    __tablename__ = "inventory_reservations"
    __table_args__ = (
        Index("ix_inventory_reservations_inventory_item_id", "inventory_item_id"),
        Index("ix_inventory_reservations_order_id", "order_id"),
        Index("ix_inventory_reservations_cart_id", "cart_id"),
        Index("ix_inventory_reservations_status", "status"),
        Index("ix_inventory_reservations_expires_at", "expires_at"),
    )

    inventory_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("inventory_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    order_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="SET NULL"),
        nullable=True,
    )
    cart_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("carts.id", ondelete="SET NULL"),
        nullable=True,
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[ReservationStatus] = mapped_column(
        Enum(ReservationStatus, name="reservation_status_enum", native_enum=False),
        default=ReservationStatus.PENDING,
        nullable=False,
    )

    # Relationships
    inventory_item: Mapped["InventoryItem"] = relationship(
        "InventoryItem", back_populates="reservations"
    )

    def __repr__(self) -> str:
        return (
            f"<InventoryReservation(id={self.id}, quantity={self.quantity}, status={self.status})>"
        )


class InventoryTransaction(BaseModel):
    """Audit trail for all inventory movements."""

    __tablename__ = "inventory_transactions"
    __table_args__ = (
        Index("ix_inventory_transactions_inventory_item_id", "inventory_item_id"),
        Index("ix_inventory_transactions_type", "type"),
        Index("ix_inventory_transactions_created_at", "created_at"),
    )

    inventory_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("inventory_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    type: Mapped[TransactionType] = mapped_column(
        Enum(TransactionType, name="inventory_transaction_type_enum", native_enum=False),
        nullable=False,
    )
    reference_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    reference_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    inventory_item: Mapped["InventoryItem"] = relationship(
        "InventoryItem", back_populates="transactions"
    )

    def __repr__(self) -> str:
        return f"<InventoryTransaction(id={self.id}, type={self.type}, quantity={self.quantity})>"
