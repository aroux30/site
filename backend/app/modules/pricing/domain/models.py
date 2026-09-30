"""Multi-level price list domain models (Odoo product.pricelist concept).

A PriceList groups pricing rules for a customer segment (e.g. "retail",
"gold partner", "B2B agent"). A rule overrides the base price of a product or
variant for a quantity window, either by a fixed price or a percentage
discount. All money is integer Rial; percentage is integer basis points (bp)
so no float ever touches money.

Clean-room: only the workflow idea is taken from Odoo — none of its code.
"""

from __future__ import annotations

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
    BigInteger,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.base import BaseModel


class CustomerSegment(str, enum.Enum):
    """Coarse customer tiers a price list can target."""

    RETAIL = "retail"
    GOLD = "gold"
    WHOLESALE = "wholesale"
    B2B = "b2b"


class PriceList(BaseModel):
    """A named list of pricing rules for one customer segment."""

    __tablename__ = "price_lists"
    __table_args__ = (
        Index("ix_price_lists_segment", "segment"),
        Index("ix_price_lists_is_active", "is_active"),
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    segment: Mapped[CustomerSegment] = mapped_column(
        Enum(CustomerSegment, name="customer_segment_enum", native_enum=False),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Lower wins when several active lists target the same segment.
    priority: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    rules: Mapped[list["PriceListRule"]] = relationship(
        "PriceListRule", back_populates="price_list", lazy="select", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<PriceList(id={self.id}, name={self.name}, segment={self.segment})>"


class PriceListRule(BaseModel):
    """One price override inside a price list.

    Exactly one of ``fixed_price_rial`` / ``discount_bp`` is set. A rule can
    scope to a whole product (all variants) or a single variant; variant rules
    beat product rules (Odoo precedence).
    """

    __tablename__ = "price_list_rules"
    __table_args__ = (
        Index("ix_price_list_rules_price_list_id", "price_list_id"),
        Index("ix_price_list_rules_product_id", "product_id"),
        Index("ix_price_list_rules_variant_id", "variant_id"),
        CheckConstraint("min_quantity >= 0", name="ck_plr_min_qty_non_negative"),
        CheckConstraint("discount_bp >= 0 AND discount_bp <= 10000", name="ck_plr_discount_bp_range"),
        CheckConstraint("fixed_price_rial IS NULL OR fixed_price_rial >= 0", name="ck_plr_fixed_price_non_negative"),
    )

    price_list_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("price_lists.id", ondelete="CASCADE"),
        nullable=False,
    )
    # One of these is set; NULL means "applies to the whole catalog list".
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=True,
    )
    variant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("product_variants.id", ondelete="CASCADE"),
        nullable=True,
    )
    min_quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Fixed price in Rial, mutually exclusive with discount_bp.
    fixed_price_rial: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    # Percentage discount in basis points (100 bp = 1%). 10000 bp = free.
    discount_bp: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Relationships
    price_list: Mapped["PriceList"] = relationship("PriceList", back_populates="rules")

    def __repr__(self) -> str:
        return (
            f"<PriceListRule(id={self.id}, product_id={self.product_id}, "
            f"variant_id={self.variant_id}, min_qty={self.min_quantity})>"
        )
