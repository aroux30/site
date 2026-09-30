"""Shopping cart domain models."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.base import BaseModel

# ---- Enums ----


class CartStatus(str, enum.Enum):
    ACTIVE = "active"
    MERGED = "merged"
    ABANDONED = "abandoned"
    CONVERTED = "converted"


class RecoveryChannel(str, enum.Enum):
    SMS = "sms"
    IN_APP = "in_app"


# ---- Models ----


class Cart(BaseModel):
    """Shopping cart supporting both authenticated and guest users."""

    __tablename__ = "carts"
    __table_args__ = (
        Index("ix_carts_user_id", "user_id"),
        Index("ix_carts_session_id", "session_id"),
        Index("ix_carts_status", "status"),
        Index("ix_carts_expires_at", "expires_at"),
    )

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    session_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[CartStatus] = mapped_column(
        Enum(CartStatus, name="cart_status_enum", native_enum=False),
        default=CartStatus.ACTIVE,
        nullable=False,
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Abandoned-cart recovery: last item edit is the idempotence signal for
    # the recovery task. A cart is only remindable again after an edit, so a
    # user who just got a reminder can never be reminded again until they
    # touch the cart.
    last_activity_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Highest recovery stage already attempted; stage numbers are the
    # 0-based indexes into Settings.CART_RECOVERY_STAGES_MINUTES.
    recovery_stage: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Relationships
    items: Mapped[list["CartItem"]] = relationship(
        "CartItem", back_populates="cart", lazy="select", cascade="all, delete-orphan"
    )
    recovery_attempts: Mapped[list["CartRecoveryAttempt"]] = relationship(
        "CartRecoveryAttempt", back_populates="cart", lazy="select", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Cart(id={self.id}, status={self.status})>"


class CartItem(BaseModel):
    """Individual items within a shopping cart."""

    __tablename__ = "cart_items"
    __table_args__ = (
        UniqueConstraint("cart_id", "variant_id", name="uq_cart_items_cart_variant"),
        CheckConstraint("quantity > 0", name="ck_cart_items_quantity_positive"),
        Index("ix_cart_items_cart_id", "cart_id"),
        Index("ix_cart_items_variant_id", "variant_id"),
    )

    cart_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("carts.id", ondelete="CASCADE"),
        nullable=False,
    )
    variant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("product_variants.id", ondelete="CASCADE"),
        nullable=False,
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    price_snapshot: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # Relationships
    cart: Mapped["Cart"] = relationship("Cart", back_populates="items")

    def __repr__(self) -> str:
        return f"<CartItem(id={self.id}, cart_id={self.cart_id}, variant_id={self.variant_id})>"


class CartRecoveryAttempt(BaseModel):
    """One attempted reminder send for an abandoned cart.

    The per-(cart, stage) row is the idempotence ledger: a reminder is only
    sent when no row exists for that stage yet, and the row is written in the
    same transaction as the outbox message that drives delivery, so a task
    retry or a crash between steps can never re-send one stage.
    """

    __tablename__ = "cart_recovery_attempts"
    __table_args__ = (
        UniqueConstraint("cart_id", "stage", name="uq_cart_recovery_cart_stage"),
        Index("ix_cart_recovery_cart_id", "cart_id"),
    )

    cart_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("carts.id", ondelete="CASCADE"),
        nullable=False,
    )
    stage: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    channel: Mapped[RecoveryChannel] = mapped_column(
        Enum(RecoveryChannel, name="recovery_channel_enum", native_enum=False),
        nullable=False,
    )
    # Snapshot of the cart the user is being reminded about; integer Rial.
    subtotal_rial: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    item_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Relationships
    cart: Mapped["Cart"] = relationship("Cart", back_populates="recovery_attempts")

    def __repr__(self) -> str:
        return f"<CartRecoveryAttempt(cart_id={self.cart_id}, stage={self.stage}, channel={self.channel})>"
