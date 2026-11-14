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
from typing import Any
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
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
        server_default=text("'UNIQUE'::character varying"),
    )
    # Legacy plaintext serial (retired by migration b1c2d3e4f5a6; kept only
    # so pre-migration NULLs do not break old readers).
    serial_number: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # Serials are sensitive too (Karta card_encrypt) — AES-256-GCM at rest.
    serial_ciphertext: Mapped[str | None] = mapped_column(Text, nullable=True)
    pin_ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    card_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[DigitalCardStatus] = mapped_column(
        Enum(DigitalCardStatus, name="digital_card_status_enum", native_enum=False),
        default=DigitalCardStatus.AVAILABLE,
        nullable=False,
        server_default=text("'AVAILABLE'::character varying"),
    )
    max_uses: Mapped[int] = mapped_column(
        Integer, default=1, nullable=False, server_default=text("1")
    )
    used_count: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, server_default=text("0")
    )
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
    __table_args__ = (Index("ix_price_tiers_product_id", "product_id"),)

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
    Player ID, server name, account region, activation note.
    Rendered dynamically in the order form and stored with the order.
    """

    __tablename__ = "category_custom_fields"
    __table_args__ = (Index("ix_category_custom_fields_category_id", "category_id"),)

    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="CASCADE"),
        nullable=False,
    )
    field_key: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    field_type: Mapped[str] = mapped_column(
        String(32),
        default="text",
        nullable=False,
        server_default=text("'text'::character varying"),
    )
    # Optional helper line under the label (Woo Product Add-ons parity — the
    # same shape the per-product addon fields carry).
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # multiple_choice display style: select | radio.
    display: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # For select-type fields: the allowed answer values.
    options_json: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    is_required: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, server_default=text("false")
    )
    # Restrictions: character length (texts), quantity (input_multiplier),
    # Toman range (custom_price) — aligned with ProductAddonField.
    min_val: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_val: Mapped[int | None] = mapped_column(Integer, nullable=True)
    position: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, server_default=text("0")
    )

    def __repr__(self) -> str:
        return f"<CategoryCustomField(category_id={self.category_id}, key={self.field_key})>"


class ProductAddonField(BaseModel):
    """Per-product add-on fields — WooCommerce Product Add-ons parity.

    Where ``CategoryCustomField`` attaches buyer-input fields to a whole
    category, this model attaches them to ONE product: the owner's request —
    addon fields are often product-specific and meaningless store-wide
    (engraving text on a mug, jersey name/number, gift wrap).

    Field types mirror the reference plugin's panel (html-addon.php):
    multiple_choice, checkbox, custom_text, custom_textarea, custom_price
    (buyer-defined price), input_multiplier (quantity), heading.
    File upload needs a public customer-upload endpoint this stack does not
    have yet, so it is out of scope for now (declared in the delivery report).

    Prices are stored in Rial (the catalog DB convention); the API boundary
    converts Toman like everywhere else (memory: money-unit-two-conventions).
    """

    __tablename__ = "product_addon_fields"
    __table_args__ = (Index("ix_product_addon_fields_product_id", "product_id"),)

    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
    )
    field_key: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    # Optional helper line under the label (reference: description_enable).
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    field_type: Mapped[str] = mapped_column(
        String(32),
        default="custom_text",
        nullable=False,
        server_default=text("'custom_text'::character varying"),
    )
    # multiple_choice display style: select | radio | checkbox.
    display: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # Options for multiple_choice/checkbox: [{"label","price","price_type"}]
    # (price = Rial int, price_type = flat_fee | quantity_based | percentage_based).
    options_json: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)
    is_required: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, server_default=text("false")
    )
    # Restrictions (reference: min/max) — character length for texts,
    # quantity range for input_multiplier, price range (Rial) for custom_price.
    min_val: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_val: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Field-level price adjustment for non-option types (input_multiplier):
    # price in Rial + flat_fee | quantity_based | percentage_based.
    price: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    price_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    position: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, server_default=text("0")
    )

    def __repr__(self) -> str:
        return f"<ProductAddonField(product_id={self.product_id}, key={self.field_key})>"
