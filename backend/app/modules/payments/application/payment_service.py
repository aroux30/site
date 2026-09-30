"""Payment application service.

Orchestrates payment creation, verification, callback handling, and refunds.
Every public function is an async entry point designed to be called from API
route handlers.
"""

from __future__ import annotations

import contextlib
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.config.settings import get_settings
from app.core.exceptions.handlers import (
    ConflictError,
    NotFoundError,
    PaymentError,
    ValidationError,
)
from app.core.observability.tracer import get_tracer
from app.core.security.data_protection import mask_card_pan
from app.modules.payments.domain.models import (
    Payment,
    PaymentStatus,
    PaymentTransaction,
    PaymentTransactionType,
    PaymentWebhookEvent,
    Refund,
    RefundStatus,
)
from app.modules.payments.domain.models import (
    PaymentProvider as PaymentProviderEnum,
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
from app.modules.settings.application.settings_service import SettingsService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────


async def _resolve_gateway(db: AsyncSession, provider_name: str) -> tuple[Any, str | None]:
    """Resolve the active gateway provider.

    A Zarinpal merchant id registered through the admin settings UI takes
    priority: as soon as one is saved, the gateway switches to Zarinpal
    without a redeploy. Otherwise the configured env provider is used.

    Returns ``(provider, override_merchant_id)`` so the caller can pin the
    credential snapshot on the payment row (verification must use the same
    credentials the payment was created with).
    """
    name = (provider_name or get_settings().PAYMENT_PROVIDER).lower().strip()
    if name in ("zarinpal", "card_transfer", "card_to_card", "c2c", "card"):
        try:
            setting = await SettingsService.get_by_key(db, "payment.zarinpal.merchant_id")
        except NotFoundError:
            setting = None
        if setting and setting.value:
            raw = setting.value
            value = raw.get("merchant_id") if isinstance(raw, dict) else raw
            merchant_id = str(value or "").strip()
            if merchant_id:
                return get_payment_provider("zarinpal", merchant_id=merchant_id), merchant_id
    return get_payment_provider(name), None


async def _resolve_gateway_for_payment(db: AsyncSession, payment: Payment) -> Any:
    """Resolve the gateway using the credential snapshot taken at creation.

    Payments created under an admin-configured Zarinpal merchant override
    must be verified/refunded with that same merchant id, not whichever
    merchant id happens to be configured at verification time. Payments
    without a snapshot (legacy rows) keep the plain env configuration.
    """
    snapshot = (payment.extra_data or {}).get("zarinpal_merchant_id")
    if snapshot:
        return get_payment_provider("zarinpal", merchant_id=str(snapshot))
    return get_payment_provider(payment.provider.value)


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


async def _payment_belongs_to_user(
    db: AsyncSession,
    payment: Payment,
    user_id: uuid.UUID,
) -> bool:
    """Whether the payment is owned by the user.

    Order payments are owned via the order; wallet top-ups via the
    ``extra_data.wallet_user_id`` snapshot recorded at creation time.
    """
    extra = payment.extra_data or {}
    if payment.order_id:
        from app.modules.orders.domain.models import Order

        order = await db.get(Order, payment.order_id)
        return order is not None and order.user_id == user_id
    if extra.get("purpose") == "wallet_topup":
        return extra.get("wallet_user_id") == str(user_id)
    return False


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
            # Idempotency keys are scoped per user: another user's payment
            # (amount, authority, gateway URL) must never be returned here.
            if not await _payment_belongs_to_user(db, existing, user_id):
                raise NotFoundError(resource="Payment")
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
        ) from None

    # ── Validate order: ownership, payable state, and amount ─────────
    # The order total is the single authoritative source for the payable
    # amount; a client-supplied amount is never trusted on its own.
    # The order row is locked so two concurrent creates cannot both pass the
    # active-payment check below and double-charge the gateway.
    from app.modules.orders.domain.models import Order, OrderStatus

    order = await db.get(Order, order_id, with_for_update=True)
    if order is None or order.user_id != user_id:
        raise NotFoundError(resource="Order")

    if order.status != OrderStatus.PENDING:
        raise ConflictError(
            detail=(f"Order {order_id} is not payable in status '{order.status.value}'"),
            error_code="ORDER_NOT_PAYABLE",
        )

    # One live payment per order: retries are only possible after the
    # previous attempt FAILED.
    active_payment_stmt = (
        select(Payment.id)
        .where(
            Payment.order_id == order_id,
            Payment.status.in_(
                [PaymentStatus.PENDING, PaymentStatus.PROCESSING, PaymentStatus.COMPLETED]
            ),
        )
        .limit(1)
    )
    if (await db.execute(active_payment_stmt)).scalar_one_or_none() is not None:
        raise ConflictError(
            detail="An active payment already exists for this order",
            error_code="PAYMENT_ALREADY_EXISTS",
        )

    if amount != order.total:
        raise ValidationError(
            detail=(f"Payment amount ({amount}) does not match the order total ({order.total})"),
            error_code="AMOUNT_MISMATCH",
        )

    if provider_enum == PaymentProviderEnum.WALLET:
        from app.modules.wallet.application import wallet_service

        # Locked balance check (FOR UPDATE) so two concurrent wallet payments
        # cannot both pass this gate before either debit lands.
        await wallet_service.check_sufficient_balance(db, user_id, amount)

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
                if not await _payment_belongs_to_user(db, existing, user_id):
                    raise NotFoundError(resource="Payment") from None
                await logger.ainfo(
                    "payment_create_idempotent_race_recovered",
                    payment_id=str(existing.id),
                    idempotency_key=idempotency_key,
                )
                return PaymentResponse.model_validate(existing)
        raise

    # ── Call gateway provider ─────────────────────────────────────────
    try:
        gateway_provider, override_merchant_id = await _resolve_gateway(db, provider.lower())
    except ValueError as exc:
        raise ValidationError(detail=str(exc), error_code="INVALID_PROVIDER") from exc

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
        # Pin the gateway credentials used at creation so verification
        # cannot drift to a different merchant id after an admin switch.
        payment.extra_data = {
            **(gateway_result.raw_response or {}),
            "zarinpal_merchant_id": override_merchant_id,
        }
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
        tracer = get_tracer()
        with tracer.start_as_current_span("payment.create") as span:
            span.set_attribute("payment.provider", provider.lower())
            span.set_attribute("payment.status", payment.status.value)
            span.set_attribute("payment.amount", amount)

        from app.shared.events.domain_events import PaymentInitiated, record_domain_event

        await record_domain_event(
            PaymentInitiated(
                payment_id=payment.id,
                order_id=order_id,
                provider=provider.lower(),
                amount=amount,
            ),
            aggregate_type="payment",
            aggregate_id=payment.id,
            db=db,
            publish_outbox=True,
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
        from app.shared.events.domain_events import PaymentFailed, record_domain_event

        await record_domain_event(
            PaymentFailed(
                payment_id=payment.id,
                order_id=order_id,
                provider=provider.lower(),
                error_code=gateway_result.error_code,
                error_message=gateway_result.error_message,
            ),
            aggregate_type="payment",
            aggregate_id=payment.id,
            db=db,
            publish_outbox=True,
        )
        raise PaymentError(
            detail=gateway_result.error_message or "Payment gateway error",
            error_code="GATEWAY_ERROR",
        )

    await db.refresh(payment)
    return PaymentResponse.model_validate(payment)


async def create_wallet_topup(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    provider: str,
    amount: int,
    idempotency_key: str | None = None,
) -> PaymentResponse:
    """Create a wallet top-up payment (no order).

    The payment carries ``extra_data.purpose = "wallet_topup"`` and
    ``extra_data.wallet_user_id``; on gateway verification the owner's
    wallet is credited inside the payment-completion transaction.
    """
    settings = get_settings()
    if amount < settings.WALLET_TOPUP_MIN_IRIALS:
        raise ValidationError(
            detail=(f"Minimum top-up amount is {settings.WALLET_TOPUP_MIN_IRIALS} IRR"),
            error_code="TOPUP_AMOUNT_TOO_LOW",
        )
    if provider.lower() == PaymentProviderEnum.WALLET.value:
        raise ValidationError(
            detail="Wallet top-up cannot be paid from the wallet itself",
            error_code="INVALID_TOPUP_PROVIDER",
        )

    await logger.ainfo(
        "wallet_topup_create_start",
        user_id=str(user_id),
        provider=provider,
        amount=amount,
    )

    provider_enum = PaymentProviderEnum(provider.lower())
    payment = Payment(
        order_id=None,
        amount=amount,
        provider=provider_enum,
        status=PaymentStatus.PENDING,
        idempotency_key=idempotency_key,
        extra_data={
            "purpose": "wallet_topup",
            "wallet_user_id": str(user_id),
        },
    )
    db.add(payment)
    try:
        await db.flush()
    except IntegrityError:
        if idempotency_key:
            stmt = select(Payment).where(Payment.idempotency_key == idempotency_key)
            existing = (await db.execute(stmt)).scalar_one_or_none()
            if existing is not None:
                if (
                    existing.extra_data
                    and existing.extra_data.get("wallet_user_id") != str(user_id)
                ):
                    raise ValidationError(
                        detail="Idempotency key already used by another user",
                        error_code="IDEMPOTENCY_KEY_CONFLICT",
                    ) from None
                return PaymentResponse.model_validate(existing)
        raise

    gateway_provider, override_merchant_id = await _resolve_gateway(db, provider.lower())
    callback_url = _build_callback_url(provider.lower(), payment.id)
    gateway_result = await gateway_provider.create_payment(
        amount=amount,
        order_id=payment.id,  # top-up payments use their own id as reference
        callback_url=callback_url,
        description="شارژ کیف پول",
    )
    await _record_transaction(
        db,
        payment_id=payment.id,
        amount=amount,
        tx_type=PaymentTransactionType.CHARGE,
        status="success" if gateway_result.success else "failed",
        provider_response=gateway_result.raw_response,
    )
    if not gateway_result.success:
        payment.status = PaymentStatus.FAILED
        payment.extra_data = {
            **(payment.extra_data or {}),
            "error_code": gateway_result.error_code,
            "error_message": gateway_result.error_message,
        }
        await db.flush()
        raise PaymentError(
            detail=gateway_result.error_message or "Payment gateway error",
            error_code="GATEWAY_ERROR",
        )

    payment.authority = gateway_result.authority
    payment.gateway_url = gateway_result.gateway_url
    payment.extra_data = {
        **(payment.extra_data or {}),
        **(gateway_result.raw_response or {}),
        "zarinpal_merchant_id": override_merchant_id,
    }
    payment.status = PaymentStatus.PROCESSING
    await db.flush()
    await logger.ainfo(
        "wallet_topup_created",
        payment_id=str(payment.id),
        user_id=str(user_id),
    )
    await db.refresh(payment)
    return PaymentResponse.model_validate(payment)


async def verify_payment(
    db: AsyncSession,
    *,
    payment_id: uuid.UUID,
    authority: str | None,
    status: str,
    user_id: uuid.UUID | None = None,
) -> PaymentResponse:
    """Verify a payment with the gateway after the user returns.

    Parameters
    ----------
    payment_id:
        The internal payment UUID.
    authority:
        The authority / token returned by the gateway.  May be ``None`` when
        the callback identified the payment by payment id only; the gateway
        verify call then falls back to the recorded ``payment.authority``.
    status:
        The status string from the gateway callback query parameters.
    user_id:
        When supplied (customer-facing verify endpoint) the payment's order
        must belong to this user, otherwise the payment is not found.
    """

    await logger.ainfo(
        "payment_verify_start",
        payment_id=str(payment_id),
        authority=authority,
        callback_status=status,
    )

    # Lock the payment row so a racing webhook / verify request cannot
    # process the same payment twice.
    payment = await db.get(Payment, payment_id, with_for_update=True)
    if payment is None:
        raise NotFoundError(resource="Payment")

    # Customer-facing verification is restricted to the payment owner:
    # order payments via the order, wallet top-ups via extra_data.
    extra = payment.extra_data or {}
    if user_id is not None and payment.order_id:
        from app.modules.orders.domain.models import Order

        order = await db.get(Order, payment.order_id)
        if order is None or order.user_id != user_id:
            raise NotFoundError(resource="Payment")
    elif user_id is not None and extra.get("purpose") == "wallet_topup":
        if extra.get("wallet_user_id") != str(user_id):
            raise NotFoundError(resource="Payment")

    # The gateway token presented for verification must be the one recorded
    # at payment creation (or the settled provider transaction id). A
    # caller-supplied look-alike must never reach the gateway verify step.
    if (
        authority
        and payment.authority
        and authority != payment.authority
        and authority != (payment.provider_transaction_id or "")
    ):
        await logger.awarning(
            "payment_verify_authority_mismatch",
            payment_id=str(payment_id),
        )
        raise ValidationError(
            detail="Payment authority does not match the recorded gateway token",
            error_code="PAYMENT_AUTHORITY_MISMATCH",
        )

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

    # Card-to-card payments that are still awaiting receipt submission or
    # admin approval must not be "verified" by the customer-facing endpoint:
    # the provider's verify call reports WAITING_ADMIN_APPROVAL and marking
    # the payment FAILED here would leave the admin approve/reject flow
    # dead (approve only accepts PENDING payments). Report the pending
    # state to the caller without transitioning the status.
    if payment.provider == PaymentProviderEnum.CARD_TRANSFER and (
        payment.status == PaymentStatus.PENDING
    ):
        raise ValidationError(
            detail="کارت به کارت: منتظر بررسی و تأیید فیش توسط مدیریت است",
            error_code="PAYMENT_WAITING_ADMIN_APPROVAL",
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
        # Split tender: a failed slice must let the order's remaining slices
        # proceed (and free the client to retry this one) rather than leaving
        # the allocation stuck in PROCESSING. No-op for single payments.
        from app.modules.payments.application import split_tender_service

        await split_tender_service.mark_allocation_failed(
            db, payment=payment, reason=f"callback_status={status}"
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
    gateway_provider = await _resolve_gateway_for_payment(db, payment)
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
        # Wallet top-ups (no order) credit the owner's wallet inside the same
        # locked transaction that completes the payment. Idempotency comes
        # from the payment status guard above (row is locked).
        if (payment.extra_data or {}).get("purpose") == "wallet_topup":
            import uuid as uuid_mod

            from app.modules.wallet.application import wallet_service
            from app.modules.wallet.domain.models import WalletTransactionType

            topup_user = uuid_mod.UUID(str((payment.extra_data or {}).get("wallet_user_id")))
            await wallet_service.credit(
                db,
                user_id=topup_user,
                amount=payment.amount,
                tx_type=WalletTransactionType.CREDIT,
                reference_type="wallet_topup",
                reference_id=payment.id,
                description="شارژ کیف پول از طریق درگاه پرداخت",
            )

        # Internal wallet payments are charged here: the wallet debit must
        # happen inside the same locked transaction that completes the
        # payment, otherwise the order would be confirmed for free.
        if payment.provider == PaymentProviderEnum.WALLET:
            from app.modules.orders.domain.models import Order as _Order

            payer_order = await db.get(_Order, payment.order_id) if payment.order_id else None
            payer_id = payer_order.user_id if payer_order is not None else None
            if payer_id is None:
                payment.status = PaymentStatus.FAILED
                await db.flush()
                raise PaymentError(
                    detail="Wallet payment is not linked to a valid order",
                    error_code="WALLET_PAYMENT_INVALID",
                )
            try:
                from app.modules.wallet.application import wallet_service
                from app.modules.wallet.domain.models import WalletTransactionType

                await wallet_service.debit(
                    db,
                    user_id=payer_id,
                    amount=payment.amount,
                    tx_type=WalletTransactionType.DEBIT,
                    reference_type="payment",
                    reference_id=payment.id,
                    description="پرداخت سفارش از کیف پول",
                )
            except Exception as exc:
                payment.status = PaymentStatus.FAILED
                payment.extra_data = {
                    **(payment.extra_data or {}),
                    "verify_error_code": "WALLET_DEBIT_FAILED",
                    "verify_error_message": str(exc),
                }
                await db.flush()
                await logger.awarning(
                    "wallet_payment_debit_failed",
                    payment_id=str(payment_id),
                    error=str(exc),
                )
                raise PaymentError(
                    detail=(
                        "Wallet payment could not be completed: "
                        "insufficient balance or inactive wallet"
                    ),
                    error_code="WALLET_DEBIT_FAILED",
                ) from exc

        payment.status = PaymentStatus.COMPLETED
        payment.provider_transaction_id = result.ref_id
        payment.extra_data = {
            **(payment.extra_data or {}),
            "ref_id": result.ref_id,
            "card_pan": mask_card_pan(result.card_pan) if result.card_pan else None,
        }

        # ── Split tender: settle this payment's allocation, if it has one ──
        # A split-tender order is confirmed when the SUM of its succeeded
        # allocations reaches the order total, not when any single payment
        # does — so a slice must not run the "this payment covers the total"
        # transition below. Payments from the legacy single-payment flow have
        # no allocation, this returns None, and their behaviour is unchanged.
        from app.modules.payments.application import split_tender_service

        split_allocation = await split_tender_service.settle_allocation_from_payment(db, payment=payment)
        if split_allocation is not None and not split_allocation.is_completing:
            # This slice settled but did not finish the order: the remaining
            # gateway slice(s) are still pending. Do not confirm the order.
            await db.flush()

        # ── Installment prepayment: settle the plan's first installment ──
        # An installment order is settled in full by the gateway's credit
        # product, which pays the merchant and collects the schedule from the
        # customer. This application only ever moves the FIRST installment,
        # so the plan's schedule must record it — but the order still
        # confirms normally below, exactly like any other paid order
        # (inventory, shipping, and the rest of the state machine depend on
        # it) — a credit sale is a sale. No-op for every other payment.
        if (payment.extra_data or {}).get("installment_prepayment"):
            from app.modules.payments.application import installment_service

            try:
                await installment_service.settle_installment_prepayment(
                    db,
                    plan_id=uuid.UUID(str(payment.extra_data["installment_prepayment"])),
                    payment_id=payment.id,
                )
            except Exception as exc:
                # A missing plan must not complete the payment as if the
                # schedule had been recorded — the customer would owe money
                # with nothing tracking it.
                await logger.aerror(
                    "installment_prepayment_settlement_failed",
                    payment_id=str(payment.id),
                    error=str(exc),
                )
                raise PaymentError(
                    detail="ثبت پیش‌پرداخت اقساطی با خطا مواجه شد",
                    error_code="INSTALLMENT_SETTLEMENT_FAILED",
                ) from exc
            await db.flush()

        # Transition associated order from PENDING to CONFIRMED
        # (skipped for orderless wallet top-ups).
        order_confirmed = False
        if payment.order_id and (payment.extra_data or {}).get("purpose") != "wallet_topup":
            from app.modules.orders.domain.models import Order, OrderStatus, OrderStatusHistory

            order_stmt = select(Order).where(Order.id == payment.order_id).with_for_update()
            order = (await db.execute(order_stmt)).scalar_one_or_none()
            if order and order.status not in (OrderStatus.PENDING, OrderStatus.CONFIRMED):
                # A canceled/returned/refunded order must never accept a
                # payment completion — the transaction (including the
                # COMPLETED status set above) rolls back.
                raise ConflictError(
                    detail=(
                        f"Order {order.id} is in status '{order.status.value}'; "
                        "payment cannot be verified"
                    ),
                    error_code="ORDER_NOT_PAYABLE",
                )
            # A split slice never confirms the order here: the allocation
            # settlement above already did it, or is waiting for its siblings.
            if (
                order
                and order.status == OrderStatus.PENDING
                and (split_allocation is None or split_allocation.is_completing is False)
            ):
                order.status = OrderStatus.CONFIRMED
                order_confirmed = True
                history = OrderStatusHistory(
                    order_id=order.id,
                    from_status=OrderStatus.PENDING.value,
                    to_status=OrderStatus.CONFIRMED.value,
                    changed_by=None,
                    reason=f"Payment verified via {payment.provider.value} (ref: {result.ref_id})",
                )
                db.add(history)

        # Publish domain events through the transactional outbox so async
        # consumers (notifications / analytics) observe the same state.
        try:
            from app.shared.events.outbox_service import OutboxService

            await OutboxService.publish(
                db,
                event_type="PaymentCompleted",
                aggregate_type="payment",
                aggregate_id=str(payment.id),
                payload={
                    "payment_id": str(payment.id),
                    "order_id": str(payment.order_id) if payment.order_id else None,
                    "amount": payment.amount,
                    "provider": payment.provider.value,
                },
            )
            if order_confirmed:
                await OutboxService.publish(
                    db,
                    event_type="OrderConfirmed",
                    aggregate_type="order",
                    aggregate_id=str(payment.order_id),
                    payload={
                        "order_id": str(payment.order_id),
                        "payment_id": str(payment.id),
                        "total": payment.amount,
                    },
                )
        except Exception as exc:
            await logger.awarning("outbox_publish_skipped", error=str(exc))

        # Automation rules (fire-and-forget): commerce must never break
        # because of the automation engine, so enqueue failures are logged
        # and dropped (see queue_automation_trigger).
        if order_confirmed:
            try:
                from app.modules.automation.application.tasks import queue_automation_trigger

                queue_automation_trigger(
                    "order_paid",
                    {
                        "order_id": str(order.id),
                        "order_number": str(getattr(order, "order_number", "") or ""),
                        "user_id": str(order.user_id),
                        "payment_id": str(payment.id),
                        "total": payment.amount,
                        "provider": payment.provider.value,
                    },
                )
            except Exception as exc:
                await logger.awarning("automation_trigger_dispatch_skipped", error=str(exc))

        await db.flush()

        await logger.ainfo(
            "payment_verify_success",
            payment_id=str(payment_id),
            ref_id=result.ref_id,
        )
        tracer = get_tracer()
        with tracer.start_as_current_span("payment.verify") as span:
            span.set_attribute("payment.provider", payment.provider.value)
            span.set_attribute("payment.status", payment.status.value)
            span.set_attribute("payment.amount", payment.amount)
            if result.ref_id:
                span.set_attribute("payment.ref_id", str(result.ref_id))

        from app.core.observability.metrics import PAYMENTS_PROCESSED
        from app.shared.events.domain_events import (
            PaymentFailed,
            PaymentVerified,
            record_domain_event,
        )

        PAYMENTS_PROCESSED.labels(provider=payment.provider.value, status="completed").inc()
        await record_domain_event(
            PaymentVerified(
                payment_id=payment.id,
                order_id=payment.order_id or uuid.UUID(int=0),
                provider=payment.provider.value,
                amount=payment.amount,
                ref_id=result.ref_id,
            ),
            aggregate_type="payment",
            aggregate_id=payment.id,
        )
    else:
        payment.status = PaymentStatus.FAILED
        payment.extra_data = {
            **(payment.extra_data or {}),
            "verify_error_code": result.error_code,
            "verify_error_message": result.error_message,
        }
        # Split tender: record the failed slice so the order shows a retryable
        # slice instead of an allocation stuck in PROCESSING. No-op otherwise.
        from app.modules.payments.application import split_tender_service

        await split_tender_service.mark_allocation_failed(
            db, payment=payment, reason=result.error_message or result.error_code
        )
        await db.flush()

        from app.core.observability.metrics import PAYMENTS_PROCESSED
        from app.shared.events.domain_events import (
            PaymentFailed,
            record_domain_event,
        )

        PAYMENTS_PROCESSED.labels(provider=payment.provider.value, status="failed").inc()
        await record_domain_event(
            PaymentFailed(
                payment_id=payment.id,
                order_id=payment.order_id or uuid.UUID(int=0),
                provider=payment.provider.value,
                error_code=result.error_code,
                error_message=result.error_message,
            ),
            aggregate_type="payment",
            aggregate_id=payment.id,
            db=db,
            publish_outbox=True,
        )

        await logger.awarning(
            "payment_verify_gateway_failed",
            payment_id=str(payment_id),
            error_code=result.error_code,
        )
        raise PaymentError(
            detail=result.error_message or "Payment verification failed",
            error_code="VERIFICATION_FAILED",
        )

    await db.refresh(payment)
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
    payment: Payment | None = None
    if authority:
        stmt = select(Payment).where(Payment.authority == authority).with_for_update()
        result = await db.execute(stmt)
        payment = result.scalar_one_or_none()

        if payment is None:
            stmt = (
                select(Payment)
                .where(Payment.provider_transaction_id == authority)
                .with_for_update()
            )
            result = await db.execute(stmt)
            payment = result.scalar_one_or_none()

    if payment is None and callback_data.order_id:
        try:
            order_uuid = uuid.UUID(str(callback_data.order_id))
            stmt = (
                select(Payment)
                .where(Payment.order_id == order_uuid)
                .order_by(Payment.created_at.desc())
                .with_for_update()
            )
            result = await db.execute(stmt)
            payment = result.scalars().first()
            if payment and not authority:
                authority = payment.authority or str(payment.id)
        except Exception:  # noqa: S110  # best-effort fallback lookup by order id
            pass

    if payment is None:
        raise NotFoundError(
            resource="Payment",
            detail=f"No payment found for authority/id '{authority or callback_data.order_id}'",
        )

    event_id = authority or str(callback_data.order_id or payment.id)

    # ── Replay Attack & Timestamp Window Guard (GAP-15) ─────────────
    # Reject webhooks with timestamp skew/drift exceeding 5 minutes (300 seconds)
    webhook_timestamp_raw = (
        getattr(callback_data, "timestamp", None)
        or (callback_data.extra.get("timestamp") if callback_data.extra else None)
        or (callback_data.extra.get("created_at") if callback_data.extra else None)
        or callback_data.date
    )
    if webhook_timestamp_raw:
        try:
            now_utc = datetime.now(UTC)
            parsed_time: datetime | None = None
            if isinstance(webhook_timestamp_raw, (int, float)):
                ts_val = float(webhook_timestamp_raw)
                if ts_val > 1e11:  # milliseconds
                    ts_val /= 1000.0
                parsed_time = datetime.fromtimestamp(ts_val, tz=UTC)
            elif isinstance(webhook_timestamp_raw, str):
                cleaned_ts = webhook_timestamp_raw.strip().replace("Z", "+00:00")
                if cleaned_ts.isdigit():
                    ts_val = float(cleaned_ts)
                    if ts_val > 1e11:
                        ts_val /= 1000.0
                    parsed_time = datetime.fromtimestamp(ts_val, tz=UTC)
                else:
                    parsed_time = datetime.fromisoformat(cleaned_ts)
                    if parsed_time.tzinfo is None:
                        parsed_time = parsed_time.replace(tzinfo=UTC)
            elif isinstance(webhook_timestamp_raw, datetime):
                parsed_time = (
                    webhook_timestamp_raw
                    if webhook_timestamp_raw.tzinfo is not None
                    else webhook_timestamp_raw.replace(tzinfo=UTC)
                )

            if parsed_time is not None:
                drift_seconds = abs((now_utc - parsed_time).total_seconds())
                if drift_seconds > 300:  # 5 minutes statutory threshold
                    await logger.awarning(
                        "payment_webhook_timestamp_expired",
                        provider=provider,
                        event_id=event_id,
                        drift_seconds=drift_seconds,
                    )
                    err = ValidationError(
                        detail=(
                            f"مهلت زمانی وب‌هوک منقضی شده است "
                            f"(اختلاف زمانی {int(drift_seconds)} ثانیه؛ حداکثر مجاز ۳۰۰ ثانیه است)"
                        ),
                        error_code="WEBHOOK_TIMESTAMP_EXPIRED",
                    )
                    err.status_code = status.HTTP_400_BAD_REQUEST
                    raise err
        except (HTTPException, ValidationError):
            raise
        except Exception as exc:
            await logger.awarning(
                "payment_webhook_timestamp_parse_error",
                error=str(exc),
                raw_timestamp=str(webhook_timestamp_raw),
            )

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
        webhook_event.processed_at = datetime.now(UTC)
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
        webhook_event.processed_at = datetime.now(UTC)
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
            detail=(f"Refund amount ({amount}) exceeds payment amount ({payment.amount})"),
            error_code="REFUND_EXCEEDS_PAYMENT",
        )

    # Check total existing refunds with row locks
    stmt = (
        select(Refund)
        .where(Refund.payment_id == payment_id)
        .where(
            Refund.status.in_(
                [RefundStatus.PENDING, RefundStatus.APPROVED, RefundStatus.PROCESSED]
            )
        )
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
    gateway_provider = await _resolve_gateway_for_payment(db, payment)

    # Resolve customer user ID from order if possible for wallet refund.
    # Top-up payments have no order; the wallet provider then credits the
    # top-up owner recorded on the payment itself.
    customer_user_id: uuid.UUID | None = None
    if payment.order_id is not None:
        try:
            from app.modules.orders.domain.models import Order

            stmt_order = select(Order.user_id).where(Order.id == payment.order_id)
            res_order = await db.execute(stmt_order)
            customer_user_id = res_order.scalar_one_or_none()
        except Exception:  # noqa: S110  # best-effort owner resolution for wallet refunds
            pass
    else:
        topup_owner = (payment.extra_data or {}).get("wallet_user_id")
        if topup_owner:
            with contextlib.suppress(ValueError):
                customer_user_id = uuid.UUID(str(topup_owner))

    # ── Persist the refund BEFORE calling the provider ─────────────────
    # The provider call is an un-rollbackable side effect: once the gateway
    # (or the wallet ledger) accepts a refund, a crash before our COMMIT
    # would otherwise leave "provider refunded / database says not refunded"
    # silently unresolved forever. Writing the row first, in a PENDING state,
    # means a reconciliation job can always find a refund that was attempted
    # and ask the provider whether it actually settled.
    refund = Refund(
        payment_id=payment.id,
        order_id=payment.order_id,
        amount=amount,
        reason=reason,
        status=RefundStatus.PENDING,
        processed_by=actor_id,
        processed_at=None,
        provider_reference=payment.authority,
    )
    db.add(refund)
    await db.flush()

    try:
        refund_result = await gateway_provider.refund(
            authority=payment.authority or "",
            amount=amount,
            user_id=customer_user_id,
            db=db,
        )
    except TypeError:
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

    # ── Finalise the refund record ────────────────────────────────────
    refund_status = RefundStatus.PROCESSED if refund_result.success else RefundStatus.APPROVED
    refund.status = refund_status
    refund.processed_at = datetime.now(UTC) if refund_result.success else None
    if refund_result.ref_id:
        refund.provider_reference = refund_result.ref_id

    # Update payment status if fully refunded
    if total_refunded + amount >= payment.amount:
        payment.status = PaymentStatus.REFUNDED
    if payment.order_id:
        # Order status changes belong to the orders state machine — never
        # write order.status directly here. Fully refunded orders that were
        # already partially refunded complete the transition to REFUNDED;
        # partial refunds mark the order PARTIALLY_REFUNDED.
        from app.modules.orders.application.order_service import apply_refund_status

        await apply_refund_status(
            db,
            order_id=payment.order_id,
            actor_id=actor_id,
            fully_refunded=total_refunded + amount >= payment.amount,
            reason=f"Refund processed for payment {payment.id}",
        )
    await db.flush()

    try:
        from app.shared.events.outbox_service import OutboxService

        await OutboxService.publish(
            db,
            event_type="RefundProcessed",
            aggregate_type="payment",
            aggregate_id=str(payment.id),
            payload={
                "payment_id": str(payment.id),
                "order_id": str(payment.order_id) if payment.order_id else None,
                "refund_id": str(refund.id),
                "amount": amount,
                "status": refund_status.value,
            },
        )
    except Exception as exc:
        await logger.awarning(
            "refund_event_publish_skipped",
            payment_id=str(payment_id),
            error=str(exc),
        )

    await logger.ainfo(
        "payment_refund_recorded",
        payment_id=str(payment_id),
        refund_id=str(refund.id),
        refund_status=refund_status.value,
        provider_success=refund_result.success,
    )

    from app.core.observability.metrics import PAYMENTS_PROCESSED
    from app.shared.events.domain_events import PaymentRefunded, record_domain_event

    PAYMENTS_PROCESSED.labels(provider=payment.provider.value, status="refunded").inc()
    await record_domain_event(
        PaymentRefunded(
            payment_id=payment.id,
            order_id=payment.order_id or uuid.UUID(int=0),
            provider=payment.provider.value,
            amount=amount,
        ),
        aggregate_type="payment",
        aggregate_id=payment.id,
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


async def get_pending_card_transfer(
    db: AsyncSession,
    *,
    order_id: uuid.UUID,
    user_id: uuid.UUID,
) -> PaymentResponse | None:
    """Return an order's pending card-to-card payment, or None.

    Used by the receipt screen to resume an abandoned card-to-card checkout.
    The order must belong to the caller; a different user's order is reported
    as not found rather than forbidden, so the endpoint leaks no existence
    information.
    """
    from app.modules.orders.domain.models import Order

    order = await db.get(Order, order_id)
    if order is None or order.user_id != user_id:
        raise NotFoundError(resource="Order")

    stmt = (
        select(Payment)
        .where(
            Payment.order_id == order_id,
            Payment.provider == PaymentProviderEnum.CARD_TRANSFER,
            Payment.status == PaymentStatus.PENDING,
        )
        .order_by(Payment.created_at.desc())
        .limit(1)
    )
    payment = (await db.execute(stmt)).scalars().first()
    if payment is None:
        return None
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
    masked_pan = mask_card_pan(card_pan) if card_pan else None
    extra.update(
        {
            "tracking_code": tracking_code,
            "card_pan": masked_pan,
            "customer_card_pan": masked_pan,
            "receipt_image_url": receipt_image_url,
            "customer_notes": notes,
            "receipt_submitted_at": datetime.now(UTC).isoformat(),
            "submitted_by": str(user_id),
            "card_transfer_status": "pending_admin_approval",
        }
    )
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
            "card_pan": masked_pan,
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

    await db.refresh(payment)
    return PaymentResponse.model_validate(payment)


async def approve_payment(
    db: AsyncSession,
    *,
    payment_id: uuid.UUID,
    admin_user_id: uuid.UUID,
) -> PaymentResponse:
    """Admin approval of a pending payment (e.g. card-to-card)."""
    # Lock the row so two concurrent approvals cannot both pass the
    # PENDING check and double-credit a wallet top-up.
    stmt_lock = select(Payment).where(Payment.id == payment_id).with_for_update()
    payment = (await db.execute(stmt_lock)).scalar_one_or_none()
    if payment is None:
        raise NotFoundError(resource="Payment")

    if payment.status == PaymentStatus.COMPLETED:
        return PaymentResponse.model_validate(payment)

    if payment.status != PaymentStatus.PENDING:
        raise ValidationError(
            detail=f"Only pending payments can be approved (current: {payment.status.value})",
            error_code="PAYMENT_NOT_PENDING",
        )

    extra = dict(payment.extra_data or {})
    extra["approved_by"] = str(admin_user_id)
    extra["approved_at"] = datetime.now(UTC).isoformat()
    extra["card_transfer_status"] = "approved"

    payment.status = PaymentStatus.COMPLETED
    if not payment.provider_transaction_id:
        payment.provider_transaction_id = (
            extra.get("tracking_code") or payment.authority or f"C2C-{payment.id.hex[:8]}"
        )
    payment.extra_data = extra

    # Approved wallet top-ups must credit the wallet inside this same
    # transaction — the customer-facing verify path never runs for
    # card-to-card (see verify_payment), so approval is the only moment
    # the credit would happen.
    if (payment.extra_data or {}).get("purpose") == "wallet_topup":
        import uuid as uuid_mod

        from app.modules.wallet.application import wallet_service
        from app.modules.wallet.domain.models import WalletTransactionType

        topup_user = uuid_mod.UUID(str(payment.extra_data["wallet_user_id"]))
        await wallet_service.credit(
            db,
            user_id=topup_user,
            amount=payment.amount,
            tx_type=WalletTransactionType.CREDIT,
            reference_type="wallet_topup",
            reference_id=payment.id,
            description="شارژ کیف پول (تأیید کارت به کارت توسط مدیریت)",
        )

    # Transition associated order from PENDING to CONFIRMED on admin approval
    order_confirmed = False
    if payment.order_id:
        from app.modules.orders.domain.models import Order, OrderStatus, OrderStatusHistory

        order_stmt = select(Order).where(Order.id == payment.order_id).with_for_update()
        order = (await db.execute(order_stmt)).scalar_one_or_none()
        if order and order.status == OrderStatus.PENDING:
            order.status = OrderStatus.CONFIRMED
            order_confirmed = True
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

    # Publish outbox events so the worker sends notifications / allocates
    # digital cards — identical to the verify_payment path.
    try:
        from app.shared.events.outbox_service import OutboxService

        await OutboxService.publish(
            db,
            event_type="PaymentCompleted",
            aggregate_type="payment",
            aggregate_id=str(payment.id),
            payload={
                "payment_id": str(payment.id),
                "order_id": str(payment.order_id) if payment.order_id else None,
                "amount": payment.amount,
                "provider": payment.provider.value,
            },
        )
        if order_confirmed:
            await OutboxService.publish(
                db,
                event_type="OrderConfirmed",
                aggregate_type="order",
                aggregate_id=str(payment.order_id),
                payload={
                    "order_id": str(payment.order_id),
                    "payment_id": str(payment.id),
                    "total": payment.amount,
                },
            )
    except Exception as exc:
        await logger.awarning("outbox_publish_skipped", error=str(exc))

    await logger.ainfo(
        "payment_admin_approved",
        payment_id=str(payment_id),
        admin_user_id=str(admin_user_id),
    )

    await db.refresh(payment)
    return PaymentResponse.model_validate(payment)


async def reject_payment(
    db: AsyncSession,
    *,
    payment_id: uuid.UUID,
    admin_user_id: uuid.UUID,
    reason: str | None = None,
) -> PaymentResponse:
    """Admin rejection of a pending payment (e.g. card-to-card)."""
    stmt_lock = select(Payment).where(Payment.id == payment_id).with_for_update()
    payment = (await db.execute(stmt_lock)).scalar_one_or_none()
    if payment is None:
        raise NotFoundError(resource="Payment")

    if payment.status in (PaymentStatus.COMPLETED, PaymentStatus.REFUNDED):
        raise ValidationError(
            detail=f"Cannot reject payment in status: {payment.status.value}",
            error_code="PAYMENT_CANNOT_BE_REJECTED",
        )

    extra = dict(payment.extra_data or {})
    extra["rejected_by"] = str(admin_user_id)
    extra["rejection_reason"] = reason or "Payment rejected by admin"
    extra["rejected_at"] = datetime.now(UTC).isoformat()
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

    try:
        from app.shared.events.outbox_service import OutboxService

        await OutboxService.publish(
            db,
            event_type="PaymentFailed",
            aggregate_type="payment",
            aggregate_id=str(payment.id),
            payload={
                "payment_id": str(payment.id),
                "order_id": str(payment.order_id) if payment.order_id else None,
                "provider": payment.provider.value,
                "error_code": "ADMIN_REJECTED",
                "error_message": reason or "Payment rejected by admin",
            },
        )
    except Exception as exc:
        await logger.awarning("outbox_publish_skipped", error=str(exc))

    await logger.ainfo(
        "payment_admin_rejected",
        payment_id=str(payment_id),
        admin_user_id=str(admin_user_id),
        reason=reason,
    )

    await db.refresh(payment)
    return PaymentResponse.model_validate(payment)


def get_payment_methods() -> PaymentMethodsResponse:
    """Return the list of available payment methods."""
    settings = get_settings()

    methods = [
        PaymentMethodInfo(
            provider=PaymentProviderEnum.ZARINPAL,
            name="Zarinpal",
            name_fa="زرین‌پال",
            is_enabled=(
                settings.PAYMENT_PROVIDER == "zarinpal" or settings.ENVIRONMENT == "development"
            ),
            icon="zarinpal",
            description="Online payment via Zarinpal gateway",
            instructions="پرداخت آنلاین از طریق کلیه کارت‌های عضو شتاب با درگاه زرین‌پال",
            instructions_fa="پرداخت آنلاین از طریق کلیه کارت‌های عضو شتاب با درگاه زرین‌پال",
        ),
        PaymentMethodInfo(
            provider=PaymentProviderEnum.IDPAY,
            name="IDPay",
            name_fa="آی‌دی‌پی",
            is_enabled=(
                settings.PAYMENT_PROVIDER == "idpay" or settings.ENVIRONMENT == "development"
            ),
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
            instructions="پرداخت امن با رمزارزهای تتر (USDT-TRC20/ERC20)، بیت‌کوین و اتریوم از طریق درگاه NowPayments همراه با تولید خودکار آدرس و QR Code",  # noqa: E501
            instructions_fa="پرداخت امن با رمزارزهای تتر (USDT-TRC20/ERC20)، بیت‌کوین و اتریوم از طریق درگاه NowPayments همراه با تولید خودکار آدرس و QR Code",  # noqa: E501
        ),
        PaymentMethodInfo(
            provider=PaymentProviderEnum.CARD_TRANSFER,
            name="Card to Card",
            name_fa="کارت به کارت",
            is_enabled=True,
            icon="credit-card",
            description="Direct card to card bank transfer",
            instructions=f"انتقال وجه به کارت شماره {settings.CARD_TO_CARD_NUMBER} ({settings.CARD_TO_CARD_BANK} - {settings.CARD_TO_CARD_HOLDER}) و ثبت کد پیگیری فیش",  # noqa: E501
            instructions_fa=f"انتقال وجه به کارت شماره {settings.CARD_TO_CARD_NUMBER} ({settings.CARD_TO_CARD_BANK} - {settings.CARD_TO_CARD_HOLDER}) و ثبت کد پیگیری فیش",  # noqa: E501
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
