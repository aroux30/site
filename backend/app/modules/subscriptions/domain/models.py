"""Subscription domain models.

Design notes
------------
* **A subscription is a plan, not a cart.** The line items are snapshotted at
  subscribe time (variant id + quantity + the price the customer agreed to).
  A price change in the catalog does not silently re-price an active
  subscription; the next cycle bills the snapshotted price, and the admin UI
  shows when the catalog price has drifted (``price_drift_rial``).
* **Billing is idempotent per period.** ``SubscriptionBilling`` rows are keyed
  ``(subscription_id, period_index)`` under a unique constraint, so a retried
  Celery task can never double-charge a cycle.
* **Failure is a state, not an exception.** A declined charge moves the
  subscription to ``PAST_DUE`` and records the attempt; the dunning path
  retries on the next run and the customer can pay manually. Subscriptions are
  never auto-cancelled on a single failure — that is a customer-hostile
  default and an Iranian gateway reality (temporary limits are common).
* **Money is integer Rials**, like every other money column in the platform.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
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

if TYPE_CHECKING:
    from app.modules.catalog.domain.models import ProductVariant


class SubscriptionStatus(str, enum.Enum):
    """Lifecycle of a subscription.

    ``PAST_DUE`` is recoverable: the next successful charge (automatic or a
    customer's manual payment) returns it to ``ACTIVE``.
    """

    ACTIVE = "active"
    PAUSED = "paused"
    PAST_DUE = "past_due"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class SubscriptionInterval(str, enum.Enum):
    """Billing cadence. ``CUSTOM_DAYS`` reads ``custom_interval_days``."""

    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"
    CUSTOM_DAYS = "custom_days"


class BillingStatus(str, enum.Enum):
    """Outcome of one billing cycle attempt."""

    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
    SKIPPED = "skipped"


class Subscription(BaseModel):
    """A recurring purchase plan owned by one user."""

    __tablename__ = "subscriptions"
    __table_args__ = (
        Index("ix_subscriptions_user_id", "user_id"),
        Index("ix_subscriptions_status", "status"),
        Index("ix_subscriptions_next_billing_at", "next_billing_at"),
        UniqueConstraint(
            "user_id",
            "idempotency_key",
            name="uq_subscriptions_user_idempotency",
        ),
        CheckConstraint("interval_count > 0", name="ck_subscriptions_interval_count"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    #: Human-readable plan name shown in the account area.
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[SubscriptionStatus] = mapped_column(
        Enum(SubscriptionStatus, name="subscription_status_enum", native_enum=False),
        default=SubscriptionStatus.ACTIVE,
        nullable=False,
    )
    interval: Mapped[SubscriptionInterval] = mapped_column(
        Enum(SubscriptionInterval, name="subscription_interval_enum", native_enum=False),
        nullable=False,
    )
    #: Multiplier on the interval (e.g. MONTHLY + 2 = every two months).
    interval_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    custom_interval_days: Mapped[int | None] = mapped_column(Integer, nullable=True)

    #: The tokenized card this subscription charges. Nullable on purpose: a
    #: subscription can exist without a card and degrade to "renewal reminder"
    #: (the customer pays manually each cycle) — the graceful path when a
    #: gateway has no tokenization support.
    saved_method_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("saved_payment_methods.id", ondelete="SET NULL"),
        nullable=True,
    )

    #: Snapshot of the agreed price, in integer Rials, per unit.
    total_per_cycle: Mapped[int] = mapped_column(BigInteger, nullable=False)
    shipping_address_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    next_billing_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_billed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    #: Consecutive failed cycles; reset on success. Drives the dunning ladder.
    failure_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True)

    items: Mapped[list["SubscriptionItem"]] = relationship(
        "SubscriptionItem",
        back_populates="subscription",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    billings: Mapped[list["SubscriptionBilling"]] = relationship(
        "SubscriptionBilling",
        back_populates="subscription",
        lazy="select",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<Subscription(id={self.id}, name={self.name!r}, "
            f"status={self.status.value}, next={self.next_billing_at})>"
        )


class SubscriptionItem(BaseModel):
    """One line of a subscription plan, priced at subscribe time."""

    __tablename__ = "subscription_items"
    __table_args__ = (
        Index("ix_subscription_items_subscription_id", "subscription_id"),
        CheckConstraint("quantity > 0", name="ck_subscription_items_quantity_positive"),
        CheckConstraint("unit_price_rial >= 0", name="ck_subscription_items_price_non_negative"),
    )

    subscription_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subscriptions.id", ondelete="CASCADE"),
        nullable=False,
    )
    variant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("product_variants.id", ondelete="RESTRICT"),
        nullable=False,
    )
    product_name: Mapped[str] = mapped_column(String(500), nullable=False)
    sku: Mapped[str] = mapped_column(String(100), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price_rial: Mapped[int] = mapped_column(BigInteger, nullable=False)

    subscription: Mapped["Subscription"] = relationship(
        "Subscription", back_populates="items"
    )
    variant: Mapped["ProductVariant"] = relationship(
        "ProductVariant", lazy="selectin", viewonly=True
    )


class SubscriptionBilling(BaseModel):
    """One billing cycle attempt — the audit trail of what was charged when.

    ``period_index`` counts cycles from the subscription start (0-based), so
    "the third month's charge" is addressable even after pauses. The unique
    ``(subscription_id, period_index)`` is what makes a retried Celery run
    safe: a second attempt at period 3 finds the row and returns it instead of
    charging again.
    """

    __tablename__ = "subscription_billings"
    __table_args__ = (
        Index("ix_subscription_billings_subscription_id", "subscription_id"),
        Index("ix_subscription_billings_period", "period_index"),
        UniqueConstraint(
            "subscription_id",
            "period_index",
            name="uq_subscription_billings_period",
        ),
    )

    subscription_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subscriptions.id", ondelete="CASCADE"),
        nullable=False,
    )
    period_index: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[BillingStatus] = mapped_column(
        Enum(BillingStatus, name="subscription_billing_status_enum", native_enum=False),
        default=BillingStatus.PENDING,
        nullable=False,
    )
    amount_rial: Mapped[int] = mapped_column(BigInteger, nullable=False)
    #: The order this cycle produced (null while pending / on failure paths
    #: that never created one).
    order_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="SET NULL"),
        nullable=True,
    )
    payment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("payments.id", ondelete="SET NULL"),
        nullable=True,
    )
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    billed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    #: Set when the cycle skipped auto-charge and notified the customer to pay
    #: manually (no saved card, or tokenization unsupported by the gateway).
    renewal_notified: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, server_default="false"
    )

    subscription: Mapped["Subscription"] = relationship(
        "Subscription", back_populates="billings"
    )

    def __repr__(self) -> str:
        return (
            f"<SubscriptionBilling(sub={self.subscription_id}, "
            f"period={self.period_index}, status={self.status.value})>"
        )
