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
    await db.flush()

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
        payment.status = PaymentStatus.PROCESSING
        await db.flush()

        await logger.ainfo(
            "payment_create_success",
            payment_id=str(payment.id),
            authority=gateway_result.authority,
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
    if status.upper() not in ("OK", "100", "101", "TRUE", "SUCCESS"):
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

    authority = callback_data.authority or callback_data.id
    await logger.ainfo(
        "payment_callback_received",
        provider=provider,
        authority=authority,
    )

    if not authority:
        raise ValidationError(
            detail="Callback data missing authority/id",
            error_code="MISSING_AUTHORITY",
        )

    # Look up payment by authority
    stmt = select(Payment).where(Payment.authority == authority)
    result = await db.execute(stmt)
    payment = result.scalar_one_or_none()

    if payment is None:
        raise NotFoundError(
            resource="Payment",
            detail=f"No payment found for authority '{authority}'",
        )

    if payment.status == PaymentStatus.COMPLETED:
        await logger.ainfo(
            "payment_callback_already_completed",
            payment_id=str(payment.id),
        )
        return PaymentResponse.model_validate(payment)

    # Verify with the provider
    callback_status = callback_data.status or ""
    return await verify_payment(
        db,
        payment_id=payment.id,
        authority=authority,
        status=callback_status,
    )


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

    payment = await _get_payment_or_raise(db, payment_id)

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

    # Check total existing refunds
    stmt = (
        select(Refund)
        .where(Refund.payment_id == payment_id)
        .where(Refund.status.in_([RefundStatus.PENDING, RefundStatus.APPROVED, RefundStatus.PROCESSED]))
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
    refund_result = await gateway_provider.refund(
        authority=payment.authority or "",
        amount=amount,
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
) -> PaymentResponse:
    """Fetch a single payment by ID."""
    payment = await _get_payment_or_raise(db, payment_id)
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
        ),
        PaymentMethodInfo(
            provider=PaymentProviderEnum.IDPAY,
            name="IDPay",
            name_fa="آی‌دی‌پی",
            is_enabled=(settings.PAYMENT_PROVIDER == "idpay" or settings.ENVIRONMENT == "development"),
            icon="idpay",
            description="Online payment via IDPay gateway",
        ),
        PaymentMethodInfo(
            provider=PaymentProviderEnum.WALLET,
            name="Wallet",
            name_fa="کیف پول",
            is_enabled=True,
            icon="wallet",
            description="Pay using your wallet balance",
        ),
    ]

    # In development / sandbox mode, include the mock provider
    if settings.ENVIRONMENT == "development" or settings.PAYMENT_SANDBOX:
        methods.append(
            PaymentMethodInfo(
                provider=PaymentProviderEnum.CARD_TRANSFER,
                name="Mock (Dev)",
                name_fa="تست (توسعه)",
                is_enabled=True,
                icon="mock",
                description="Mock payment provider for development",
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
