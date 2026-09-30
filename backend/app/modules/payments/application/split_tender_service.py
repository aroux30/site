"""Split tender: settle one order with several payments.

The flow
--------
1. :func:`create_split_payments` records **one allocation + one payment row
   per slice** — e.g. ``wallet 300,000`` + ``zarinpal remainder``. Wallet
   slices are settled inside this call (the wallet debit is atomic, see
   :func:`settle_wallet_allocation`); gateway slices come back with a
   ``gateway_url`` the client redirects to.
2. When a gateway slice is verified through the normal
   ``payment_service.verify_payment`` path, the allocation is settled via
   :func:`settle_allocation_from_payment`.
3. The **last** slice that brings the sum of succeeded allocations to the
   order total flips the order to ``CONFIRMED``.

Race safety (why this is not just an if-statement)
--------------------------------------------------
Two slices can settle concurrently (a customer returns from the gateway at the
same moment the wallet slice lands). Both would see "sum + mine == total" and
both would confirm the order, producing two CONFIRMED transitions, two status
history rows, and two ``OrderConfirmed`` outbox events.

Guards, in order:

* The **order row is locked ``FOR UPDATE``** before the sum is read, so the
  two settlers serialise. The second one re-reads the sum *after* the first
  committed and sees the order already fully paid.
* :func:`claim_completion` is the only writer of ``is_completing`` and sets it
  under that lock, and the partial unique index
  ``uq_payment_allocations_one_completing_per_order`` makes a second claim a
  database error rather than a second order transition.
* The order status transition itself re-checks ``order.status == PENDING``
  under the lock.

Lock ordering (deadlock avoidance)
----------------------------------
``payment_service.verify_payment`` locks the **payment** row first, then the
**order** row. A split settlement that locked the order first and then the
payment would deadlock against a concurrent verify of the same slice. So
:func:`settle_allocation_from_payment` deliberately takes the order lock
*after* it has read the allocation with ``FOR UPDATE`` on the allocation row —
and the caller (``verify_payment``) is already holding the payment lock. The
ordering is therefore always payment → allocation → order, never the reverse.

Idempotency
-----------
``create_split_payments`` accepts an ``idempotency_key`` per slice; a repeat
returns the existing slice. :func:`settle_allocation_from_payment` is a no-op
for an already-succeeded allocation, so a replayed callback cannot
double-settle.

Refunds (v1)
------------
Refunds stay per-``Payment`` through the existing ``refund_payment`` flow: a
split tender is several payments, so refunding "per allocation" means refunding
the payment that allocation points at. :func:`refund_allocation` resolves that
mapping and records ``refunded_rial`` on the allocation so the order-fully-
refunded arithmetic can account for partial per-slice refunds.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.core.exceptions.handlers import (
    ConflictError,
    NotFoundError,
    PaymentError,
    ValidationError,
)
from app.modules.payments.domain.allocation_models import (
    AllocationStatus,
    PaymentAllocation,
)
from app.modules.payments.domain.models import (
    Payment,
    PaymentStatus,
    PaymentTransactionType,
)
from app.modules.payments.infrastructure.provider_factory import get_payment_provider
from app.modules.payments.schemas.allocation import (
    AllocationSliceRequest,
    OrderAllocationSummary,
    PaymentAllocationResponse,
    SplitPaymentResponse,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# Slice providers that settle immediately with no redirect step.
_INTERNAL_PROVIDERS = frozenset({"wallet"})
# Splits are capped so a client cannot fan one order into hundreds of slices
# and blow up the allocation sum scan.
_MAX_SLICES = 5


def to_response(allocation: PaymentAllocation) -> PaymentAllocationResponse:
    return PaymentAllocationResponse(
        id=allocation.id,
        order_id=allocation.order_id,
        payment_id=allocation.payment_id,
        amount_rial=allocation.amount_rial,
        provider=allocation.provider,
        status=allocation.status,
        is_completing=allocation.is_completing,
        settled_at=allocation.settled_at,
        refunded_rial=allocation.refunded_rial,
        failure_reason=allocation.failure_reason,
        created_at=allocation.created_at,
        updated_at=allocation.updated_at,
    )


async def _load_order_locked(db: AsyncSession, order_id: uuid.UUID) -> Any:
    from app.modules.orders.domain.models import Order

    order = await db.get(Order, order_id, with_for_update=True)
    if order is None:
        raise NotFoundError(resource="Order")
    return order


async def sum_succeeded_allocations(
    db: AsyncSession,
    *,
    order_id: uuid.UUID,
    exclude_allocation_id: uuid.UUID | None = None,
) -> int:
    """Sum of *succeeded* allocations for an order, read from the rows.

    Deliberately never read from a cached counter on the order: a cached value
    that drifted high would confirm an underpaid order, and one that drifted
    low would leave a fully paid order pending.
    """
    stmt = (
        select(func.coalesce(func.sum(PaymentAllocation.amount_rial), 0))
        .select_from(PaymentAllocation)
        .where(
            PaymentAllocation.order_id == order_id,
            PaymentAllocation.status.in_(
                [AllocationStatus.SUCCEEDED, AllocationStatus.REFUNDED, AllocationStatus.PARTIALLY_REFUNDED]
            ),
        )
    )
    if exclude_allocation_id is not None:
        stmt = stmt.where(PaymentAllocation.id != exclude_allocation_id)
    return int(await db.scalar(stmt) or 0)


async def list_order_allocations(
    db: AsyncSession,
    *,
    order_id: uuid.UUID,
    user_id: uuid.UUID,
) -> list[PaymentAllocationResponse]:
    """All slices of an order, ownership-checked against the order's buyer."""
    from app.modules.orders.domain.models import Order

    order = await db.get(Order, order_id)
    if order is None or order.user_id != user_id:
        raise NotFoundError(resource="Order")

    stmt = (
        select(PaymentAllocation)
        .where(PaymentAllocation.order_id == order_id)
        .order_by(PaymentAllocation.created_at.asc())
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [to_response(row) for row in rows]


async def order_allocation_summary(
    db: AsyncSession,
    *,
    order_id: uuid.UUID,
    user_id: uuid.UUID,
) -> OrderAllocationSummary:
    """Paid / remaining / fully-paid view of an order's split tender."""
    from app.modules.orders.domain.models import Order

    order = await db.get(Order, order_id)
    if order is None or order.user_id != user_id:
        raise NotFoundError(resource="Order")

    allocations = await list_order_allocations(db, order_id=order_id, user_id=user_id)
    paid = sum(
        a.amount_rial
        for a in allocations
        if a.status
        in (
            AllocationStatus.SUCCEEDED,
            AllocationStatus.REFUNDED,
            AllocationStatus.PARTIALLY_REFUNDED,
        )
    )
    pending = sum(
        a.amount_rial
        for a in allocations
        if a.status in (AllocationStatus.PENDING, AllocationStatus.PROCESSING)
    )
    return OrderAllocationSummary(
        order_id=order_id,
        order_total_rial=order.total,
        paid_amount_rial=paid,
        pending_amount_rial=pending,
        remaining_amount_rial=max(0, order.total - paid),
        is_fully_paid=paid >= order.total,
        allocations=allocations,
    )


async def get_allocation_for_user(
    db: AsyncSession,
    *,
    allocation_id: uuid.UUID,
    user_id: uuid.UUID,
) -> PaymentAllocationResponse:
    """Fetch one allocation, ownership-checked through its order's buyer."""
    from app.modules.orders.domain.models import Order

    allocation = (
        await db.execute(
            select(PaymentAllocation).where(PaymentAllocation.id == allocation_id)
        )
    ).scalar_one_or_none()
    if allocation is None:
        raise NotFoundError(resource="PaymentAllocation")

    order = await db.get(Order, allocation.order_id)
    if order is None or order.user_id != user_id:
        # Another user's allocation must be indistinguishable from a missing
        # one — no id enumeration.
        raise NotFoundError(resource="PaymentAllocation")
    return to_response(allocation)


# ── Creation ──────────────────────────────────────────────────────────────


async def create_split_payments(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    order_id: uuid.UUID,
    slices: list[AllocationSliceRequest],
) -> SplitPaymentResponse:
    """Create one payment + allocation per slice of a split-tender checkout.

    Validation before any write:

    * the slices' amounts sum **exactly** to the order total (the order total
      is authoritative; a client-side total is never trusted),
    * every provider is known,
    * there is at most one wallet slice (two wallet slices would each debit
      independently and the second could fail after the first settled, leaving
      a half-paid order with no gateway fallback).

    The wallet slice is settled inside this transaction; gateway slices are
    left ``PENDING`` with a ``gateway_url`` for the client to redirect to.
    """
    if not slices:
        raise ValidationError(
            detail="At least one payment slice is required",
            error_code="NO_ALLOCATION_SLICES",
        )
    if len(slices) > _MAX_SLICES:
        raise ValidationError(
            detail=f"At most {_MAX_SLICES} payment slices are supported",
            error_code="TOO_MANY_ALLOCATION_SLICES",
        )

    wallet_slices = [s for s in slices if s.provider.lower() == "wallet"]
    if len(wallet_slices) > 1:
        raise ValidationError(
            detail="Only one wallet slice is allowed per order",
            error_code="MULTIPLE_WALLET_SLICES",
        )

    for slice_ in slices:
        if slice_.amount_rial <= 0:
            raise ValidationError(
                detail="Each slice amount must be a positive integer (IRR)",
                error_code="INVALID_AMOUNT",
            )
        try:
            get_payment_provider(slice_.provider.lower())
        except ValueError as exc:
            raise ValidationError(detail=str(exc), error_code="INVALID_PROVIDER") from exc

    # Lock the order first so a concurrent split / single payment cannot both
    # pass the state checks below.
    order = await _load_order_locked(db, order_id)
    if order.user_id != user_id:
        raise NotFoundError(resource="Order")

    from app.modules.orders.domain.models import OrderStatus

    if order.status != OrderStatus.PENDING:
        raise ConflictError(
            detail=f"Order {order_id} is not payable in status '{order.status.value}'",
            error_code="ORDER_NOT_PAYABLE",
        )

    # Any existing non-failed payment for this order means a split (or a
    # legacy single payment) is already in flight. Retrying a partially
    # settled split is a separate flow: the client should resume the pending
    # slices via GET /orders/{id}/allocations, not create a second set.
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

    total_requested = sum(s.amount_rial for s in slices)
    if total_requested != order.total:
        raise ValidationError(
            detail=(
                f"The slices total {total_requested} but the order total is {order.total}; "
                "a split tender must cover the order exactly"
            ),
            error_code="ALLOCATION_TOTAL_MISMATCH",
        )

    created: list[tuple[PaymentAllocation, Payment]] = []
    for slice_ in slices:
        if slice_.idempotency_key:
            existing_stmt = select(PaymentAllocation).where(
                PaymentAllocation.idempotency_key == slice_.idempotency_key
            )
            existing = (await db.execute(existing_stmt)).scalar_one_or_none()
            if existing is not None:
                if existing.order_id != order_id:
                    raise ConflictError(
                        detail="Idempotency key already used for another order",
                        error_code="IDEMPOTENCY_KEY_CONFLICT",
                    )
                existing_payment = await db.get(Payment, existing.payment_id)
                if existing_payment is not None:
                    created.append((existing, existing_payment))
                    continue

        payment, allocation = await _create_slice(
            db,
            user_id=user_id,
            order=order,
            slice_=slice_,
        )
        created.append((allocation, payment))

    # Settle internal slices (wallet) inside this transaction. A wallet slice
    # that cannot settle fails the whole split before any gateway redirect —
    # a checkout that half-commits is worse than one that asks again.
    for allocation, payment in created:
        if allocation.provider in _INTERNAL_PROVIDERS and allocation.status == AllocationStatus.PENDING:
            await settle_wallet_allocation(db, allocation=allocation, payment=payment)

    gateway_slices = [
        (allocation, payment)
        for allocation, payment in created
        if allocation.status in (AllocationStatus.PENDING, AllocationStatus.PROCESSING)
    ]
    # One redirect: the first unsettled gateway slice. Subsequent gateway
    # slices are settled by re-entering the flow (their payment ids are
    # returned so the client can chain verifies).
    redirect_url = next(
        (payment.gateway_url for _, payment in gateway_slices if payment.gateway_url),
        None,
    )

    await db.flush()

    paid = await sum_succeeded_allocations(db, order_id=order_id)
    summary = OrderAllocationSummary(
        order_id=order_id,
        order_total_rial=order.total,
        paid_amount_rial=paid,
        pending_amount_rial=sum(
            a.amount_rial for a, _ in created if a.status in (AllocationStatus.PENDING, AllocationStatus.PROCESSING)
        ),
        remaining_amount_rial=max(0, order.total - paid),
        is_fully_paid=paid >= order.total,
        allocations=[to_response(a) for a, _ in created],
    )

    await logger.ainfo(
        "split_tender_created",
        order_id=str(order_id),
        user_id=str(user_id),
        slices=len(created),
        paid_amount_rial=paid,
        redirect=bool(redirect_url),
    )

    return SplitPaymentResponse(
        order_id=order_id,
        payments=[_payment_view(p) for _, p in created],
        allocations=[to_response(a) for a, _ in created],
        redirect_url=redirect_url,
        summary=summary,
    )


def _payment_view(payment: Payment) -> Any:
    from app.modules.payments.schemas.payment import PaymentResponse

    return PaymentResponse.model_validate(payment)


async def _create_slice(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    order: Any,
    slice_: AllocationSliceRequest,
) -> tuple[Payment, PaymentAllocation]:
    """Create the payment row and its allocation for one slice."""
    from app.modules.payments.domain.models import PaymentProvider as PaymentProviderEnum

    provider_name = slice_.provider.lower()
    provider_enum = PaymentProviderEnum(provider_name)

    if provider_name == "wallet":
        from app.modules.wallet.application import wallet_service

        # Locked balance check (FOR UPDATE) so two concurrent wallet slices —
        # or a wallet slice racing a wallet top-up debit — cannot both pass
        # this gate before either debit lands.
        await wallet_service.check_sufficient_balance(db, user_id, slice_.amount_rial)

    payment = Payment(
        order_id=order.id,
        amount=slice_.amount_rial,
        provider=provider_enum,
        status=PaymentStatus.PENDING,
        extra_data={
            "split_tender": True,
            "slice_provider": provider_name,
        },
    )
    db.add(payment)
    await db.flush()

    try:
        get_payment_provider(provider_name)
    except ValueError as exc:  # pragma: no cover - validated by the caller
        raise ValidationError(detail=str(exc), error_code="INVALID_PROVIDER") from exc

    if provider_name not in _INTERNAL_PROVIDERS:
        from app.modules.payments.application.payment_service import (
            _build_callback_url,
            _resolve_gateway,
        )

        try:
            gateway_provider, override_merchant_id = await _resolve_gateway(db, provider_name)
        except ValueError as exc:
            raise ValidationError(detail=str(exc), error_code="INVALID_PROVIDER") from exc

        callback_url = _build_callback_url(provider_name, payment.id)
        gateway_result = await gateway_provider.create_payment(
            amount=slice_.amount_rial,
            order_id=order.id,
            callback_url=callback_url,
            description=slice_.description or "پرداخت ترکیبی سفارش",
        )

        from app.modules.payments.application.payment_service import _record_transaction

        await _record_transaction(
            db,
            payment_id=payment.id,
            amount=slice_.amount_rial,
            tx_type=PaymentTransactionType.CHARGE,
            status="success" if gateway_result.success else "failed",
            provider_response=gateway_result.raw_response,
        )

        if gateway_result.success:
            payment.authority = gateway_result.authority
            payment.gateway_url = gateway_result.gateway_url
            payment.status = PaymentStatus.PROCESSING
            payment.extra_data = {
                **(payment.extra_data or {}),
                **(gateway_result.raw_response or {}),
                "zarinpal_merchant_id": override_merchant_id,
            }
        else:
            payment.status = PaymentStatus.FAILED
            payment.extra_data = {
                **(payment.extra_data or {}),
                "error_code": gateway_result.error_code,
                "error_message": gateway_result.error_message,
            }

    allocation = PaymentAllocation(
        order_id=order.id,
        payment_id=payment.id,
        amount_rial=slice_.amount_rial,
        provider=provider_name,
        status=(
            AllocationStatus.PENDING
            if payment.status != PaymentStatus.FAILED
            else AllocationStatus.FAILED
        ),
        idempotency_key=slice_.idempotency_key,
        failure_reason=(
            (payment.extra_data or {}).get("error_message")
            if payment.status == PaymentStatus.FAILED
            else None
        ),
        extra_data={"split_tender": True},
    )
    db.add(allocation)
    try:
        await db.flush()
    except IntegrityError as exc:
        # A racing duplicate idempotency key: recover by returning the winner.
        if slice_.idempotency_key:
            existing_stmt = select(PaymentAllocation).where(
                PaymentAllocation.idempotency_key == slice_.idempotency_key
            )
            existing = (await db.execute(existing_stmt)).scalar_one_or_none()
            if existing is not None and existing.order_id == order.id:
                existing_payment = await db.get(Payment, existing.payment_id)
                if existing_payment is not None:
                    return existing_payment, existing
        raise PaymentError(
            detail="Could not record the payment slice",
            error_code="ALLOCATION_CREATE_FAILED",
        ) from exc

    if payment.status == PaymentStatus.FAILED:
        raise PaymentError(
            detail=(payment.extra_data or {}).get("error_message") or "Gateway rejected the slice",
            error_code="GATEWAY_ERROR",
        )

    return payment, allocation


# ── Settlement ────────────────────────────────────────────────────────────


async def settle_wallet_allocation(
    db: AsyncSession,
    *,
    allocation: PaymentAllocation,
    payment: Payment,
) -> PaymentAllocationResponse:
    """Debit the wallet for a slice and settle both payment and allocation.

    The wallet debit goes through ``wallet_service.debit``, which locks the
    wallet row and decides sufficiency from the ledger SUM — the same atomic
    primitive every other wallet movement uses. The debit's transaction id is
    recorded on the allocation so the movement is traceable.
    """
    if allocation.provider != "wallet":
        raise ValidationError(
            detail="settle_wallet_allocation called for a non-wallet slice",
            error_code="NOT_A_WALLET_SLICE",
        )
    if allocation.status == AllocationStatus.SUCCEEDED:
        return to_response(allocation)

    from app.modules.wallet.application import wallet_service
    from app.modules.wallet.domain.models import WalletTransactionType

    from app.modules.orders.domain.models import Order

    payer_order = await db.get(Order, payment.order_id) if payment.order_id else None
    if payer_order is None:
        raise PaymentError(
            detail="Wallet slice is not linked to an order",
            error_code="WALLET_PAYMENT_INVALID",
        )

    tx = await wallet_service.debit(
        db,
        user_id=payer_order.user_id,
        amount=allocation.amount_rial,
        tx_type=WalletTransactionType.DEBIT,
        reference_type="payment_allocation",
        reference_id=allocation.id,
        description="پرداخت بخشی از سفارش از کیف پول",
    )

    # The wallet provider has no gateway: the payment completes in-line.
    payment.status = PaymentStatus.COMPLETED
    payment.provider_transaction_id = f"WALLETALLOC-{allocation.id.hex[:12].upper()}"
    payment.extra_data = {
        **(payment.extra_data or {}),
        "wallet_transaction_id": str(tx.id),
    }

    allocation.status = AllocationStatus.SUCCEEDED
    allocation.settled_at = datetime.now(UTC)
    allocation.wallet_transaction_id = tx.id
    await db.flush()

    await logger.ainfo(
        "wallet_allocation_settled",
        allocation_id=str(allocation.id),
        payment_id=str(payment.id),
        amount_rial=allocation.amount_rial,
        wallet_transaction_id=str(tx.id),
    )

    # Completing the order is a separate step so the lock ordering stays
    # payment → allocation → order.
    await _maybe_complete_order(
        db,
        order_id=allocation.order_id,
        allocation=allocation,
    )
    return to_response(allocation)


async def settle_allocation_from_payment(
    db: AsyncSession,
    *,
    payment: Payment,
) -> PaymentAllocationResponse | None:
    """Settle the allocation behind a payment that just verified.

    Called from ``payment_service.verify_payment`` **after** the payment row
    has been completed, so the payment lock is already held by the caller and
    the order lock taken here is always the last one (payment → allocation →
    order). Returns ``None`` for payments that are not part of a split tender,
    which is how the legacy single-payment path stays untouched.
    """
    stmt = (
        select(PaymentAllocation)
        .where(PaymentAllocation.payment_id == payment.id)
        .with_for_update()
    )
    allocation = (await db.execute(stmt)).scalar_one_or_none()
    if allocation is None:
        return None

    if allocation.status == AllocationStatus.SUCCEEDED:
        await logger.ainfo(
            "allocation_already_settled",
            allocation_id=str(allocation.id),
            payment_id=str(payment.id),
        )
        return to_response(allocation)

    allocation.status = AllocationStatus.SUCCEEDED
    allocation.settled_at = datetime.now(UTC)
    allocation.failure_reason = None
    await db.flush()

    await logger.ainfo(
        "allocation_settled",
        allocation_id=str(allocation.id),
        order_id=str(allocation.order_id),
        payment_id=str(payment.id),
        amount_rial=allocation.amount_rial,
    )

    await _maybe_complete_order(db, order_id=allocation.order_id, allocation=allocation)
    return to_response(allocation)


async def mark_allocation_failed(
    db: AsyncSession,
    *,
    payment: Payment,
    reason: str | None = None,
) -> PaymentAllocationResponse | None:
    """Mark a split slice failed (gateway declined / customer cancelled)."""
    stmt = select(PaymentAllocation).where(PaymentAllocation.payment_id == payment.id).with_for_update()
    allocation = (await db.execute(stmt)).scalar_one_or_none()
    if allocation is None:
        return None
    if allocation.status == AllocationStatus.SUCCEEDED:
        # A succeeded slice must not be un-settled by a late failure callback:
        # the money moved. A refund is the only way back.
        await logger.awarning(
            "allocation_failed_after_success_ignored",
            allocation_id=str(allocation.id),
            payment_id=str(payment.id),
        )
        return to_response(allocation)
    allocation.status = AllocationStatus.FAILED
    allocation.failure_reason = reason
    await db.flush()
    return to_response(allocation)


async def _maybe_complete_order(
    db: AsyncSession,
    *,
    order_id: uuid.UUID,
    allocation: PaymentAllocation,
) -> bool:
    """Confirm the order when the slices now cover the total.

    Returns True when this call performed the transition. Locking the order
    here (after the payment and allocation locks are held) serialises rival
    settlers; the sum is re-read under that lock and ``is_completing`` is
    claimed only once.
    """
    from app.modules.orders.domain.models import Order, OrderStatus, OrderStatusHistory

    # Lock the order row. Any concurrent settler waits here, then re-reads a
    # sum that already includes this allocation.
    order_stmt = select(Order).where(Order.id == order_id).with_for_update()
    order = (await db.execute(order_stmt)).scalar_one_or_none()
    if order is None:
        raise NotFoundError(resource="Order")

    if order.status != OrderStatus.PENDING:
        # Already confirmed (by this or a rival settlement) or no longer
        # payable. Either way this allocation must not transition it again.
        await logger.ainfo(
            "order_already_settled_for_allocation",
            order_id=str(order_id),
            order_status=order.status.value,
            allocation_id=str(allocation.id),
        )
        return False

    paid = await sum_succeeded_allocations(db, order_id=order_id)
    if paid < order.total:
        await logger.ainfo(
            "order_partially_paid",
            order_id=str(order_id),
            paid=paid,
            total=order.total,
            allocation_id=str(allocation.id),
        )
        return False
    if paid > order.total:
        # Overpayment: the slices were created against the order total, so
        # this means a slice amount was mutated after creation. Confirm would
        # book revenue that does not match the order; refuse loudly.
        raise PaymentError(
            detail=(
                f"Allocations for order {order_id} total {paid}, "
                f"exceeding the order total {order.total}"
            ),
            error_code="ALLOCATION_OVERPAYMENT",
        )

    # Claim the completion marker. The partial unique index turns a second
    # claim into an IntegrityError rather than a second order transition.
    if not allocation.is_completing:
        allocation.is_completing = True
        try:
            await db.flush()
        except IntegrityError as exc:
            raise ConflictError(
                detail="This order was already completed by another allocation",
                error_code="ALLOCATION_ALREADY_COMPLETED",
            ) from exc

    order.status = OrderStatus.CONFIRMED
    db.add(
        OrderStatusHistory(
            order_id=order.id,
            from_status=OrderStatus.PENDING.value,
            to_status=OrderStatus.CONFIRMED.value,
            changed_by=None,
            reason="Split tender completed (all allocations settled)",
        )
    )
    await db.flush()

    try:
        from app.shared.events.outbox_service import OutboxService

        await OutboxService.publish(
            db,
            event_type="OrderConfirmed",
            aggregate_type="order",
            aggregate_id=str(order.id),
            payload={
                "order_id": str(order.id),
                "payment_id": str(allocation.payment_id),
                "total": order.total,
                "paid_amount_rial": paid,
                "split_tender": True,
            },
        )
    except Exception as exc:  # noqa: BLE001 — outbox is best-effort here
        await logger.awarning("outbox_publish_skipped", error=str(exc))

    await logger.ainfo(
        "order_completed_by_split_tender",
        order_id=str(order_id),
        allocation_id=str(allocation.id),
        paid_amount_rial=paid,
    )
    return True


# ── Refunds (v1: per-payment, recorded per allocation) ────────────────────


async def refund_allocation(
    db: AsyncSession,
    *,
    allocation_id: uuid.UUID,
    amount: int,
    actor_id: uuid.UUID,
    reason: str | None = None,
) -> dict[str, Any]:
    """Refund the payment behind one allocation through the existing flow.

    v1 refuses an amount smaller than the allocation ("per-allocation refund"):
    partial refunds of a split slice would need per-allocation refund bookkeeping
    the existing ``refund_payment`` does not model. Splitting a slice's refund
    is a documented manual operation for now.
    """
    stmt = select(PaymentAllocation).where(PaymentAllocation.id == allocation_id).with_for_update()
    allocation = (await db.execute(stmt)).scalar_one_or_none()
    if allocation is None:
        raise NotFoundError(resource="PaymentAllocation")

    if allocation.status not in (
        AllocationStatus.SUCCEEDED,
        AllocationStatus.PARTIALLY_REFUNDED,
    ):
        raise ValidationError(
            detail="فقط پرداخت‌های موفق قابل استرداد هستند",
            error_code="ALLOCATION_NOT_REFUNDABLE",
        )

    refundable = allocation.amount_rial - allocation.refunded_rial
    if refundable <= 0:
        raise ConflictError(
            detail="این سهم قبلاً به‌طور کامل مسترد شده است",
            error_code="ALLOCATION_ALREADY_REFUNDED",
        )
    if amount != refundable:
        raise ValidationError(
            detail=(
                f"Split-tender refunds are per allocation in v1: this slice has "
                f"{refundable} IRR refundable, requested {amount}. Partial refunds of a "
                f"single slice must be handled manually."
            ),
            error_code="ALLOCATION_PARTIAL_REFUND_UNSUPPORTED",
        )

    from app.modules.payments.application import payment_service

    payment = await db.get(Payment, allocation.payment_id)
    if payment is None:
        raise NotFoundError(resource="Payment")

    refund = await payment_service.refund_payment(
        db,
        payment_id=payment.id,
        amount=amount,
        reason=reason,
        actor_id=actor_id,
    )

    allocation.refunded_rial += amount
    allocation.status = AllocationStatus.REFUNDED
    await db.flush()

    await logger.ainfo(
        "allocation_refunded",
        allocation_id=str(allocation.id),
        payment_id=str(payment.id),
        amount=amount,
    )
    return {
        "allocation_id": str(allocation.id),
        "payment_id": str(payment.id),
        "amount": amount,
        "refund_id": str(refund.id),
        "refund_status": refund.status.value,
    }
