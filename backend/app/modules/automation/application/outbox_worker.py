"""Celery background worker for processing transactional outbox messages."""

from __future__ import annotations

import asyncio
from typing import Any

import structlog

from app.core.database.session import async_session_factory
from app.shared.events.outbox_service import OutboxService
from app.worker.celery_app import celery_app

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


_ORDER_NOTIFICATIONS: dict[str, dict[str, str]] = {
    "OrderConfirmed": {
        "notification_type": "order_confirmed",
        "title": "سفارش شما تأیید شد",
    },
    "PaymentCompleted": {
        "notification_type": "payment_completed",
        "title": "پرداخت شما با موفقیت انجام شد",
    },
    "OrderCanceled": {
        "notification_type": "order_canceled",
        "title": "سفارش شما لغو شد",
    },
    "ReturnApproved": {
        "notification_type": "return_approved",
        "title": "درخواست مرجوعی شما تأیید شد",
    },
}


async def _handle_message(db: Any, event_type: str, payload: dict[str, Any]) -> None:
    """Route outbox message to the appropriate module handler."""
    if event_type in ("ProductCreated", "ProductUpdated", "ProductDeleted"):
        # Search index sync
        product_id = payload.get("product_id") or payload.get("id")
        if product_id:
            try:
                from app.modules.search.application.tasks import sync_single_product

                sync_single_product.delay(str(product_id))
            except Exception as e:
                logger.warning("outbox_search_dispatch_failed", error=str(e))

    elif event_type in _ORDER_NOTIFICATIONS:
        spec = _ORDER_NOTIFICATIONS[event_type]
        if event_type == "PaymentCompleted":
            await _allocate_digital_cards(db, order_id=payload.get("order_id"))
        await _notify_order_event(
            db,
            event_type=event_type,
            notification_type=spec["notification_type"],
            title=spec["title"],
            order_id=payload.get("order_id"),
            data=payload,
        )

    elif event_type == "RefundProcessed":
        await _notify_refund_event(db, payload)


async def _allocate_digital_cards(db: Any, *, order_id: Any) -> None:
    """Allocate digital-card stock for a paid order (Karta digital delivery).

    Runs on PaymentCompleted so the retail checkout flow receives PINs the
    same way the B2B reseller flow does; customers read them via
    ``GET /inventory/digital/orders/{id}/cards``.

    Idempotent by transaction: allocation effects and the outbox
    ``processed`` flag commit atomically, so a retry only happens after a
    full rollback. A stock-out is logged for manual action (the payment is
    already settled) and must never swallow the customer notification.
    """
    if not order_id:
        return
    try:
        import uuid as uuid_mod

        from sqlalchemy.orm import selectinload

        from app.core.exceptions.handlers import ConflictError
        from app.modules.catalog.domain.models import Product, ProductType, ProductVariant
        from app.modules.inventory.application import card_service
        from app.modules.orders.domain.models import Order

        order = await db.get(
            Order,
            uuid_mod.UUID(str(order_id)),
            options=(selectinload(Order.items),),
        )
        if order is None:
            logger.warning(
                "outbox_order_not_found",
                event_type="PaymentCompleted",
                order_id=str(order_id),
            )
            return

        for item in order.items:
            variant = await db.get(ProductVariant, item.variant_id)
            if variant is None:
                continue
            product = await db.get(Product, variant.product_id)
            if product is None or product.product_type != ProductType.DIGITAL:
                continue

            try:
                await card_service.allocate_cards_for_order(
                    db,
                    product_id=product.id,
                    order_id=order.id,
                    quantity=item.quantity,
                )
            except ConflictError as exc:
                # Payment is already settled — surface loudly for manual
                # restocking; never block the customer notification.
                await logger.aerror(
                    "digital_stock_out_after_payment",
                    order_id=str(order.id),
                    product_id=str(product.id),
                    quantity=item.quantity,
                    error=str(exc),
                )
                continue

        await logger.ainfo("digital_allocation_processed", order_id=str(order.id))
    except Exception as exc:
        # Let the outbox retry mechanism handle transient failures.
        raise RuntimeError(f"digital allocation failed for order {order_id}: {exc}") from exc


