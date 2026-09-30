"""Subscription lifecycle and recurring billing.

The billing path deliberately reuses the existing order pipeline: each cycle
creates a real ``Order`` (so invoices, accounting journal entries, and the
audit trail all see it like any other order) and charges the customer's
tokenized card through ``payments.tokenization_service.charge_saved_method``.
Nothing new touches money; this module only decides *when* to call what.

Two degradation paths, both intentional:

* **No saved card** (or the gateway cannot tokenize): the cycle still creates
  the order and marks the billing ``PENDING`` with ``renewal_notified``, and
  the customer pays manually from their account. The subscription stays
  ``ACTIVE``.
* **Declined charge**: the billing is ``FAILED``, ``failure_count`` grows, and
  the subscription moves to ``PAST_DUE``. The next run retries. After
  ``MAX_CONSECUTIVE_FAILURES`` the subscription is ``EXPIRED`` rather than
  cancelled — no further charges are attempted, but the customer's history is
  preserved and support can reactivate it.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import select

from app.core.exceptions.handlers import (
    ConflictError,
    NotFoundError,
    ValidationError,
)
from app.modules.orders.domain.models import Order, OrderItem, OrderStatus
from app.modules.subscriptions.application import schedule
from app.modules.subscriptions.domain.models import (
    BillingStatus,
    Subscription,
    SubscriptionBilling,
    SubscriptionInterval,
    SubscriptionItem,
    SubscriptionStatus,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

#: Consecutive failed cycles before a subscription expires. Four monthly
#: failures is roughly a quarter of silence — long enough to survive a
#: temporary gateway limit, short enough to stop billing a dead card.
MAX_CONSECUTIVE_FAILURES = 4


# ── Creation ────────────────────────────────────────────────────────────────


async def create_subscription(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    name: str,
    interval: SubscriptionInterval,
    interval_count: int,
    items: list[dict[str, Any]],
    saved_method_id: uuid.UUID | None = None,
    custom_interval_days: int | None = None,
    shipping_address_snapshot: dict[str, Any] | None = None,
    notes: str | None = None,
    idempotency_key: str | None = None,
    now: datetime | None = None,
) -> Subscription:
    """Create an ACTIVE subscription whose first charge happens immediately.

    ``items`` is ``[{"variant_id": UUID, "quantity": int}]``; prices are
    resolved server-side from the catalog at creation time and snapshotted —
    a caller-supplied price is never trusted (the reseller service learned
    this lesson the same way).
    """
    from app.modules.catalog.domain.models import ProductVariant

    now = now or datetime.now(UTC)

    if not items:
        raise ValidationError(
            detail="اشتراک باید حداقل یک قلم کالا داشته باشد",
            error_code="EMPTY_SUBSCRIPTION",
        )
    if interval_count < 1:
        raise ValidationError(
            detail="تعداد دوره باید حداقل ۱ باشد",
            error_code="INVALID_INTERVAL_COUNT",
        )
    if interval == SubscriptionInterval.CUSTOM_DAYS and not custom_interval_days:
        raise ValidationError(
            detail="برای دوره سفارشی، تعداد روز الزامی است",
            error_code="MISSING_CUSTOM_DAYS",
        )

    if idempotency_key:
        existing = (
            await db.execute(
                select(Subscription).where(
                    Subscription.user_id == user_id,
                    Subscription.idempotency_key == idempotency_key,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing

    total = 0
    subscription_items: list[SubscriptionItem] = []
    for entry in items:
        variant_id = entry.get("variant_id")
        quantity = int(entry.get("quantity", 1))
        if quantity < 1:
            raise ValidationError(
                detail="تعداد هر قلم باید حداقل ۱ باشد",
                error_code="INVALID_QUANTITY",
            )
        variant = await db.get(ProductVariant, variant_id, with_for_update=False)
        if variant is None or not variant.is_active or variant.price <= 0:
            raise NotFoundError(
                resource="ProductVariant",
                detail="کالای انتخابی موجود یا فعال نیست",
            )
        line_total = int(variant.price) * quantity
        total += line_total
        product_name = entry.get("product_name") or f"{variant.sku}"
        subscription_items.append(
            SubscriptionItem(
                variant_id=variant.id,
                product_name=product_name,
                sku=variant.sku,
                quantity=quantity,
                unit_price_rial=int(variant.price),
            )
        )

    if total <= 0:
        raise ValidationError(
            detail="مبلغ اشتراک باید بیشتر از صفر باشد",
            error_code="INVALID_TOTAL",
        )

    subscription = Subscription(
        user_id=user_id,
        name=name,
        status=SubscriptionStatus.ACTIVE,
        interval=interval,
        interval_count=interval_count,
        custom_interval_days=custom_interval_days,
        saved_method_id=saved_method_id,
        total_per_cycle=total,
        shipping_address_snapshot=shipping_address_snapshot,
        notes=notes,
        started_at=now,
        next_billing_at=now,
        idempotency_key=idempotency_key,
        items=subscription_items,
    )
    db.add(subscription)
    await db.flush()

    await logger.ainfo(
        "subscription_created",
        subscription_id=str(subscription.id),
        user_id=str(user_id),
        total_rial=total,
        interval=interval.value,
    )
    return subscription


# ── Lifecycle ───────────────────────────────────────────────────────────────


async def get_subscription(
    db: AsyncSession,
    *,
    subscription_id: uuid.UUID,
    user_id: uuid.UUID | None = None,
) -> Subscription:
    """Fetch a subscription, optionally scoped to its owner."""
    stmt = select(Subscription).where(Subscription.id == subscription_id)
    if user_id is not None:
        stmt = stmt.where(Subscription.user_id == user_id)
    subscription = (await db.execute(stmt)).scalar_one_or_none()
    if subscription is None:
        raise NotFoundError(resource="Subscription")
    return subscription


async def pause_subscription(
    db: AsyncSession, *, subscription_id: uuid.UUID, user_id: uuid.UUID
) -> Subscription:
    """Pause billing. The next cycle is not charged; the plan is preserved."""
    subscription = await get_subscription(db, subscription_id=subscription_id, user_id=user_id)
    if subscription.status not in (SubscriptionStatus.ACTIVE, SubscriptionStatus.PAST_DUE):
        raise ConflictError(
            detail=f"اشتراک در وضعیت «{subscription.status.value}» قابل توقف نیست",
            error_code="SUBSCRIPTION_NOT_PAUSABLE",
        )
    subscription.status = SubscriptionStatus.PAUSED
    await db.flush()
    await logger.ainfo("subscription_paused", subscription_id=str(subscription_id))
    return subscription


async def resume_subscription(
    db: AsyncSession,
    *,
    subscription_id: uuid.UUID,
    user_id: uuid.UUID,
    now: datetime | None = None,
) -> Subscription:
    """Resume a paused subscription, billing from the resume moment.

    The pause window is not back-billed: the schedule re-anchors to now, so a
    customer who paused for two months is not charged for the two months they
    received nothing.
    """
    now = now or datetime.now(UTC)
    subscription = await get_subscription(db, subscription_id=subscription_id, user_id=user_id)
    if subscription.status != SubscriptionStatus.PAUSED:
        raise ConflictError(
            detail=f"اشتراک در وضعیت «{subscription.status.value}» قابل فعال‌سازی نیست",
            error_code="SUBSCRIPTION_NOT_RESUMABLE",
        )
    subscription.status = SubscriptionStatus.ACTIVE
    subscription.next_billing_at = now
    subscription.failure_count = 0
    await db.flush()
    await logger.ainfo("subscription_resumed", subscription_id=str(subscription_id))
    return subscription


async def cancel_subscription(
    db: AsyncSession,
    *,
    subscription_id: uuid.UUID,
    user_id: uuid.UUID,
    reason: str | None = None,
    now: datetime | None = None,
) -> Subscription:
    """Cancel for good. No further cycles are billed or scheduled."""
    now = now or datetime.now(UTC)
    subscription = await get_subscription(db, subscription_id=subscription_id, user_id=user_id)
    if subscription.status == SubscriptionStatus.CANCELLED:
        return subscription  # idempotent
    subscription.status = SubscriptionStatus.CANCELLED
    subscription.cancelled_at = now
    subscription.cancelled_reason = reason
    subscription.next_billing_at = None
    await db.flush()
    await logger.ainfo(
        "subscription_cancelled",
        subscription_id=str(subscription_id),
        reason=reason,
    )
    return subscription


# ── Billing ─────────────────────────────────────────────────────────────────


async def _create_cycle_order(
    db: AsyncSession,
    subscription: Subscription,
    *,
    period_index: int,
) -> Order:
    """Create the order a billing cycle is paying for.

    A real order — not a synthetic payment — so the invoice, the accounting
    journal entry, and the audit trail treat a subscription charge exactly
    like any other purchase.
    """
    from app.modules.orders.application.order_service import generate_unique_order_number

    order_number = await generate_unique_order_number(db)
    order = Order(
        user_id=subscription.user_id,
        order_number=order_number,
        status=OrderStatus.PENDING,
        subtotal=subscription.total_per_cycle,
        shipping_cost=0,
        tax=0,
        discount_amount=0,
        total=subscription.total_per_cycle,
        shipping_address_snapshot=subscription.shipping_address_snapshot,
        notes=f"اشتراک «{subscription.name}» — دوره {period_index + 1}",
        idempotency_key=f"sub:{subscription.id}:period:{period_index}",
    )
    db.add(order)
    await db.flush()

    for item in subscription.items:
        db.add(
            OrderItem(
                order_id=order.id,
                variant_id=item.variant_id,
                product_name=item.product_name,
                variant_info=None,
                sku=item.sku,
                quantity=item.quantity,
                unit_price=item.unit_price_rial,
                total_price=item.unit_price_rial * item.quantity,
            )
        )
    await db.flush()
    return order


async def bill_cycle(
    db: AsyncSession,
    subscription: Subscription,
    *,
    now: datetime | None = None,
) -> SubscriptionBilling:
    """Bill one cycle: create the order, charge the saved card, advance.

    Idempotent per ``(subscription, period_index)``: a retried run finds the
    existing billing row and returns it without charging again.
    """
    now = now or datetime.now(UTC)
    period_index = schedule.next_period_index(subscription)

    existing = (
        await db.execute(
            select(SubscriptionBilling).where(
                SubscriptionBilling.subscription_id == subscription.id,
                SubscriptionBilling.period_index == period_index,
            )
        )
    ).scalar_one_or_none()
    if existing is not None and existing.status != BillingStatus.PENDING:
        return existing

    billing = existing or SubscriptionBilling(
        subscription_id=subscription.id,
        period_index=period_index,
        status=BillingStatus.PENDING,
        amount_rial=subscription.total_per_cycle,
    )
    if existing is None:
        db.add(billing)
        await db.flush()

    # ``or 0`` guards a row whose column default has not been applied yet
    # (a fresh instance before its first flush) — the count is bookkeeping,
    # and None must not break a billing cycle.
    billing.attempt_count = (billing.attempt_count or 0) + 1

    order = await _create_cycle_order(db, subscription, period_index=period_index)
    billing.order_id = order.id

    # No card on file: the order waits for the customer. This is a first-class
    # path, not an error — tokenization is not available on every gateway.
    if subscription.saved_method_id is None:
        billing.status = BillingStatus.SKIPPED
        billing.renewal_notified = True
        billing.last_error = "no_saved_method"
        subscription.last_billed_at = now
        subscription.next_billing_at = schedule.advance(
            subscription.next_billing_at or now, subscription
        )
        await db.flush()
        await logger.ainfo(
            "subscription_cycle_needs_manual_payment",
            subscription_id=str(subscription.id),
            order_id=str(order.id),
            period_index=period_index,
        )
        return billing

    from app.modules.payments.application import tokenization_service

    try:
        payment, result = await tokenization_service.charge_saved_method(
            db,
            user_id=subscription.user_id,
            method_id=subscription.saved_method_id,
            amount=subscription.total_per_cycle,
            order_id=order.id,
            description=f"اشتراک {subscription.name} — دوره {period_index + 1}",
        )
    except Exception as exc:  # noqa: BLE001 - every failure is a dunning state
        billing.status = BillingStatus.FAILED
        billing.last_error = str(exc)[:500]
        subscription.failure_count += 1
        await _apply_failure_policy(subscription, now)
        await db.flush()
        await logger.awarning(
            "subscription_charge_raised",
            subscription_id=str(subscription.id),
            error=str(exc),
        )
        return billing

    billing.payment_id = payment.id
    if result.success:
        billing.status = BillingStatus.PAID
        billing.billed_at = now
        billing.last_error = None
        subscription.status = SubscriptionStatus.ACTIVE
        subscription.failure_count = 0
        subscription.last_billed_at = now
        subscription.next_billing_at = schedule.advance(
            subscription.next_billing_at or now, subscription
        )
    else:
        billing.status = BillingStatus.FAILED
        billing.last_error = (result.error_message or "charge declined")[:500]
        subscription.failure_count += 1
        await _apply_failure_policy(subscription, now)

    await db.flush()
    await logger.ainfo(
        "subscription_cycle_billed",
        subscription_id=str(subscription.id),
        period_index=period_index,
        status=billing.status.value,
        amount_rial=billing.amount_rial,
    )
    return billing


async def _apply_failure_policy(subscription: Subscription, now: datetime) -> None:
    """Move a subscription to PAST_DUE, or EXPIRED after too many failures."""
    if subscription.failure_count >= MAX_CONSECUTIVE_FAILURES:
        subscription.status = SubscriptionStatus.EXPIRED
        subscription.next_billing_at = None
        return
    subscription.status = SubscriptionStatus.PAST_DUE
    # Retry soon (not a full interval later): the customer is still reachable
    # and a temporary gateway limit usually clears within a day.
    subscription.next_billing_at = schedule.advance(now, subscription)


async def list_due_subscriptions(
    db: AsyncSession, *, now: datetime | None = None, limit: int = 200
) -> list[Subscription]:
    """Subscriptions whose billing date has arrived, oldest first."""
    now = now or datetime.now(UTC)
    rows = (
        await db.execute(
            select(Subscription)
            .where(
                Subscription.status.in_(
                    (SubscriptionStatus.ACTIVE, SubscriptionStatus.PAST_DUE)
                ),
                Subscription.next_billing_at.is_not(None),
                Subscription.next_billing_at <= now,
            )
            .order_by(Subscription.next_billing_at.asc())
            .limit(limit)
        )
    ).scalars().all()
    return list(rows)


async def run_due_billings(
    db: AsyncSession, *, now: datetime | None = None, limit: int = 200
) -> dict[str, int]:
    """Process every due subscription once. Returns a small run summary.

    Each subscription is billed in its own savepoint so one broken row cannot
    poison the batch — the worker logs the failure and moves on.
    """
    now = now or datetime.now(UTC)
    due = await list_due_subscriptions(db, now=now, limit=limit)
    summary = {"due": len(due), "paid": 0, "failed": 0, "skipped": 0, "errors": 0}

    for subscription in due:
        try:
            billing = await bill_cycle(db, subscription, now=now)
        except Exception as exc:  # noqa: BLE001 - one bad row must not stop the run
            summary["errors"] += 1
            await logger.aerror(
                "subscription_billing_run_error",
                subscription_id=str(subscription.id),
                error=str(exc),
            )
            continue
        if billing.status == BillingStatus.PAID:
            summary["paid"] += 1
        elif billing.status == BillingStatus.FAILED:
            summary["failed"] += 1
        else:
            summary["skipped"] += 1

    await logger.ainfo("subscription_billing_run", **summary)
    return summary


async def list_user_subscriptions(
    db: AsyncSession, *, user_id: uuid.UUID
) -> list[Subscription]:
    """All subscriptions for one customer, newest first."""
    rows = (
        await db.execute(
            select(Subscription)
            .where(Subscription.user_id == user_id)
            .order_by(Subscription.created_at.desc())
        )
    ).scalars().all()
    return list(rows)
