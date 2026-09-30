"""Domain events and emission helpers for core business modules."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import structlog

from app.shared.events.base import DomainEvent, event_bus

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


# ── Cart Domain Events ────────────────────────────────────────────────────


class CartItemAdded(DomainEvent):
    cart_id: uuid.UUID
    variant_id: uuid.UUID
    quantity: int
    user_id: uuid.UUID | None = None


class CartItemUpdated(DomainEvent):
    cart_id: uuid.UUID
    item_id: uuid.UUID
    quantity: int
    user_id: uuid.UUID | None = None


class CartItemRemoved(DomainEvent):
    cart_id: uuid.UUID
    item_id: uuid.UUID
    user_id: uuid.UUID | None = None


class CartCleared(DomainEvent):
    cart_id: uuid.UUID
    user_id: uuid.UUID | None = None


class CartRecoveryQueued(DomainEvent):
    """An abandoned-cart recovery reminder was queued for delivery."""

    cart_id: uuid.UUID
    user_id: uuid.UUID
    stage: int
    channel: str
    subtotal_rial: int
    item_count: int
    recover_url: str


# ── Checkout Domain Events ────────────────────────────────────────────────


class CheckoutStarted(DomainEvent):
    cart_id: uuid.UUID
    user_id: uuid.UUID


class CheckoutCompleted(DomainEvent):
    order_id: uuid.UUID
    user_id: uuid.UUID
    total_amount: int


# ── Order Domain Events ───────────────────────────────────────────────────


class OrderCreated(DomainEvent):
    order_id: uuid.UUID
    order_number: str
    user_id: uuid.UUID
    total: int


class OrderStatusChanged(DomainEvent):
    order_id: uuid.UUID
    from_status: str | None
    to_status: str
    changed_by: uuid.UUID | None = None
    reason: str | None = None


class OrderCancelled(DomainEvent):
    order_id: uuid.UUID
    user_id: uuid.UUID
    reason: str | None = None


# ── Payment Domain Events ─────────────────────────────────────────────────


class PaymentInitiated(DomainEvent):
    payment_id: uuid.UUID
    order_id: uuid.UUID
    provider: str
    amount: int


class PaymentVerified(DomainEvent):
    payment_id: uuid.UUID
    order_id: uuid.UUID
    provider: str
    amount: int
    ref_id: str | None = None


class PaymentFailed(DomainEvent):
    payment_id: uuid.UUID
    order_id: uuid.UUID
    provider: str
    error_code: str | None = None
    error_message: str | None = None


class PaymentRefunded(DomainEvent):
    payment_id: uuid.UUID
    order_id: uuid.UUID
    provider: str
    amount: int


# ── Event Recorder Helper ─────────────────────────────────────────────────


async def record_domain_event(
    event: DomainEvent,
    aggregate_type: str,
    aggregate_id: str | uuid.UUID,
    *,
    db: AsyncSession | None = None,
    publish_outbox: bool = False,
) -> None:
    """Record a domain event with Prometheus metrics, structured logs, and bus dispatch."""
    from app.core.observability.metrics import DOMAIN_EVENTS_TOTAL
    from app.core.observability.tracer import get_current_trace_id

    agg_id_str = str(aggregate_id)
    event_type = event.event_type or type(event).__name__
    trace_id = get_current_trace_id()

    # 1. Prometheus Metric
    DOMAIN_EVENTS_TOTAL.labels(aggregate_type=aggregate_type, event_type=event_type).inc()

    # 2. Structured Log
    await logger.ainfo(
        "domain_event_emitted",
        event_type=event_type,
        aggregate_type=aggregate_type,
        aggregate_id=agg_id_str,
        trace_id=trace_id,
        payload=event.model_dump(mode="json"),
    )

    # 3. In-process EventBus dispatch
    try:
        await event_bus.publish(event)
    except Exception as exc:
        await logger.awarning(
            "domain_event_bus_dispatch_failed", event_type=event_type, error=str(exc)
        )

    # 4. Transactional Outbox (optional)
    if db is not None and publish_outbox:
        try:
            from app.shared.events.outbox_service import OutboxService

            await OutboxService.publish(
                db,
                event_type=event_type,
                aggregate_type=aggregate_type,
                aggregate_id=agg_id_str,
                payload=event.model_dump(mode="json"),
                correlation_id=trace_id,
            )
        except Exception as exc:
            await logger.awarning(
                "domain_event_outbox_publish_failed", event_type=event_type, error=str(exc)
            )