async def _notify_order_event(
    db: Any,
    *,
    event_type: str,
    notification_type: str,
    title: str,
    order_id: Any,
    data: dict[str, Any],
) -> None:
    """Create the customer-facing in-app notification for an order event."""
    if not order_id:
        return
    try:
        import uuid as uuid_mod

        from app.modules.notifications.application.notification_service import (
            NotificationService,
        )
        from app.modules.orders.domain.models import Order

        order = await db.get(Order, uuid_mod.UUID(str(order_id)))
        if order is None:
            logger.warning(
                "outbox_order_not_found",
                event_type=event_type,
                order_id=str(order_id),
            )
            return

        order_number = getattr(order, "order_number", "")
        body = f"سفارش {order_number} به‌روزرسانی شد. برای جزئیات به بخش سفارش‌های خود مراجعه کنید."
        notification = await NotificationService.create_notification(
            db,
            user_id=order.user_id,
            type=notification_type,
            title=title,
            body=body,
            data=data,
        )
        _dispatch(str(notification.id))
        logger.info(
            "outbox_notification_created",
            event_type=event_type,
            notification_id=str(notification.id),
        )
    except Exception as exc:
        # Let the outbox retry mechanism handle transient failures.
        raise RuntimeError(f"notification handling failed for {event_type}: {exc}") from exc


async def _notify_refund_event(db: Any, payload: dict[str, Any]) -> None:
    """Create the customer-facing notification for a processed refund."""
    order_id = payload.get("order_id")
    if not order_id:
        return
    try:
        import uuid as uuid_mod

        from app.modules.notifications.application.notification_service import (
            NotificationService,
        )
        from app.modules.orders.domain.models import Order

        order = await db.get(Order, uuid_mod.UUID(str(order_id)))
        if order is None:
            logger.warning(
                "outbox_order_not_found",
                event_type="RefundProcessed",
                order_id=str(order_id),
            )
            return

        notification = await NotificationService.create_notification(
            db,
            user_id=order.user_id,
            type="refund_processed",
            title="بازگشت وجه انجام شد",
            body=(
                f"مبلغ بازگشتی برای سفارش {order.order_number} ثبت شد. "
                "وجه حداکثر تا ۷۲ ساعت آینده به حساب یا کیف پول شما بازمی‌گردد."
            ),
            data=payload,
        )
        _dispatch(str(notification.id))
        logger.info(
            "outbox_notification_created",
            event_type="RefundProcessed",
            notification_id=str(notification.id),
        )
    except Exception as exc:
        raise RuntimeError(f"notification handling failed for RefundProcessed: {exc}") from exc


def _dispatch(notification_id: str) -> None:
    """Queue channel dispatch for a created notification (best-effort).

    The in-app notification row already exists at this point; a failure to
    enqueue channel delivery must never fail the outbox message (it would
    duplicate the in-app notification on retry).
    """
    try:
        from app.modules.notifications.application.tasks import send_notification_task

        send_notification_task.delay(notification_id)
    except Exception as exc:
        logger.warning("notification_dispatch_enqueue_failed", error=str(exc))


async def _drain_outbox_async(batch_size: int = 50) -> dict[str, Any]:
    """Claim and dispatch a batch of pending outbox messages."""
    processed = 0
    failed = 0

    async with async_session_factory() as db:
        try:
            messages = await OutboxService.claim_batch(db, batch_size=batch_size)
            await db.commit()
        except Exception as e:
            await db.rollback()
            await logger.aerror("outbox_claim_failed", error=str(e))
            return {"status": "error", "message": str(e)}

    # Process each claimed message
    for msg in messages:
        async with async_session_factory() as db:
            try:
                await _handle_message(db, msg.event_type, msg.payload)
                await OutboxService.mark_processed(db, msg.id)
                await db.commit()
                processed += 1
            except Exception as e:
                await db.rollback()
                await OutboxService.mark_failed(db, msg.id, str(e))
                await db.commit()
                failed += 1

    return {"status": "success", "processed": processed, "failed": failed}


@celery_app.task(name="app.modules.automation.application.outbox_worker.process_outbox_queue")
def process_outbox_queue() -> dict[str, Any]:
    """Periodic Celery worker task to process outbox queue."""
    return asyncio.run(_drain_outbox_async())
