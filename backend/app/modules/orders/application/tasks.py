"""Orders background Celery tasks."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import select

from app.core.config.settings import get_settings
from app.core.database.session import async_session_factory
from app.modules.orders.domain.models import Order, OrderStatus, OrderStatusHistory
from app.worker.celery_app import celery_app

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_BATCH_LIMIT = 100


def _as_aware(dt: datetime) -> datetime:
    """Normalize a possibly-naive datetime to UTC-aware for comparisons."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


async def _cancel_stale_pending_orders_async() -> dict[str, Any]:
    """Cancel PENDING orders whose payment never arrived within the TTL.

    Checkout commits inventory at order-creation time, so an unpaid PENDING
    order holds stock indefinitely.  This task cancels stale orders, returns
    their stock to available inventory, and records a status-history entry.
    """
    settings = get_settings()
    timeout_minutes = getattr(settings, "ORDER_PAYMENT_TIMEOUT_MINUTES", 60)
    cutoff = datetime.now(UTC) - timedelta(minutes=timeout_minutes)
    cancelled = 0

    async with async_session_factory() as db:
        try:
            stmt = select(Order).filter_by(status=OrderStatus.PENDING).with_for_update()
            pending_orders = (await db.scalars(stmt)).all()
            # Filter the payment timeout in Python — pending orders are a
            # small, bounded set and this keeps the scan index-friendly.
            stale_orders = [
                o
                for o in pending_orders
                if o.created_at is not None and _as_aware(o.created_at) < cutoff
            ][:_BATCH_LIMIT]

            for order in stale_orders:
                from app.modules.inventory.application import inventory_service

                try:
                    await inventory_service.restock_order(db, order.id)
                except Exception as exc:
                    await logger.aerror(
                        "stale_order_restock_failed",
                        order_id=str(order.id),
                        error=str(exc),
                    )
                    continue

                from_status = order.status.value
                order.status = OrderStatus.CANCELED
                db.add(order)
                db.add(
                    OrderStatusHistory(
                        order_id=order.id,
                        from_status=from_status,
                        to_status=OrderStatus.CANCELED.value,
                        changed_by=None,
                        reason=(
                            "Payment not received within "
                            f"{timeout_minutes} minutes; order auto-cancelled"
                        ),
                    )
                )
                try:
                    from app.shared.events.outbox_service import OutboxService

                    await OutboxService.publish(
                        db,
                        event_type="OrderCanceled",
                        aggregate_type="order",
                        aggregate_id=str(order.id),
                        payload={
                            "order_id": str(order.id),
                            "order_number": order.order_number,
                            "initiated_by": "system",
                            "reason": "payment_timeout",
                        },
                    )
                except Exception as exc:
                    await logger.awarning(
                        "order_event_publish_skipped",
                        event_type="OrderCanceled",
                        order_id=str(order.id),
                        error=str(exc),
                    )
                cancelled += 1

            await db.commit()
        except Exception as exc:
            await db.rollback()
            await logger.aerror("cancel_stale_orders_failed", error=str(exc))
            return {"status": "error", "message": str(exc)}

    if cancelled:
        await logger.ainfo("stale_pending_orders_cancelled", count=cancelled)
    return {"status": "success", "cancelled": cancelled}


@celery_app.task(name="app.modules.orders.application.tasks.cancel_stale_pending_orders")
def cancel_stale_pending_orders() -> dict[str, Any]:
    """Celery task entrypoint: auto-cancel unpaid PENDING orders."""
    return asyncio.run(_cancel_stale_pending_orders_async())
