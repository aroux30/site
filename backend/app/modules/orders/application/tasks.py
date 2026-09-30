"""Orders background Celery tasks."""

from __future__ import annotations

import asyncio
import uuid
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

    Reconciliation guard (Phase 4 §13): an order with a live payment attempt
    (PENDING / PROCESSING / COMPLETED) is NEVER auto-cancelled. If the
    customer paid at the gateway but the callback was lost, cancelling here
    would strand the money at the gateway *and* block the late server-side
    verify (a CANCELED order is not payable). Such orders stay PENDING so the
    webhook / late callback / admin verify can still complete them; see
    docs/runbooks/payment-reconciliation.md.
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

            # Orders with a live payment attempt are reconciliation
            # candidates, not abandonments — exclude them from auto-cancel.
            from app.modules.payments.domain.models import Payment, PaymentStatus

            live_payment_order_ids: set[uuid.UUID] = set()
            if stale_orders:
                pay_stmt = select(Payment.order_id).where(
                    Payment.order_id.in_([o.id for o in stale_orders]),
                    Payment.status.in_(
                        [
                            PaymentStatus.PENDING,
                            PaymentStatus.PROCESSING,
                            PaymentStatus.COMPLETED,
                        ]
                    ),
                )
                rows = (await db.scalars(pay_stmt)).all()
                live_payment_order_ids = {oid for oid in rows if oid is not None}

            for order in stale_orders:
                if order.id in live_payment_order_ids:
                    await logger.awarning(
                        "stale_order_skipped_payment_in_flight",
                        order_id=str(order.id),
                        order_number=order.order_number,
                        age_minutes=int(
                            (datetime.now(UTC) - _as_aware(order.created_at)).total_seconds()
                            // 60
                        ),
                    )
                    continue

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
            # Re-raise rather than returning an error dict. Celery records a
            # returned value as SUCCESS, so the failure counter never moved,
            # nothing was retried, and every PENDING order kept its stock
            # committed — silently, forever, since the task is beat-scheduled
            # with no autoretry. Raising makes the failure visible and lets
            # the retry policy below act on it.
            raise

    if cancelled:
        await logger.ainfo("stale_pending_orders_cancelled", count=cancelled)
    return {"status": "success", "cancelled": cancelled}


@celery_app.task(
    name="app.modules.orders.application.tasks.cancel_stale_pending_orders",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=120,
    max_retries=5,
)
def cancel_stale_pending_orders() -> dict[str, Any]:
    """Celery task entrypoint: auto-cancel unpaid PENDING orders.

    Retries with backoff: this task releases stock, so a transient database or
    broker failure that merely returned a dict left orders stuck holding
    inventory with no signal anywhere.
    """
    return asyncio.run(_cancel_stale_pending_orders_async())
