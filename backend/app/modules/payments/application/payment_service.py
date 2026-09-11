"""Payment application service.

Orchestrates payment creation, verification, callback handling, and refunds.
Every public function is an async entry point designed to be called from API
route handlers.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import structlog
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.settings import get_settings
from app.core.exceptions.handlers import (
    ConflictError,
    NotFoundError,
    PaymentError,
    ValidationError,
)
from app.modules.payments.domain.models import (
    Payment,
    PaymentProvider as PaymentProviderEnum,
    PaymentStatus,
    PaymentTransaction,
    PaymentTransactionType,
    PaymentWebhookEvent,
    Refund,
    RefundStatus,
)
from app.modules.payments.infrastructure.provider_factory import (
    get_payment_provider,
)
from app.modules.payments.schemas.payment import (
    PaymentCallbackData,
    PaymentMethodInfo,
    PaymentMethodsResponse,
    PaymentResponse,
    RefundResponse,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────


def _build_callback_url(provider: str, payment_id: uuid.UUID) -> str:
    """Build the callback URL that the gateway will redirect to."""
    settings = get_settings()
    base = settings.PAYMENT_CALLBACK_BASE_URL.rstrip("/")
    return f"{base}/{provider}/{payment_id}"


async def _record_transaction(
    db: AsyncSession,
    *,
    payment_id: uuid.UUID,
    amount: int,
    tx_type: PaymentTransactionType,
    status: str,
    provider_response: dict[str, Any] | None = None,
) -> PaymentTransaction:
    """Insert an audit transaction row for a payment operation."""
    tx = PaymentTransaction(
        payment_id=payment_id,
        amount=amount,
        type=tx_type,
        status=status,
        provider_response=provider_response,
    )
    db.add(tx)
    await db.flush()
    return tx


# ── Public Service Functions ──────────────────────────────────────────────


async def create_payment(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    order_id: uuid.UUID,
    provider: str,
    amount: int,
    idempotency_key: str | None = None,
    description: str = "",
    mobile: str | None = None,
    email: str | None = None,
) -> PaymentResponse:
    """Create a payment record and obtain the gateway URL.

    Idempotency
    ------------
    When ``idempotency_key`` is supplied and a payment with the same key
    already exists, the existing payment is returned instead of creating
    a duplicate.
    """

    await logger.ainfo(
        "payment_create_start",
        user_id=str(user_id),
        order_id=str(order_id),
        provider=provider,
        amount=amount,
        idempotency_key=idempotency_key,
    )

    # ── Idempotency check ─────────────────────────────────────────────
    if idempotency_key:
        stmt = select(Payment).where(Payment.idempotency_key == idempotency_key)
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing is not None:
            await logger.ainfo(
                "payment_create_idempotent_hit",
                payment_id=str(existing.id),
                idempotency_key=idempotency_key,
            )
            return PaymentResponse.model_validate(existing)

    # ── Validate provider ─────────────────────────────────────────────
    try:
        provider_enum = PaymentProviderEnum(provider.lower())
    except ValueError:
        raise ValidationError(
            detail=f"Unsupported payment provider: {provider}",
            error_code="INVALID_PROVIDER",
        )

    # ── Create payment record ─────────────────────────────────────────
    payment = Payment(
        order_id=order_id,
        amount=amount,
        provider=provider_enum,
        status=PaymentStatus.PENDING,
        idempotency_key=idempotency_key,
    )
    db.add(payment)
    try:
        await db.flush()
    except IntegrityError:
        if idempotency_key:
            stmt = select(Payment).where(Payment.idempotency_key == idempotency_key)
            result = await db.execute(stmt)
            existing = result.scalar_one_or_none()
            if existing is not None:
                await logger.ainfo(
                    "payment_create_idempotent_race_recovered",
                    payment_id=str(existing.id),
                    idempotency_key=idempotency_key,
                )
                return PaymentResponse.model_validate(existing)
        raise

    # ── Call gateway provider ─────────────────────────────────────────
    try:
        gateway_provider = get_payment_provider(provider.lower())
    except ValueError as exc:
        raise ValidationError(detail=str(exc), error_code="INVALID_PROVIDER")

    callback_url = _build_callback_url(provider.lower(), payment.id)

    gateway_result = await gateway_provider.create_payment(
        amount=amount,
        order_id=order_id,
        callback_url=callback_url,
        description=description,
        mobile=mobile,
        email=email,
    )

    # ── Record transaction ────────────────────────────────────────────
    await _record_transaction(
        db,
        payment_id=payment.id,
        amount=amount,
        tx_type=PaymentTransactionType.CHARGE,
        status="success" if gateway_result.success else "failed",
        provider_response=gateway_result.raw_response,
    )

    if gateway_result.success:
        payment.authority = gateway_result.authority
        payment.gateway_url = gateway_result.gateway_url
        payment.extra_data = gateway_result.raw_response
        if provider_enum == PaymentProviderEnum.CARD_TRANSFER:
            payment.status = PaymentStatus.PENDING
        else:
            payment.status = PaymentStatus.PROCESSING
        await db.flush()

        await logger.ainfo(
            "payment_create_success",
            payment_id=str(payment.id),
            authority=gateway_result.authority,
            status=payment.status.value,
        )
    else:
        payment.status = PaymentStatus.FAILED
        payment.extra_data = {
            "error_code": gateway_result.error_code,
            "error_message": gateway_result.error_message,
        }
        await db.flush()

        await logger.awarning(
            "payment_create_gateway_failed",
            payment_id=str(payment.id),
            error_code=gateway_result.error_code,
            error_message=gateway_result.error_message,
        )
        raise PaymentError(
            detail=gateway_result.error_message or "Payment gateway error",
            error_code="GATEWAY_ERROR",
        )

    return PaymentResponse.model_validate(payment)


async def verify_payment(
    db: AsyncSession,
    *,
    payment_id: uuid.UUID,
    authority: str,
    status: str,
) -> PaymentResponse:
    """Verify a payment with the gateway after the user returns.

    Parameters
    ----------
    payment_id:
        The internal payment UUID.
    authority:
        The authority / token returned by the gateway.
    status:
        The status string from the gateway callback query parameters.
    """

    await logger.ainfo(
        "payment_verify_start",
        payment_id=str(payment_id),
        authority=authority,
        callback_status=status,
    )

    payment = await _get_payment_or_raise(db, payment_id)

    # Ensure the payment is in a verifiable state
    if payment.status == PaymentStatus.COMPLETED:
        await logger.ainfo(
            "payment_verify_already_completed",
            payment_id=str(payment_id),
        )
        return PaymentResponse.model_validate(payment)

    if payment.status not in (PaymentStatus.PENDING, PaymentStatus.PROCESSING):
        raise ValidationError(
            detail=f"Payment is in non-verifiable status: {payment.status.value}",
            error_code="PAYMENT_NOT_VERIFIABLE",
        )

    # If the callback status indicates failure, mark it and return
    if status and status.upper() not in (
        "OK",
        "100",
        "101",
        "TRUE",
        "SUCCESS",
        "FINISHED",
        "CONFIRMED",
        "COMPLETED",
        "SENDING",
    ):
        payment.status = PaymentStatus.FAILED
        payment.extra_data = {
            **(payment.extra_data or {}),
            "callback_status": status,
        }
        await _record_transaction(
            db,
            payment_id=payment.id,
            amount=payment.amount,
            tx_type=PaymentTransactionType.VERIFY,
            status="user_cancelled",
            provider_response={"callback_status": status},
        )
        await db.flush()

        await logger.awarning(
            "payment_verify_user_cancelled",
            payment_id=str(payment_id),
            callback_status=status,
        )
        raise PaymentError(
            detail="Payment was cancelled or failed at the gateway",
            error_code="PAYMENT_CANCELLED",
        )

    # ── Verify with the provider ──────────────────────────────────────
    gateway_provider = get_payment_provider(payment.provider.value)
    result = await gateway_provider.verify_payment(
        authority=authority or payment.authority or "",
        amount=payment.amount,
    )

    await _record_transaction(
        db,
        payment_id=payment.id,
        amount=payment.amount,
        tx_type=PaymentTransactionType.VERIFY,
        status="success" if result.success else "failed",
        provider_response=result.raw_response,
    )

    if result.success:
        payment.status = PaymentStatus.COMPLETED
        payment.provider_transaction_id = result.ref_id
        payment.extra_data = {
            **(payment.extra_data or {}),
            "ref_id": result.ref_id,
            "card_pan": result.card_pan,
        }

        # Transition associated order from PENDING to CONFIRMED
        if payment.order_id:
            from app.modules.orders.domain.models import Order, OrderStatus, OrderStatusHistory
            order_stmt = select(Order).where(Order.id == payment.order_id).with_for_update()
            order = (await db.execute(order_stmt)).scalar_one_or_none()
            if order and order.status == OrderStatus.PENDING:
                order.status = OrderStatus.CONFIRMED
                history = OrderStatusHistory(
                    order_id=order.id,
                    from_status=OrderStatus.PENDING.value,
                    to_status=OrderStatus.CONFIRMED.value,
                    changed_by=None,
                    reason=f"Payment verified via {payment.provider.value} (ref: {result.ref_id})",
                )
                db.add(history)

        await db.flush()

        await logger.ainfo(
            "payment_verify_success",
            payment_id=str(payment_id),
            ref_id=result.ref_id,
        )
    else:
        payment.status = PaymentStatus.FAILED
        payment.extra_data = {
            **(payment.extra_data or {}),
            "verify_error_code": result.error_code,
            "verify_error_message": result.error_message,
        }
        await db.flush()

        await logger.awarning(
            "payment_verify_gateway_failed",
            payment_id=str(payment_id),
            error_code=result.error_code,
        )
        raise PaymentError(
            detail=result.error_message or "Payment verification failed",
            error_code="VERIFICATION_FAILED",
        )

    return PaymentResponse.model_validate(payment)


async def process_callback(
    db: AsyncSession,
    *,
    provider: str,
    callback_data: PaymentCallbackData,
) -> PaymentResponse:
    """Handle an asynchronous webhook / callback from a payment provider.

    The function attempts to identify the payment via the authority or ID
    sent in the callback payload.
    """

    authority = (
        callback_data.authority
        or callback_data.id
        or (str(callback_data.payment_id) if callback_data.payment_id is not None else None)
    )
    await logger.ainfo(
        "payment_callback_received",
        provider=provider,
        authority=authority,
        order_id=callback_data.order_id,
    )

    # Look up payment by authority or provider_transaction_id or order_id with row lock
    payment: Optional[Payment] = None
    if authority:
        stmt = select(Payment).where(Payment.authority == authority).with_for_update()
        result = await db.execute(stmt)
        payment = result.scalar_one_or_none()

        if payment is None:
            stmt = select(Payment).where(Payment.provider_transaction_id == authority).with_for_update()
            result = await db.execute(stmt)
            payment = result.scalar_one_or_none()

    if payment is None and callback_data.order_id:
        try:
            order_uuid = uuid.UUID(str(callback_data.order_id))
            stmt = select(Payment).where(Payment.order_id == order_uuid).order_by(Payment.created_at.desc()).with_for_update()
            result = await db.execute(stmt)
            payment = result.scalars().first()
            if payment and not authority:
                authority = payment.authority or str(payment.id)
        except Exception:
            pass

    if payment is None:
        raise NotFoundError(
            resource="Payment",
            detail=f"No payment found for authority/id '{authority or callback_data.order_id}'",
        )

    event_id = authority or str(callback_data.order_id or payment.id)

    # ── Replay & Idempotency check via PaymentWebhookEvent ───────────
    webhook_stmt = (
        select(PaymentWebhookEvent)
        .where(
            PaymentWebhookEvent.provider == provider,
            PaymentWebhookEvent.event_id == event_id,
        )
        .with_for_update()
    )
    webhook_result = await db.execute(webhook_stmt)
    webhook_event = webhook_result.scalar_one_or_none()

    if webhook_event and webhook_event.processed:
        await logger.ainfo(
            "payment_webhook_already_processed",
            provider=provider,
            event_id=event_id,
            payment_id=str(payment.id),
        )
        return PaymentResponse.model_validate(payment)

    if webhook_event is None:
        webhook_event = PaymentWebhookEvent(
            provider=provider,
            event_id=event_id,
            payment_id=payment.id,
            payload=callback_data.model_dump(mode="json"),
            processed=False,
        )
        db.add(webhook_event)
        await db.flush()

    if payment.status == PaymentStatus.COMPLETED:
        await logger.ainfo(
            "payment_callback_already_completed",
            payment_id=str(payment.id),
        )
        webhook_event.processed = True
        webhook_event.processed_at = datetime.now(timezone.utc)
        await db.flush()
        return PaymentResponse.model_validate(payment)

    # Verify with the provider
    callback_status = callback_data.status or ""
    try:
        response = await verify_payment(
            db,
            payment_id=payment.id,
            authority=authority,
            status=callback_status,
        )
        webhook_event.processed = True
        webhook_event.processed_at = datetime.now(timezone.utc)
        await db.flush()
        return response
    except Exception as exc:
        webhook_event.error = str(exc)
        await db.flush()
        raise


async def refund_payment(
    db: AsyncSession,
    *,
    payment_id: uuid.UUID,
    amount: int,
    reason: str | None = None,
    actor_id: uuid.UUID,
) -> RefundResponse:
    """Process a refund for a completed payment.

    Parameters
    ----------
    payment_id:
        The payment to refund.
    amount:
        Refund amount in IRR. Must be <= the original payment amount.
    reason:
        Optional reason text.
    actor_id:
        UUID of the admin / user processing the refund.
    """

    await logger.ainfo(
        "payment_refund_start",
        payment_id=str(payment_id),
        amount=amount,
        actor_id=str(actor_id),
    )

    stmt_lock = select(Payment).where(Payment.id == payment_id).with_for_update()
    payment = (await db.execute(stmt_lock)).scalar_one_or_none()
    if payment is None:
        raise NotFoundError(resource="Payment")

    if payment.status != PaymentStatus.COMPLETED:
        raise ValidationError(
            detail="Only completed payments can be refunded",
            error_code="PAYMENT_NOT_COMPLETED",
        )

    if amount > payment.amount:
        raise ValidationError(
            detail=(
                f"Refund amount ({amount}) exceeds payment amount ({payment.amount})"
            ),
            error_code="REFUND_EXCEEDS_PAYMENT",
        )

    # Check total existing refunds with row locks
    stmt = (
        select(Refund)
        .where(Refund.payment_id == payment_id)
        .where(Refund.status.in_([RefundStatus.PENDING, RefundStatus.APPROVED, RefundStatus.PROCESSED]))
        .with_for_update()
    )
    result = await db.execute(stmt)
    existing_refunds = result.scalars().all()
    total_refunded = sum(r.amount for r in existing_refunds)

    if total_refunded + amount > payment.amount:
        raise ValidationError(
            detail=(
                f"Total refund amount ({total_refunded + amount}) "
                f"would exceed payment amount ({payment.amount})"
            ),
            error_code="REFUND_TOTAL_EXCEEDS_PAYMENT",
        )

    # ── Attempt provider refund ───────────────────────────────────────
    gateway_provider = get_payment_provider(payment.provider.value)

    # Resolve customer user ID from order if possible for wallet refund
    customer_user_id: Optional[uuid.UUID] = None
    try:
        from app.modules.orders.domain.models import Order
        stmt_order = select(Order.user_id).where(Order.id == payment.order_id)
        res_order = await db.execute(stmt_order)
        customer_user_id = res_order.scalar_one_or_none()
    except Exception:
        pass

    refund_result = await gateway_provider.refund(
        authority=payment.authority or "",
        amount=amount,
        user_id=customer_user_id or actor_id,
        db=db,
    )

    # ── Record transaction ────────────────────────────────────────────
    await _record_transaction(
        db,
        payment_id=payment.id,
        amount=amount,
        tx_type=PaymentTransactionType.REFUND,
        status="success" if refund_result.success else "pending_manual",
        provider_response=refund_result.raw_response,
    )

    # ── Create refund record ──────────────────────────────────────────
    refund_status = RefundStatus.PROCESSED if refund_result.success else RefundStatus.APPROVED
    refund = Refund(
        payment_id=payment.id,
        order_id=payment.order_id,
        amount=amount,
        reason=reason,
        status=refund_status,
        processed_by=actor_id,
        processed_at=datetime.now(timezone.utc) if refund_result.success else None,
    )
    db.add(refund)

    # Update payment status if fully refunded
    if total_refunded + amount >= payment.amount:
        payment.status = PaymentStatus.REFUNDED
        if payment.order_id:
            from app.modules.orders.domain.models import Order, OrderStatus, OrderStatusHistory
            order_lock = select(Order).where(Order.id == payment.order_id).with_for_update()
            order = (await db.execute(order_lock)).scalar_one_or_none()
            if order and order.status not in (OrderStatus.CANCELED, OrderStatus.REFUNDED):
                order.status = OrderStatus.REFUNDED
                history = OrderStatusHistory(
                    order_id=order.id,
                    from_status=order.status.value,
                    to_status=OrderStatus.REFUNDED.value,
                    changed_by=actor_id,
                    reason=f"Full refund processed for payment {payment.id}",
                )
                db.add(history)
    await db.flush()

    await logger.ainfo(
        "payment_refund_recorded",
        payment_id=str(payment_id),
        refund_id=str(refund.id),
        refund_status=refund_status.value,
        provider_success=refund_result.success,
    )

    return RefundResponse.model_validate(refund)


async def get_payment(
    db: AsyncSession,
    *,
    payment_id: uuid.UUID,
    user_id: uuid.UUID | None = None,
) -> PaymentResponse:
    """Fetch a single payment by ID, validating ownership if user_id is provided."""
    payment = await _get_payment_or_raise(db, payment_id)
    if user_id and payment.order_id:
        from app.modules.orders.domain.models import Order
        order_stmt = select(Order).where(Order.id == payment.order_id)
        result = await db.execute(order_stmt)
        order = result.scalar_one_or_none()
        if isinstance(order, Order) and order.user_id != user_id:
            raise NotFoundError(resource="Payment")
    return PaymentResponse.model_validate(payment)


async def submit_card_receipt(
    db: AsyncSession,
    *,
    payment_id: uuid.UUID,
    user_id: uuid.UUID,
    tracking_code: str,
    card_pan: str | None = None,
    receipt_image_url: str | None = None,
    notes: str | None = None,
) -> PaymentResponse:
    """Submit transaction reference / tracking code for a card-to-card payment.

    Updates payment extra_data and keeps the status in PENDING waiting
    for administrator approval.
    """
    payment = await _get_payment_or_raise(db, payment_id)

    if payment.order_id:
        from app.modules.orders.domain.models import Order
        order_stmt = select(Order).where(Order.id == payment.order_id)
        result = await db.execute(order_stmt)
        order = result.scalar_one_or_none()
        if isinstance(order, Order) and order.user_id != user_id:
            raise NotFoundError(resource="Payment")

    if payment.provider != PaymentProviderEnum.CARD_TRANSFER:
        raise ValidationError(
            detail="Receipt submission is only applicable for card-to-card transfers",
            error_code="INVALID_PROVIDER_FOR_RECEIPT",
        )

    if payment.status not in (PaymentStatus.PENDING, PaymentStatus.PROCESSING):
        raise ValidationError(
            detail=f"Cannot submit receipt for payment in status: {payment.status.value}",
            error_code="INVALID_PAYMENT_STATUS",
        )

    extra = dict(payment.extra_data or {})
    extra.update({
        "tracking_code": tracking_code,
        "card_pan": card_pan,
        "customer_card_pan": card_pan,
        "receipt_image_url": receipt_image_url,
        "customer_notes": notes,
        "receipt_submitted_at": datetime.now(timezone.utc).isoformat(),
        "submitted_by": str(user_id),
        "card_transfer_status": "pending_admin_approval",
    })
    payment.extra_data = extra
    payment.status = PaymentStatus.PENDING
    payment.provider_transaction_id = tracking_code
    if card_pan and not payment.authority:
        payment.authority = f"C2C-{tracking_code}"

    await _record_transaction(
        db,
        payment_id=payment.id,
        amount=payment.amount,
        tx_type=PaymentTransactionType.CHARGE,
        status="receipt_submitted",
        provider_response={
            "tracking_code": tracking_code,
            "card_pan": card_pan,
            "receipt_image_url": receipt_image_url,
        },
    )
    await db.flush()

    await logger.ainfo(
        "card_receipt_submitted",
        payment_id=str(payment_id),
        tracking_code=tracking_code,
        user_id=str(user_id),
    )

    return PaymentResponse.model_validate(payment)


async def approve_payment(
    db: AsyncSession,
    *,
    payment_id: uuid.UUID,
    admin_user_id: uuid.UUID,
) -> PaymentResponse:
    """Admin approval of a pending payment (e.g. card-to-card)."""
    payment = await _get_payment_or_raise(db, payment_id)

    if payment.status == PaymentStatus.COMPLETED:
        return PaymentResponse.model_validate(payment)

    if payment.status != PaymentStatus.PENDING:
        raise ValidationError(
            detail=f"Only pending payments can be approved (current: {payment.status.value})",
            error_code="PAYMENT_NOT_PENDING",
        )

    extra = dict(payment.extra_data or {})
    extra["approved_by"] = str(admin_user_id)
    extra["approved_at"] = datetime.now(timezone.utc).isoformat()
    extra["card_transfer_status"] = "approved"

    payment.status = PaymentStatus.COMPLETED
    if not payment.provider_transaction_id:
        payment.provider_transaction_id = extra.get("tracking_code") or payment.authority or f"C2C-{payment.id.hex[:8]}"
    payment.extra_data = extra

    # Transition associated order from PENDING to CONFIRMED on admin approval
    if payment.order_id:
        from app.modules.orders.domain.models import Order, OrderStatus, OrderStatusHistory
        order_stmt = select(Order).where(Order.id == payment.order_id).with_for_update()
        order = (await db.execute(order_stmt)).scalar_one_or_none()
        if order and order.status == OrderStatus.PENDING:
            order.status = OrderStatus.CONFIRMED
            history = OrderStatusHistory(
                order_id=order.id,
                from_status=OrderStatus.PENDING.value,
                to_status=OrderStatus.CONFIRMED.value,
                changed_by=admin_user_id,
                reason=f"Admin approved payment (ref: {payment.provider_transaction_id})",
            )
            db.add(history)

    await _record_transaction(
        db,
        payment_id=payment.id,
        amount=payment.amount,
        tx_type=PaymentTransactionType.VERIFY,
        status="admin_approved",
        provider_response={"approved_by": str(admin_user_id)},
    )
    await db.flush()

    await logger.ainfo(
        "payment_admin_approved",
        payment_id=str(payment_id),
        admin_user_id=str(admin_user_id),
    )

    return PaymentResponse.model_validate(payment)


async def reject_payment(
    db: AsyncSession,
    *,
    payment_id: uuid.UUID,
    admin_user_id: uuid.UUID,
    reason: str | None = None,
) -> PaymentResponse:
    """Admin rejection of a pending payment (e.g. card-to-card)."""
    payment = await _get_payment_or_raise(db, payment_id)

    if payment.status in (PaymentStatus.COMPLETED, PaymentStatus.REFUNDED):
        raise ValidationError(
            detail=f"Cannot reject payment in status: {payment.status.value}",
            error_code="PAYMENT_CANNOT_BE_REJECTED",
        )

    extra = dict(payment.extra_data or {})
    extra["rejected_by"] = str(admin_user_id)
    extra["rejection_reason"] = reason or "Payment rejected by admin"
    extra["rejected_at"] = datetime.now(timezone.utc).isoformat()
    extra["card_transfer_status"] = "rejected"

    payment.status = PaymentStatus.FAILED
    payment.extra_data = extra

    await _record_transaction(
        db,
        payment_id=payment.id,
        amount=payment.amount,
        tx_type=PaymentTransactionType.VERIFY,
        status="admin_rejected",
        provider_response={
            "rejected_by": str(admin_user_id),
            "reason": reason,
        },
    )
    await db.flush()

    await logger.ainfo(
        "payment_admin_rejected",
        payment_id=str(payment_id),
        admin_user_id=str(admin_user_id),
        reason=reason,
    )

    return PaymentResponse.model_validate(payment)


def get_payment_methods() -> PaymentMethodsResponse:
    """Return the list of available payment methods."""
    settings = get_settings()

    methods = [
        PaymentMethodInfo(
            provider=PaymentProviderEnum.ZARINPAL,
            name="Zarinpal",
            name_fa="زرین‌پال",
            is_enabled=(settings.PAYMENT_PROVIDER == "zarinpal" or settings.ENVIRONMENT == "development"),
            icon="zarinpal",
            description="Online payment via Zarinpal gateway",
            instructions="پرداخت آنلاین از طریق کلیه کارت‌های عضو شتاب با درگاه زرین‌پال",
            instructions_fa="پرداخت آنلاین از طریق کلیه کارت‌های عضو شتاب با درگاه زرین‌پال",
        ),
        PaymentMethodInfo(
            provider=PaymentProviderEnum.IDPAY,
            name="IDPay",
            name_fa="آی‌دی‌پی",
            is_enabled=(settings.PAYMENT_PROVIDER == "idpay" or settings.ENVIRONMENT == "development"),
            icon="idpay",
            description="Online payment via IDPay gateway",
            instructions="پرداخت آنلاین امن از طریق درگاه پرداخت آی‌دی‌پی",
            instructions_fa="پرداخت آنلاین امن از طریق درگاه پرداخت آی‌دی‌پی",
        ),
        PaymentMethodInfo(
            provider=PaymentProviderEnum.CRYPTO,
            name="Cryptocurrency (NowPayments / USDT)",
            name_fa="ارز دیجیتال (تتر / بیت‌کوین)",
            is_enabled=True,
            icon="crypto",
            description="Pay using USDT (TRC20/ERC20), BTC, or ETH via NowPayments",
            instructions="پرداخت امن با رمزارزهای تتر (USDT-TRC20/ERC20)، بیت‌کوین و اتریوم از طریق درگاه NowPayments همراه با تولید خودکار آدرس و QR Code",
            instructions_fa="پرداخت امن با رمزارزهای تتر (USDT-TRC20/ERC20)، بیت‌کوین و اتریوم از طریق درگاه NowPayments همراه با تولید خودکار آدرس و QR Code",
        ),
        PaymentMethodInfo(
            provider=PaymentProviderEnum.CARD_TRANSFER,
            name="Card to Card",
            name_fa="کارت به کارت",
            is_enabled=True,
            icon="credit-card",
            description="Direct card to card bank transfer",
            instructions=f"انتقال وجه به کارت شماره {settings.CARD_TO_CARD_NUMBER} ({settings.CARD_TO_CARD_BANK} - {settings.CARD_TO_CARD_HOLDER}) و ثبت کد پیگیری فیش",
            instructions_fa=f"انتقال وجه به کارت شماره {settings.CARD_TO_CARD_NUMBER} ({settings.CARD_TO_CARD_BANK} - {settings.CARD_TO_CARD_HOLDER}) و ثبت کد پیگیری فیش",
        ),
        PaymentMethodInfo(
            provider=PaymentProviderEnum.WALLET,
            name="Wallet",
            name_fa="کیف پول",
            is_enabled=True,
            icon="wallet",
            description="Pay using your wallet balance",
            instructions="پرداخت سریع از موجودی حساب کیف پول شما",
            instructions_fa="پرداخت سریع از موجودی حساب کیف پول شما",
        ),
    ]

    # In development / sandbox mode, include the mock provider
    if settings.ENVIRONMENT == "development" or settings.PAYMENT_SANDBOX:
        methods.append(
            PaymentMethodInfo(
                provider=PaymentProviderEnum.MOCK,
                name="Mock (Dev)",
                name_fa="تست (توسعه)",
                is_enabled=True,
                icon="mock",
                description="Mock payment provider for development and testing",
                instructions="درگاه آزمایشی توسعه‌دهندگان",
                instructions_fa="درگاه آزمایشی توسعه‌دهندگان",
            )
        )

    return PaymentMethodsResponse(methods=methods)


# ── Internal Helpers ──────────────────────────────────────────────────────


async def _get_payment_or_raise(
    db: AsyncSession,
    payment_id: uuid.UUID,
) -> Payment:
    """Fetch a payment by primary key or raise ``NotFoundError``."""
    stmt = select(Payment).where(Payment.id == payment_id)
    result = await db.execute(stmt)
    payment = result.scalar_one_or_none()
    if payment is None:
        raise NotFoundError(resource="Payment")
    return payment
