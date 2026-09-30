"""Saved payment methods: tokenize, list, set-default, delete, charge.

User-scoped CRUD over :class:`SavedPaymentMethod`, plus the tokenized-charge
entry point a future recurring/subscription service will call.

Security invariants (enforced here, not only in the schema):

1. **No PAN is ever persisted.** :func:`save_tokenized_method` accepts only a
   :class:`TokenizationResult` from a provider and stores ``token`` (opaque,
   gateway-scoped) plus display metadata. If a provider ever echoes a
   full-length PAN, the write is rejected outright rather than masked and
   stored — masking at write time would still mean the PAN transited and could
   be logged.
2. **The token never leaves the server.** The response schema exposes
   ``masked_pan``/``last4`` only; ``to_response`` deliberately drops ``token``.
3. **A revoked or inactive method is never chargeable.**
   :func:`charge_saved_method` re-checks status and ``is_active`` under the
   same transaction that records the payment.

Deleting a method is a *local revocation*: the row is marked revoked and the
gateway is asked (best-effort) to invalidate its token. It is never a hard
delete, so the audit trail of which card paid which order survives — refunds
and support both need that link.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import func, select

from app.core.exceptions.handlers import (
    ConflictError,
    NotFoundError,
    PaymentError,
    ValidationError,
)
from app.core.security.data_protection import mask_card_pan
from app.modules.payments.domain.saved_method_models import (
    SavedPaymentMethod,
    TokenizationStatus,
)
from app.modules.payments.infrastructure.provider_factory import get_payment_provider
from app.modules.payments.schemas.saved_method import SavedPaymentMethodResponse

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.payments.domain.models import Payment
    from app.modules.payments.infrastructure.providers.base import TokenizationResult

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# A token shorter than this is not a plausible gateway handle and is refused —
# cheap guard against a provider mistakenly returning a truncated PAN.
_MIN_TOKEN_LENGTH = 8


def _assert_token_is_not_a_pan(token: str) -> None:
    """Refuse a "token" that is actually a card number.

    Providers must never hand this application a PAN (see the capability
    contract in ``providers/base.py``). The check is deliberately blunt: a
    token that is ``13..19`` digits, optionally space/dash separated, is a PAN
    shape and is rejected rather than masked-and-stored.
    """
    digits_only = token.replace(" ", "").replace("-", "")
    if digits_only.isdigit() and 13 <= len(digits_only) <= 19:
        raise PaymentError(
            detail=(
                "Provider returned a card-number-shaped token; refusing to store it. "
                "A tokenized card must be handled by the gateway, never by this service."
            ),
            error_code="TOKEN_LOOKS_LIKE_PAN",
        )


async def _get_provider_for_tokenization(provider_name: str) -> Any:
    """Resolve a provider and refuse one that cannot tokenize."""
    try:
        provider = get_payment_provider(provider_name)
    except ValueError as exc:
        raise ValidationError(detail=str(exc), error_code="INVALID_PROVIDER") from exc

    if not getattr(provider, "supports_tokenization", False):
        raise ValidationError(
            detail=(
                f"درگاه «{provider_name}» از ذخیره‌سازی کارت پشتیبانی نمی‌کند. "
                f"Gateway '{provider_name}' does not support saved cards."
            ),
            error_code="PROVIDER_NO_TOKENIZATION",
        )
    return provider


def to_response(method: SavedPaymentMethod) -> SavedPaymentMethodResponse:
    """Build the client-facing view, which never carries the gateway token."""
    return SavedPaymentMethodResponse(
        id=method.id,
        provider=method.provider,
        masked_pan=method.masked_pan,
        last4=method.last4,
        expiry_jalali=method.expiry_jalali,
        card_holder_name=method.card_holder_name,
        bank_name=method.bank_name,
        status=method.status,
        is_default=method.is_default,
        is_active=method.is_active,
        last_used_at=method.last_used_at,
        created_at=method.created_at,
        updated_at=method.updated_at,
    )


async def list_saved_methods(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    include_inactive: bool = False,
) -> list[SavedPaymentMethodResponse]:
    """List the user's saved cards, default first then newest first."""
    stmt = select(SavedPaymentMethod).where(SavedPaymentMethod.user_id == user_id)
    if not include_inactive:
        stmt = stmt.where(SavedPaymentMethod.is_active.is_(True))
    stmt = stmt.order_by(
        SavedPaymentMethod.is_default.desc(),
        SavedPaymentMethod.created_at.desc(),
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [to_response(row) for row in rows]


async def list_saved_methods_admin(
    db: AsyncSession,
    *,
    user_id: uuid.UUID | None = None,
    provider: str | None = None,
    include_inactive: bool = True,
    limit: int = 100,
) -> list[SavedPaymentMethodResponse]:
    """Admin visibility: which customers hold which saved cards.

    The gateway token is still not exposed — an admin sees the same masked
    view the customer does. Support can identify a card ("the •1234 Zarinpal
    one") without gaining a way to charge it.
    """
    stmt = select(SavedPaymentMethod)
    if user_id is not None:
        stmt = stmt.where(SavedPaymentMethod.user_id == user_id)
    if provider is not None:
        stmt = stmt.where(SavedPaymentMethod.provider == provider)
    if not include_inactive:
        stmt = stmt.where(SavedPaymentMethod.is_active.is_(True))
    stmt = stmt.order_by(SavedPaymentMethod.created_at.desc()).limit(max(1, min(limit, 500)))
    rows = (await db.execute(stmt)).scalars().all()
    return [to_response(row) for row in rows]


async def _clear_other_defaults(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    keep_id: uuid.UUID | None,
) -> None:
    """Unset the default flag on every other active method of this user."""
    stmt = select(SavedPaymentMethod).where(
        SavedPaymentMethod.user_id == user_id,
        SavedPaymentMethod.is_default.is_(True),
    )
    for row in (await db.execute(stmt)).scalars().all():
        if keep_id is not None and row.id == keep_id:
            continue
        row.is_default = False
    await db.flush()


async def save_tokenized_method(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    provider_name: str,
    result: TokenizationResult,
    make_default: bool | None = None,
) -> SavedPaymentMethodResponse:
    """Persist a successful tokenization as the user's saved card.

    Idempotency: the same gateway token re-saved for the same user updates the
    existing row (display metadata refresh, ``last_used_at`` untouched)
    instead of failing on the ``(provider, token)`` unique index. A token
    already owned by *another* user is a hard conflict — that would be a
    cross-account card leak.
    """
    if not result.success or not result.token:
        raise PaymentError(
            detail=result.error_message or "Card registration failed at the gateway",
            error_code=result.error_code or "TOKENIZATION_FAILED",
        )

    token = result.token.strip()
    _assert_token_is_not_a_pan(token)
    if len(token) < _MIN_TOKEN_LENGTH:
        raise ValidationError(
            detail="Provider returned an implausibly short token",
            error_code="TOKEN_TOO_SHORT",
        )

    stmt = select(SavedPaymentMethod).where(
        SavedPaymentMethod.provider == provider_name,
        SavedPaymentMethod.token == token,
    )
    existing = (await db.execute(stmt)).scalar_one_or_none()

    if existing is not None:
        if existing.user_id != user_id:
            # A gateway token must be globally unique; if it collides across
            # users the gateway is echoing another customer's handle. Refuse.
            await logger.aerror(
                "saved_method_token_owner_conflict",
                provider=provider_name,
                existing_user_id=str(existing.user_id),
                requesting_user_id=str(user_id),
            )
            raise ConflictError(
                detail="This card is already saved to another account",
                error_code="SAVED_METHOD_OWNED_BY_ANOTHER_USER",
            )
        existing.masked_pan = result.masked_pan or existing.masked_pan
        existing.last4 = result.last4 or existing.last4
        existing.expiry_jalali = result.expiry_jalali or existing.expiry_jalali
        existing.card_holder_name = result.card_holder_name or existing.card_holder_name
        existing.bank_name = result.bank_name or existing.bank_name
        existing.status = TokenizationStatus.ACTIVE
        existing.is_active = True
        existing.revoked_at = None
        existing.revoked_reason = None
        if make_default:
            await _clear_other_defaults(db, user_id=user_id, keep_id=existing.id)
            existing.is_default = True
        await db.flush()
        await logger.ainfo(
            "saved_method_refreshed",
            saved_method_id=str(existing.id),
            user_id=str(user_id),
            provider=provider_name,
        )
        return to_response(existing)

    # First card for a user becomes the default automatically; otherwise the
    # caller decides. Either way exactly one default is maintained.
    count = int(
        await db.scalar(
            select(func.count())
            .select_from(SavedPaymentMethod)
            .where(
                SavedPaymentMethod.user_id == user_id,
                SavedPaymentMethod.is_active.is_(True),
            )
        )
        or 0
    )
    should_default = make_default if make_default is not None else count == 0
    if should_default:
        await _clear_other_defaults(db, user_id=user_id, keep_id=None)

    method = SavedPaymentMethod(
        user_id=user_id,
        provider=provider_name,
        token=token,
        masked_pan=result.masked_pan,
        last4=result.last4,
        expiry_jalali=result.expiry_jalali,
        card_holder_name=result.card_holder_name,
        bank_name=result.bank_name,
        status=TokenizationStatus.ACTIVE,
        is_default=should_default,
        is_active=True,
        extra_data={"tokenized": True},
    )
    db.add(method)
    await db.flush()
    await logger.ainfo(
        "saved_method_created",
        saved_method_id=str(method.id),
        user_id=str(user_id),
        provider=provider_name,
        is_default=should_default,
    )
    return to_response(method)


async def initiate_tokenization(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    provider_name: str,
    callback_url: str | None = None,
    mobile: str | None = None,
) -> Any:
    """Ask the gateway to register a card, returning its tokenization result.

    The gateway hosts the card-entry page; this application never receives the
    PAN. The returned result is *not* persisted here — the caller (API route)
    decides when to save it, so a half-finished registration never becomes a
    saved card.
    """
    provider = await _get_provider_for_tokenization(provider_name)
    if not callback_url:
        from app.core.config.settings import get_settings

        base = get_settings().PAYMENT_CALLBACK_BASE_URL.rstrip("/")
        callback_url = f"{base}/{provider_name}/tokenize-callback"

    result = await provider.tokenize(
        user_id=user_id,
        callback_url=callback_url,
        mobile=mobile,
    )
    await logger.ainfo(
        "tokenization_initiated",
        user_id=str(user_id),
        provider=provider_name,
        success=result.success,
        error_code=result.error_code,
    )
    return result


async def get_saved_method(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    method_id: uuid.UUID,
) -> SavedPaymentMethod:
    """Fetch one of the user's saved methods or raise ``NotFoundError``.

    Ownership is part of the query, not a check after the fetch, so another
    user's method is indistinguishable from a missing one (no enumeration).
    """
    stmt = select(SavedPaymentMethod).where(
        SavedPaymentMethod.id == method_id,
        SavedPaymentMethod.user_id == user_id,
    )
    method = (await db.execute(stmt)).scalar_one_or_none()
    if method is None:
        raise NotFoundError(resource="SavedPaymentMethod")
    return method


async def set_default_method(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    method_id: uuid.UUID,
) -> SavedPaymentMethodResponse:
    """Make one saved card the user's default, atomically."""
    method = await get_saved_method(db, user_id=user_id, method_id=method_id)
    if not method.is_active or method.status != TokenizationStatus.ACTIVE:
        raise ConflictError(
            detail="این کارت غیرفعال است و نمی‌تواند پیش‌فرض شود",
            error_code="SAVED_METHOD_INACTIVE",
        )

    # Unset the others first, then set this one: the partial unique index
    # (one default per user) would otherwise reject an intermediate state.
    await _clear_other_defaults(db, user_id=user_id, keep_id=method.id)
    method.is_default = True
    await db.flush()
    await logger.ainfo(
        "saved_method_set_default",
        saved_method_id=str(method.id),
        user_id=str(user_id),
    )
    return to_response(method)


async def revoke_saved_method(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    method_id: uuid.UUID,
    reason: str | None = None,
) -> SavedPaymentMethodResponse:
    """Delete a saved card (local revocation + best-effort gateway revoke).

    Never a hard DELETE: the row keeps the link between this card and the
    orders it paid, which refunds and reconciliation rely on. A local commit
    failure cannot leave a chargeable card behind either way — the row is
    inactive regardless of what the gateway answers.
    """
    method = await get_saved_method(db, user_id=user_id, method_id=method_id)

    gateway_revoked = False
    if method.status == TokenizationStatus.ACTIVE:
        try:
            provider = get_payment_provider(method.provider)
            gateway_revoked = await provider.revoke_token(token=method.token)
        except Exception as exc:  # noqa: BLE001 — best-effort remote revoke
            await logger.awarning(
                "saved_method_gateway_revoke_failed",
                saved_method_id=str(method.id),
                provider=method.provider,
                error=str(exc),
            )

    was_default = method.is_default
    method.is_active = False
    method.is_default = False
    method.status = TokenizationStatus.REVOKED
    method.revoked_at = datetime.now(UTC)
    method.revoked_reason = reason
    await db.flush()

    # Promote another card to default so the account page never ends up with
    # saved cards but no default.
    if was_default:
        remaining = (
            await db.execute(
                select(SavedPaymentMethod)
                .where(
                    SavedPaymentMethod.user_id == user_id,
                    SavedPaymentMethod.is_active.is_(True),
                    SavedPaymentMethod.id != method.id,
                )
                .order_by(SavedPaymentMethod.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if remaining is not None:
            remaining.is_default = True
            await db.flush()

    await logger.ainfo(
        "saved_method_revoked",
        saved_method_id=str(method.id),
        user_id=str(user_id),
        gateway_revoked=gateway_revoked,
    )
    return to_response(method)


async def get_chargeable_method(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    method_id: uuid.UUID,
) -> SavedPaymentMethod:
    """Fetch a saved method that is currently chargeable, or raise.

    Chargeability is ``is_active`` + ``status == ACTIVE``. The check lives here
    so every charge path shares it; a revoked card must be unchargeable even
    if a caller holds a stale id.
    """
    method = await get_saved_method(db, user_id=user_id, method_id=method_id)
    if not method.is_active:
        raise ConflictError(
            detail="این کارت حذف شده است",
            error_code="SAVED_METHOD_INACTIVE",
        )
    if method.status != TokenizationStatus.ACTIVE:
        raise ConflictError(
            detail=f"این کارت در وضعیت «{method.status.value}» است و قابل استفاده نیست",
            error_code="SAVED_METHOD_NOT_ACTIVE",
        )
    return method


async def charge_saved_method(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    method_id: uuid.UUID,
    amount: int,
    order_id: uuid.UUID,
    description: str = "",
) -> tuple[Payment, Any]:
    """Charge a saved card for an order.

    Returns ``(payment, gateway_result)``. The caller owns the transaction:
    this function creates the ``Payment`` row (so the charge is auditable even
    if the gateway call is interrupted) and leaves status transitions to the
    normal ``verify``/callback path, exactly like a redirect payment.

    This is the entry point a recurring-charge service uses — it does not
    require the customer to be present. Idempotency is the caller's
    responsibility via ``order_id``/an idempotency key, mirroring
    ``payment_service.create_payment``.
    """
    if amount <= 0:
        raise ValidationError(
            detail="Charge amount must be a positive integer (IRR)",
            error_code="INVALID_AMOUNT",
        )

    method = await get_chargeable_method(db, user_id=user_id, method_id=method_id)

    from app.modules.orders.domain.models import Order, OrderStatus
    from app.modules.payments.domain.models import (
        Payment,
        PaymentProvider as PaymentProviderEnum,
        PaymentStatus,
        PaymentTransactionType,
    )

    order = await db.get(Order, order_id, with_for_update=True)
    if order is None or order.user_id != user_id:
        raise NotFoundError(resource="Order")
    if order.status != OrderStatus.PENDING:
        raise ConflictError(
            detail=f"Order {order_id} is not payable in status '{order.status.value}'",
            error_code="ORDER_NOT_PAYABLE",
        )
    if amount != order.total:
        raise ValidationError(
            detail=(f"Charge amount ({amount}) does not match the order total ({order.total})"),
            error_code="AMOUNT_MISMATCH",
        )

    try:
        provider_enum = PaymentProviderEnum(method.provider)
    except ValueError:
        raise ValidationError(
            detail=f"Unsupported payment provider: {method.provider}",
            error_code="INVALID_PROVIDER",
        ) from None

    payment = Payment(
        order_id=order_id,
        amount=amount,
        provider=provider_enum,
        status=PaymentStatus.PENDING,
        extra_data={
            "saved_method_id": str(method.id),
            "tokenized_charge": True,
        },
    )
    db.add(payment)
    await db.flush()

    provider = get_payment_provider(method.provider)
    result = await provider.charge_token(
        token=method.token,
        amount=amount,
        order_id=order_id,
        description=description,
    )

    from app.modules.payments.application.payment_service import _record_transaction

    await _record_transaction(
        db,
        payment_id=payment.id,
        amount=amount,
        tx_type=PaymentTransactionType.CHARGE,
        status="success" if result.success else "failed",
        provider_response=result.raw_response,
    )

    if result.success:
        payment.status = PaymentStatus.PROCESSING
        payment.authority = result.authority
        payment.extra_data = {
            **(payment.extra_data or {}),
            "ref_id": result.ref_id,
        }
        method.last_used_at = datetime.now(UTC)
    else:
        payment.status = PaymentStatus.FAILED
        payment.extra_data = {
            **(payment.extra_data or {}),
            "error_code": result.error_code,
            "error_message": result.error_message,
        }
    await db.flush()

    await logger.ainfo(
        "saved_method_charged",
        payment_id=str(payment.id),
        saved_method_id=str(method.id),
        provider=method.provider,
        amount=amount,
        success=result.success,
    )
    return payment, result


# ── Display helpers ───────────────────────────────────────────────────────


def mask_pan_for_display(pan: str | None) -> str | None:
    """Mask a PAN for display, reusing the shared masking helper.

    Exposed here so provider adapters that receive a one-time PAN echo (some
    gateways return it on the tokenization response) can normalise it before
    it reaches :func:`save_tokenized_method`.
    """
    return mask_card_pan(pan) if pan else None
