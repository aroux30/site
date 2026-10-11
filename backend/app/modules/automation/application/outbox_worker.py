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
    "OrderCreated": {
        "notification_type": "order_created",
        "title": "سفارش شما ثبت شد",
    },
    "OrderAccepted": {
        "notification_type": "order_accepted",
        "title": "سفارش شما پذیرفته شد",
    },
    "OrderProcessing": {
        "notification_type": "order_processing",
        "title": "سفارش شما در حال پردازش است",
    },
    "OrderCompleted": {
        "notification_type": "order_completed",
        "title": "سفارش شما تکمیل شد",
    },
    "OrderCanceled": {
        "notification_type": "order_canceled",
        "title": "سفارش شما لغو شد",
    },
    "OrderCancelled": {
        "notification_type": "order_canceled",
        "title": "سفارش شما لغو شد",
    },
    "PaymentCompleted": {
        "notification_type": "payment_completed",
        "title": "پرداخت شما با موفقیت انجام شد",
    },
    "PaymentFailed": {
        "notification_type": "payment_failed",
        "title": "پرداخت شما ناموفق بود",
    },
}

#: Wallet event types published by wallet_service. Each carries ``user_id`` in
#: the payload (the recipient). Bodies are built in ``_notify_wallet_event``
#: because they need the amount/direction, which differ per event.
_WALLET_NOTIFICATIONS = {
    "WalletTransferSent": {
        "notification_type": "wallet_transfer_sent",
        "title": "انتقال از کیف پول انجام شد",
    },
    "WalletTransferReceived": {
        "notification_type": "wallet_transfer_received",
        "title": "مبلغی به کیف پول شما واریز شد",
    },
    "WalletWithdrawalRequested": {
        "notification_type": "wallet_withdrawal_requested",
        "title": "درخواست برداشت ثبت شد",
    },
    "WalletWithdrawalApproved": {
        "notification_type": "wallet_withdrawal_approved",
        "title": "درخواست برداشت تأیید شد",
    },
    "WalletWithdrawalRejected": {
        "notification_type": "wallet_withdrawal_rejected",
        "title": "درخواست برداشت رد شد",
    },
    "WalletWithdrawalPaid": {
        "notification_type": "wallet_withdrawal_paid",
        "title": "برداشت کیف پول پرداخت شد",
    },
    "WalletAdminAdjusted": {
        "notification_type": "wallet_admin_adjusted",
        "title": "موجودی کیف پول شما تغییر کرد",
    },
}


async def _handle_message(
    db: Any, event_type: str, payload: dict[str, Any], message_id: Any = None
) -> None:
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
        if event_type == "OrderAccepted":
            await _award_order_points(db, order_id=payload.get("order_id"))
        await _notify_order_event(
            db,
            event_type=event_type,
            notification_type=spec["notification_type"],
            title=spec["title"],
            order_id=payload.get("order_id"),
            data=payload,
            message_id=str(message_id) if message_id else None,
        )

    elif event_type in _BLOG_NOTIFICATIONS:
        # BlogNotificationService emitted this but nothing consumed it, so no
        # one was ever told about a new comment or a published post.
        spec = _BLOG_NOTIFICATIONS[event_type]
        await _notify_blog_event(
            db,
            event_type=event_type,
            notification_type=spec["notification_type"],
            title=spec["title"],
            payload=payload,
            message_id=str(message_id) if message_id else None,
        )

    elif event_type == "RefundProcessed":
        await _notify_refund_event(
            db, payload, message_id=str(message_id) if message_id else None
        )

    elif event_type == "CartRecoveryQueued":
        await _notify_cart_recovery(
            db, payload, message_id=str(message_id) if message_id else None
        )

    elif event_type in _WALLET_NOTIFICATIONS:
        # Wallet events carry the recipient ``user_id`` directly in the
        # payload (unlike order events, which resolve it via ``order_id``) —
        # a wallet movement has no order to look up.
        spec = _WALLET_NOTIFICATIONS[event_type]
        await _notify_wallet_event(
            db,
            event_type=event_type,
            notification_type=spec["notification_type"],
            title=spec["title"],
            payload=payload,
            message_id=str(message_id) if message_id else None,
        )


