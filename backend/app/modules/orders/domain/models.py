"""Order management domain models."""

import enum
import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.base import BaseModel

if TYPE_CHECKING:
    from app.modules.payments.domain.models import Payment
    from app.modules.users.domain.models import User

# ---- Enums ----


class OrderStatus(str, enum.Enum):
    """Order lifecycle — a WooCommerce-style vocabulary, 2026-10-11.

    Owner decision: the previous twelve-status chain modelled a physical
    store. This is a DIGITAL store (2908 digital + 2238 simple products, 0
    shipments), so the packaging and delivery stages were noise. The live
    table backs that up — ``delivered``, ``on_hold``, ``returned`` and
    ``partially_refunded`` held zero rows, and ``shipped``/``refunded`` one
    each, both synthetic test fixtures.

    The one distinction that DOES matter is payment: an unpaid order sitting
    in a gateway and one waiting for an admin to eyeball a card-to-card
    receipt need different handling. The first is abandoned by the customer
    and should expire to ``canceled`` on its own; the second is an operator's
    job and must never expire, however late they get to it.
    """

    #: Order created, sent to the gateway, awaiting the gateway callback.
    #: Abandoned ones expire to CANCELED (see the pending-payment sweep).
    WAITING_PAYMENT_GATEWAY = "waiting_payment_gateway"
    #: Card-to-card receipt uploaded — waiting for an ADMIN, never expires.
    WAITING_PAYMENT_CARD = "waiting_payment_card"
    #: Paid and accepted; the operator is working on it.
    PENDING = "pending"
    #: Being fulfilled / under review (WooCommerce "On-hold" stage).
    PROCESSING = "processing"
    COMPLETED = "completed"
    CANCELED = "canceled"
    REFUNDED = "refunded"


# ---- Models ----


class Order(BaseModel):
    """Customer order with full financial snapshot."""

    __tablename__ = "orders"
    __table_args__ = (
        Index("ix_orders_user_id", "user_id"),
        Index("ix_orders_order_number", "order_number"),
        Index("ix_orders_status", "status"),
        Index("ix_orders_created_at", "created_at"),
        Index("ix_orders_idempotency_key", "idempotency_key"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    order_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    status: Mapped[OrderStatus] = mapped_column(
        # `length` is explicit on purpose. Left to itself, SQLAlchemy derives
        # the column width from the longest enum NAME at the time the DDL was
        # written — that was `PARTIALLY_REFUNDED` (18), and the width silently
        # survived the vocabulary change, so the longer names added later
        # (`WAITING_PAYMENT_GATEWAY` is 23) fail at the database with
        # StringDataRightTruncation. Pinning a comfortable width means a
        # future rename cannot die that way.
        Enum(OrderStatus, name="order_status_enum", native_enum=False, length=32),
        # Safe default for any code path that constructs an Order without an
        # explicit status. Checkout sets the real opening status
        # (WAITING_PAYMENT_GATEWAY or WAITING_PAYMENT_CARD) based on the
        # payment method; this is the fallback and matches the common
        # (gateway) case.
        default=OrderStatus.WAITING_PAYMENT_GATEWAY,
        nullable=False,
    )
    subtotal: Mapped[int] = mapped_column(BigInteger, nullable=False)
    shipping_cost: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    tax: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    discount_amount: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    total: Mapped[int] = mapped_column(BigInteger, nullable=False)
    shipping_address_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", lazy="selectin", viewonly=True)
    items: Mapped[list["OrderItem"]] = relationship(
        "OrderItem", back_populates="order", lazy="selectin", cascade="all, delete-orphan"
    )
    status_history: Mapped[list["OrderStatusHistory"]] = relationship(
        "OrderStatusHistory", back_populates="order", lazy="select"
    )
    # One-to-many via payments.order_id FK; the Payment side has no
    # back_populates (orderless top-up payments keep order_id NULL).
    payments: Mapped[list["Payment"]] = relationship(
        "Payment", foreign_keys="Payment.order_id", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<Order(id={self.id}, order_number={self.order_number}, status={self.status})>"


class OrderItem(BaseModel):
    """Individual line items in an order with immutable snapshots."""

    __tablename__ = "order_items"
    __table_args__ = (
        Index("ix_order_items_order_id", "order_id"),
        Index("ix_order_items_variant_id", "variant_id"),
        CheckConstraint("quantity > 0", name="ck_order_items_quantity_positive"),
    )

    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
    )
    variant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("product_variants.id", ondelete="RESTRICT"),
        nullable=False,
    )
    product_name: Mapped[str] = mapped_column(String(500), nullable=False)
    variant_info: Mapped[str | None] = mapped_column(String(500), nullable=True)
    sku: Mapped[str] = mapped_column(String(100), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[int] = mapped_column(BigInteger, nullable=False)
    total_price: Mapped[int] = mapped_column(BigInteger, nullable=False)
    # Karta categoryFields answers captured at checkout (Sprint 1.7);
    # validated server-side against the category field definitions.
    custom_fields: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    # Relationships
    order: Mapped["Order"] = relationship("Order", back_populates="items")

    def __repr__(self) -> str:
        return f"<OrderItem(id={self.id}, sku={self.sku}, quantity={self.quantity})>"


class OrderStatusHistory(BaseModel):
    """Immutable log of order status transitions."""

    __tablename__ = "order_status_history"
    __table_args__ = (
        Index("ix_order_status_history_order_id", "order_id"),
        Index("ix_order_status_history_created_at", "created_at"),
    )

    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
    )
    from_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    to_status: Mapped[str] = mapped_column(String(50), nullable=False)
    changed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra_data: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONB, nullable=True)

    # Relationships
    order: Mapped["Order"] = relationship("Order", back_populates="status_history")

    @property
    def actor_id(self) -> uuid.UUID | None:
        return self.changed_by

    @actor_id.setter
    def actor_id(self, val: uuid.UUID | None) -> None:
        self.changed_by = val

    @property
    def correlation_id(self) -> str | None:
        if self.extra_data and isinstance(self.extra_data, dict):
            return self.extra_data.get("correlation_id")
        return None

    @correlation_id.setter
    def correlation_id(self, val: str | None) -> None:
        if self.extra_data is None:
            self.extra_data = {}
        self.extra_data["correlation_id"] = val

    def __repr__(self) -> str:
        return f"<OrderStatusHistory(id={self.id}, order_id={self.order_id}, to_status={self.to_status})>"  # noqa: E501
