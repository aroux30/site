"""Digital goods inventory domain models (Karta roadmap Phase 1/2).

Covers the three Karta delivery types:
- UNIQUE: one-time PIN/serial, consumed on first sale
- SHARED: multi-use account with capacity limit
- FILE: downloadable license/config with time-limited access

Security notes:
- PINs are NEVER stored as plaintext. Only ``pin_ciphertext`` (AES-256-GCM)
  and ``card_hash`` (SHA-256) are persisted.
- ``card_hash`` prevents duplicate imports caused by operator error via unique constraint.
- ``reading_at`` is the legal audit flag proving when a buyer first viewed
  the code (Karta ``reading`` flag).
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import BaseModel


class DigitalDeliveryType(str, enum.Enum):
    UNIQUE = "unique"
    SHARED = "shared"
    FILE = "file"


class DigitalCardStatus(str, enum.Enum):
    AVAILABLE = "available"
    RESERVED = "reserved"
    DELIVERED = "delivered"
    REVOKED = "revoked"
    EXPIRED = "expired"


class DigitalCard(BaseModel):
    """A single digital code / account / file asset in stock."""

    __tablename__ = "digital_cards"
    __table_args__ = (
        UniqueConstraint("card_hash", name="uq_digital_cards_card_hash"),
        Index("ix_digital_cards_product_id", "product_id"),
        Index("ix_digital_cards_status", "status"),
        Index("ix_digital_cards_card_hash", "card_hash"),
        Index("ix_digital_cards_order_id", "assigned_order_id"),
        Index("ix_digital_cards_product_status", "product_id", "status"),
    )

    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
    )
    delivery_type: Mapped[DigitalDeliveryType] = mapped_column(
        Enum(DigitalDeliveryType, name="digital_delivery_enum", native_enum=False),
        default=DigitalDeliveryType.UNIQUE,
        nullable=False,
    )
    serial_number: Mapped[str | None] = mapped_column(String(128), nullable=True)
    pin_ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    card_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[DigitalCardStatus] = mapped_column(
        Enum(DigitalCardStatus, name="digital_card_status_enum", native_enum=False),
        default=DigitalCardStatus.AVAILABLE,
        nullable=False,
    )
    max_uses: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    used_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    assigned_order_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="SET NULL"),
        nullable=True,
    )
    file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    expire_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reading_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<DigitalCard(id={self.id}, product_id={self.product_id}, status={self.status})>"


class PriceTier(BaseModel):
    """Volume-based tiered pricing (Karta ``rynk_prices`` / ``findPrice``).

    Example: qty 1-5 -> base price, 6-20 -> 5% off, 21+ -> 10% off.
    ``to_qty`` of None means unbounded (21+).
    Amounts are stored in the smallest currency unit (IRR).
    """

    __tablename__ = "price_tiers"
    __table_args__ = (
        Index("ix_price_tiers_product_id", "product_id"),
    )

    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
    )
    from_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    to_qty: Mapped[int | None] = mapped_column(Integer, nullable=True)
    unit_price: Mapped[int] = mapped_column(Integer, nullable=False)

    def __repr__(self) -> str:
        return (
            f"<PriceTier(product_id={self.product_id}, "
            f"from={self.from_qty}, to={self.to_qty}, price={self.unit_price})>"
        )


class CategoryCustomField(BaseModel):
    """Dynamic per-category order fields (Karta ``categoryFields``).

    Lets a category require extra buyer input at checkout, e.g.
    Player ID, server name, account region, activation email.
    Rendered dynamically in the order form and stored with the order.
    """

    __tablename__ = "category_custom_fields"
    __table_args__ = (
        Index("ix_category_custom_fields_category_id", "category_id"),
    )

    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="CASCADE"),
        nullable=False,
    )
    field_key: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    field_type: Mapped[str] = mapped_column(String(32), default="text", nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    def __repr__(self) -> str:
        return f"<CategoryCustomField(category_id={self.category_id}, key={self.field_key})>"