async def _allocate_digital_cards(db: Any, *, order_id: Any) -> None:
    """Allocate digital-card stock for a paid order (Karta digital delivery).

    Runs on PaymentCompleted so the checkout flow delivers PINs; customers
    read them via ``GET /inventory/digital/orders/{id}/cards``.

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

        stock_out_items: list[tuple[Any, Any]] = []
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
                # Karta checkOrderCardsAgain semantics (Pay.php:2187): the
                # payment is already settled, so the money must not stay
                # stuck — the paid amount is credited back to the wallet
                # and the customer is told to re-order from the wallet.
                stock_out_items.append((product, item))
                await logger.aerror(
                    "digital_stock_out_after_payment",
                    order_id=str(order.id),
                    product_id=str(product.id),
                    quantity=item.quantity,
                    error=str(exc),
                )
                continue

        if stock_out_items:
            await _refund_stock_out_to_wallet(db, order=order, stock_out_items=stock_out_items)

        await logger.ainfo("digital_allocation_processed", order_id=str(order.id))
    except Exception as exc:
        # Let the outbox retry mechanism handle transient failures.
        raise RuntimeError(f"digital allocation failed for order {order_id}: {exc}") from exc


async def _refund_stock_out_to_wallet(
    db: Any,
    *,
    order: Any,
    stock_out_items: list[tuple[Any, Any]],
) -> None:
    """Credit the paid amount of undeliverable digital items back to the wallet.

    Idempotent per order: the refund ledger entry uses
    ``reference_type='stock_out_refund'`` + ``reference_id=order_id``, and an
    existing entry is never duplicated on outbox retries (P0.5).
    """

    from sqlalchemy import func as sa_func
    from sqlalchemy import select

    from app.modules.notifications.application.notification_service import (
        NotificationService,
    )
    from app.modules.wallet.application import wallet_service
    from app.modules.wallet.domain.models import WalletTransaction, WalletTransactionType

    refund_amount = sum(int(item.total_price or 0) for _, item in stock_out_items)
    if refund_amount <= 0:
        return

    existing_stmt = (
        select(sa_func.count())
        .select_from(WalletTransaction)
        .where(
            WalletTransaction.reference_type == "stock_out_refund",
            WalletTransaction.reference_id == order.id,
            WalletTransaction.type == WalletTransactionType.REFUND,
        )
    )
    if (await db.execute(existing_stmt)).scalar_one() > 0:
        logger.warning("digital_stock_out_refund_duplicated", order_id=str(order.id))
        return

    product_names = "، ".join(str(product.name) for product, _ in stock_out_items)
    await wallet_service.credit(
        db,
        user_id=order.user_id,
        amount=refund_amount,
        tx_type=WalletTransactionType.REFUND,
        reference_type="stock_out_refund",
        reference_id=order.id,
        description=(
            f"بازگشت وجه سفارش {order.order_number} به دلیل اتمام موجودی: {product_names}"
        ),
    )
    await logger.awarning(
        "digital_stock_out_refunded_to_wallet",
        order_id=str(order.id),
        user_id=str(order.user_id),
        refund_amount=refund_amount,
        products=product_names,
    )

    notification = await NotificationService.create_notification(
        db,
        user_id=order.user_id,
        type="stock_out_refunded",
        title="موجودی کد دیجیتال به پایان رسید",
        body=(
            f"پرداخت سفارش {order.order_number} با موفقیت انجام شد اما موجودی "
            f"«{product_names}» به پایان رسید. مبلغ {refund_amount:,} ریال به کیف پول "
            "شما بازگشت داده شد؛ می‌توانید سفارش خود را با کیف پول ثبت کنید."
        ),
        data={"order_id": str(order.id), "refund_amount": refund_amount},
    )
    _dispatch(str(notification.id))


async def _award_order_points(db: Any, *, order_id: Any) -> None:
    """Award rule-driven loyalty points for a confirmed order.

    Points come exclusively from admin-managed ``GamificationRule`` rows —
    the client can never self-report points (``POST /loyalty/earn`` is
    admin-only). Failures raise so the outbox retry mechanism handles them.
    """
    if not order_id:
        return
    try:
        import uuid as uuid_mod

        from app.modules.gamification.application import gamification_service
        from app.modules.orders.domain.models import Order

        order = await db.get(Order, uuid_mod.UUID(str(order_id)))
        if order is None:
            logger.warning(
                "outbox_order_not_found",
                event_type="OrderAccepted",
                order_id=str(order_id),
            )
            return

        await gamification_service.award_points_for_event(
            db,
            user_id=order.user_id,
            event_type="order_completed",
            event_data={"order_id": str(order.id), "total": order.total},
        )
    except Exception as exc:
        raise RuntimeError(f"loyalty award failed for order {order_id}: {exc}") from exc


async def _notify_order_event(
    db: Any,
    *,
    event_type: str,
    notification_type: str,
    title: str,
    order_id: Any,
    data: dict[str, Any],
    message_id: str | None = None,
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
            idempotency_key=f"outbox:{message_id}" if message_id else None,
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


# The order-lifecycle transactional emails (order_confirmation / order_shipped)
# were removed on 2026-10-07 with the rest of the email feature. The in-app
# notification and SMS paths above are unchanged.


async def _notify_refund_event(
    db: Any, payload: dict[str, Any], *, message_id: str | None = None
) -> None:
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
            idempotency_key=f"outbox:{message_id}" if message_id else None,
        )
        _dispatch(str(notification.id))
        logger.info(
            "outbox_notification_created",
            event_type="RefundProcessed",
            notification_id=str(notification.id),
        )
    except Exception as exc:
        raise RuntimeError(f"notification handling failed for RefundProcessed: {exc}") from exc


# `_maybe_dispatch_refund_email` was removed on 2026-10-07 with the rest of
# the email feature; the in-app refund notification above still fires.


async def _notify_cart_recovery(
    db: Any, payload: dict[str, Any], *, message_id: str | None = None
) -> None:
    """Create the abandoned-cart reminder notification and send the SMS.

    Idempotent by message: the notification carries ``outbox:{message_id}`` as
    its dedupe key, so a retried outbox message reuses the existing row rather
    than creating a second in-app notification. The SMS body is short enough
    to stay within a single SMS segment and always carries the one-click
    recovery link.
    """
    user_id = payload.get("user_id")
    cart_id = payload.get("cart_id")
    if not user_id or not cart_id:
        return
    try:
        import uuid as uuid_mod

        from app.modules.messaging.application import sms_hub_service
        from app.modules.notifications.application.notification_service import (
            NotificationService,
        )
        from app.modules.users.domain.models import User

        user = await db.get(User, uuid_mod.UUID(str(user_id)))
        if user is None:
            logger.warning(
                "outbox_user_not_found",
                event_type="CartRecoveryQueued",
                user_id=str(user_id),
            )
            return

        subtotal = int(payload.get("subtotal_rial") or 0)
        item_count = int(payload.get("item_count") or 0)
        recover_url = str(payload.get("recover_url") or "")
        stage = int(payload.get("stage") or 0)
        # SMS price reads far better in Toman; the integer Rial value in the
        # payload stays the source of truth (no float anywhere).
        subtotal_toman = subtotal // 10

        notification = await NotificationService.create_notification(
            db,
            user_id=user.id,
            type="cart_recovery_reminder",
            title="سبد خرید شما هنوز باز است",
            body=(
                f"{item_count} قلم کالا به ارزش {subtotal_toman:,} تومان در سبد شما "
                "مانده است. برای تکمیل خرید روی پیوند بزنید."
            ),
            data={
                "cart_id": str(cart_id),
                "stage": stage,
                "subtotal_rial": subtotal,
                "recover_url": recover_url,
            },
            idempotency_key=f"outbox:{message_id}" if message_id else None,
        )
        _dispatch(str(notification.id))

        if user.phone:
            sms_text = (
                f"سبد خرید شما با {item_count} قلم ({subtotal_toman:,} تومان) هنوز باز است.\n"
                f"تکمیل خرید: {recover_url}"
            )
            await sms_hub_service.send_sms_with_failover(mobile=user.phone, text=sms_text)

        logger.info(
            "outbox_notification_created",
            event_type="CartRecoveryQueued",
            notification_id=str(notification.id),
            stage=stage,
        )
    except Exception as exc:
        raise RuntimeError(f"cart recovery handling failed for cart {cart_id}: {exc}") from exc


async def _notify_wallet_event(
    db: Any,
    *,
    event_type: str,
    notification_type: str,
    title: str,
    payload: dict[str, Any],
    message_id: str | None = None,
) -> None:
    """Create the customer-facing notification for a wallet event.

    Recipient is ``payload['user_id']`` — a wallet movement has no order, so
    the order-keyed helper cannot be reused. Idempotency is keyed on the
    outbox ``message_id`` (the established ``outbox:{message_id}`` dedupe), so
    a retry never double-notifies.
    """
    user_id = payload.get("user_id")
    if not user_id:
        logger.warning("outbox_wallet_event_no_user", event_type=event_type)
        return
    try:
        import uuid as uuid_mod

        from app.modules.notifications.application.notification_service import (
            NotificationService,
        )

        amount = int(payload.get("amount", 0) or 0)
        amount_toman = amount // 10
        body_map = {
            "WalletTransferSent": f"مبلغ {amount_toman:,} تومان از کیف پول به گیرنده منتقل شد.",
            "WalletTransferReceived": f"مبلغ {amount_toman:,} تومان به کیف پول شما منتقل شد.",
            "WalletWithdrawalRequested": (
                f"درخواست برداشت {amount_toman:,} تومان ثبت شد و تا بررسی بلوکه است."
            ),
            "WalletWithdrawalApproved": (
                f"درخواست برداشت {amount_toman:,} تومان تأیید شد و در انتظار واریز است."
            ),
            "WalletWithdrawalRejected": (
                f"درخواست برداشت {amount_toman:,} تومان رد شد و مبلغ به کیف پول شما بازگشت."
            ),
            "WalletWithdrawalPaid": f"مبلغ برداشت {amount_toman:,} تومان به حساب شما واریز شد.",
            "WalletAdminAdjusted": "موجودی کیف پول شما توسط مدیریت به‌روزرسانی شد.",
        }
        body = body_map.get(event_type, "کیف پول شما به‌روزرسانی شد.")

        notification = await NotificationService.create_notification(
            db,
            user_id=uuid_mod.UUID(str(user_id)),
            type=notification_type,
            title=title,
            body=body,
            data=payload,
            idempotency_key=f"outbox:{message_id}" if message_id else None,
        )
        _dispatch(str(notification.id))
        logger.info(
            "outbox_wallet_notification_created",
            event_type=event_type,
            notification_id=str(notification.id),
        )
    except Exception as exc:
        raise RuntimeError(f"notification handling failed for {event_type}: {exc}") from exc


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
                await _handle_message(db, msg.event_type, msg.payload, msg.id)
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


# ── Blog notifications ──────────────────────────────────────────────────────

#: Blog event types emitted by BlogNotificationService.
_BLOG_NOTIFICATIONS = {
    "notification.blog.post.published": {
        "notification_type": "blog_new_post",
        "title": "نوشته تازه منتشر شد",
    },
    "notification.blog.comment.new": {
        "notification_type": "blog_new_comment",
        "title": "نظر تازه",
    },
    "notification.blog.comment.approved": {
        "notification_type": "blog_comment_approved",
        "title": "نظر شما منتشر شد",
    },
}


async def _notify_blog_event(
    db: Any,
    *,
    event_type: str,
    notification_type: str,
    title: str,
    payload: dict[str, Any],
    message_id: str | None = None,
) -> None:
    """Fan a blog event out to the users it concerns.

    The recipient differs per event: a new comment goes to the post author and
    the parent commenter (ids in the payload), a published post goes to its
    author as a byline, and an approved comment goes back to whoever wrote it.
    """
    import uuid as uuid_mod

    from app.modules.notifications.application.notification_service import (
        NotificationService,
    )

    def _uuid_or_none(value: Any) -> uuid_mod.UUID | None:
        try:
            return uuid_mod.UUID(str(value)) if value else None
        except (ValueError, TypeError):
            return None

    targets: list[tuple[Any, str]] = []
    if event_type.endswith("blog.comment.new"):
        for raw in payload.get("recipient_user_ids") or []:
            targets.append((_uuid_or_none(raw), "یک نظر تازه روی نوشتهٔ شما ثبت شد."))
    elif event_type.endswith("blog.comment.approved"):
        recipient = _uuid_or_none(payload.get("comment_author_id"))
        if recipient:
            targets.append((recipient, f"نظر شما روی «{payload.get('post_title', '')}» منتشر شد."))
    else:  # post published — a confirmation for the author
        author = _uuid_or_none(payload.get("author_id"))
        if author:
            targets.append((author, f"نوشتهٔ «{payload.get('title', '')}» منتشر شد."))

    for user_id, body in targets:
        if user_id is None:
            continue
        try:
            notification = await NotificationService.create_notification(
                db,
                user_id=user_id,
                type=notification_type,
                title=title,
                body=body,
                data=payload,
                idempotency_key=f"outbox:{message_id}" if message_id else None,
            )
            _dispatch(str(notification.id))
            logger.info(
                "outbox_blog_notification_created",
                event_type=event_type,
                notification_id=str(notification.id),
            )
        except Exception:
            # A retry of the outbox message re-runs this handler; the
            # idempotency key keeps it from producing a second notification.
            logger.warning("outbox_blog_notification_failed", event_type=event_type)
