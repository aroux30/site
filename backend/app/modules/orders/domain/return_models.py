"""SQLAlchemy persistence for the RMA (Return Merchandise Authorization) flow.

TASK BE-20: the domain layer (``returns.py``) previously operated on an
in-memory dataclass that was never persisted, so a customer's return request
vanished after the HTTP response and no admin could process it.  These models
give the lifecycle a durable home while keeping the domain state machine as
the single source of transition rules.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.base import BaseModel


class ReturnStatus(str, enum.Enum):
    REQUESTED = "requested"
    APPROVED = "approved"
    REJECTED = "rejected"
    RECEIVED = "received"
    INSPECTED = "inspected"
    REFUNDED = "refunded"
    REPLACED = "replaced"
    CLOSED = "closed"


class OrderReturn(BaseModel):
    """A customer return request (RMA) for one order."""

    __tablename__ = "order_returns"

    __table_args__ = (
        Index("ix_order_returns_order_id", "order_id"),
        Index("ix_order_returns_user_id", "user_id"),
        Index("ix_order_returns_status", "status"),
    )

    rma_number: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="RESTRICT"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(20), default="requested", nullable=False)
    admin_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    refund_amount: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    inspected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    refunded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    items: Mapped[list[OrderReturnItem]] = relationship(
        "OrderReturnItem",
        back_populates="order_return",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<OrderReturn(id={self.id}, rma={self.rma_number}, status={self.status})>"


class OrderReturnItem(BaseModel):
    """One order line included in a return, with its inspection outcome."""

    __tablename__ = "order_return_items"

    __table_args__ = (
        Index("ix_order_return_items_return_id", "return_id"),
        CheckConstraint("quantity > 0", name="ck_order_return_items_quantity_positive"),
    )

    return_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("order_returns.id", ondelete="CASCADE"),
        nullable=False,
    )
    order_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("order_items.id", ondelete="RESTRICT"),
        nullable=False,
    )
    variant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("product_variants.id", ondelete="RESTRICT"),
        nullable=False,
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(50), nullable=False)
    inspection_outcome: Mapped[str | None] = mapped_column(String(50), nullable=True)
    customer_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    order_return: Mapped[OrderReturn] = relationship(
        "OrderReturn",
        back_populates="items",
    )
