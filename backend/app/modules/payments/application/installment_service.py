"""Installment plans: schedule maths, create, list, settle.

Schedule maths (integer Rials, exact)
-------------------------------------
``build_installment_schedule`` splits ``total_rial`` into
``num_installments`` integer slices:

* the first installment is ``first_installment_rial`` (the prepayment taken at
  checkout),
* the remaining ``n - 1`` slices are equal, and the **last** slice absorbs the
  rounding remainder.

The invariant ``first + sum(rest) == total`` is asserted before the row is
written. A rounding scheme that distributed the remainder into the first slice
would make the prepayment (the amount actually charged immediately) depend on
the division, which is harder to explain on a receipt; putting it last keeps
"pay X now, then Y monthly" honest for the customer.

Jalali dates
------------
Due dates are stored Gregorian (for scheduling/indexing) **and** as a Jalali
label via the codebase's existing ``gregorian_to_jalali`` converter, so the
customer-facing schedule needs no client-side date library.

Provider capability
-------------------
A plan can only be created for a provider that advertises
``supports_installments``. No public Zarinpal v4 / IDPay v1.1 endpoint creates
an installment plan (see the capability notes in the provider adapters), so in
production only gateways whose merchant contract provides the API will report
True; the mock provider implements it so the flow is testable end to end.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import select

from sqlalchemy.exc import IntegrityError

from app.core.exceptions.handlers import (
    ConflictError,
    NotFoundError,
    PaymentError,
    ValidationError,
)
from app.modules.orders.application.invoice_service import gregorian_to_jalali
from app.modules.payments.domain.installment_models import (
    InstallmentPlan,
    InstallmentPlanStatus,
)
from app.modules.payments.infrastructure.provider_factory import get_payment_provider
from app.modules.payments.schemas.installment import (
    InstallmentPlanResponse,
    InstallmentScheduleEntry,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# Durations offered when a gateway does not advertise its own. Matches the
# Iranian market's common 2 / 4 / 6 / 12 month offerings.
DEFAULT_INSTALLMENT_MONTHS: tuple[int, ...] = (2, 4, 6, 12)
MAX_INSTALLMENTS = 24


def format_jalali_label(d: date) -> str:
    """``"1404/07/05"`` — the Jalali display label used on statements."""
    jy, jm, jd = gregorian_to_jalali(d.year, d.month, d.day)
    return f"{jy:04d}/{jm:02d}/{jd:02d}"


def add_jalali_months(d: date, months: int) -> date:
    """Add months to a Gregorian date, clamping the day to the target month.

    A due date on the 31st must not silently roll into the next month when the
    target month is shorter; clamping keeps every due date inside the month
    the customer was quoted.
    """
    total = d.month - 1 + months
    year = d.year + total // 12
    month = total % 12 + 1
    # Clamp the day to the last day of the target month.
    if month == 12:
        next_month_first = date(year + 1, 1, 1)
    else:
        next_month_first = date(year, month + 1, 1)
    last_day = (next_month_first - timedelta(days=1)).day
    return date(year, month, min(d.day, last_day))


def split_remaining_amounts(total_rial: int, remaining_count: int) -> list[int]:
    """Split ``total_rial`` into ``remaining_count`` integer Rials.

    The last slice absorbs the remainder, so the sum is exact. Pure integer
    arithmetic — no floats anywhere.
    """
    if remaining_count <= 0:
        return []
    base = total_rial // remaining_count
    amounts = [base] * (remaining_count - 1)
    amounts.append(total_rial - base * (remaining_count - 1))
    return amounts


def build_installment_schedule(
    *,
    total_rial: int,
    num_installments: int,
    first_installment_rial: int,
    start_date: date,
    interval_months: int = 1,
) -> list[dict[str, Any]]:
    """Build the JSONB schedule: ``[{due_date_jalali, due_date, amount_rial, ...}]``.

    Entry 0 is the prepayment (due immediately, ``due_date == start_date``);
    entries 1..n-1 are monthly. The integer-sum invariant is asserted here so
    a caller can never persist a schedule that does not reconstruct the total.
    """
    if num_installments < 2:
        raise ValidationError(
            detail="An installment plan needs at least 2 installments",
            error_code="INVALID_INSTALLMENT_COUNT",
        )
    if num_installments > MAX_INSTALLMENTS:
        raise ValidationError(
            detail=f"At most {MAX_INSTALLMENTS} installments are supported",
            error_code="INVALID_INSTALLMENT_COUNT",
        )
    if total_rial <= 0:
        raise ValidationError(
            detail="Installment total must be a positive integer (IRR)",
            error_code="INVALID_AMOUNT",
        )
    if first_installment_rial <= 0 or first_installment_rial > total_rial:
        raise ValidationError(
            detail=(
                f"First installment ({first_installment_rial}) must be between 1 "
                f"and the total ({total_rial})"
            ),
            error_code="INVALID_FIRST_INSTALLMENT",
        )

    remaining_total = total_rial - first_installment_rial
    remaining = split_remaining_amounts(remaining_total, num_installments - 1)

    schedule: list[dict[str, Any]] = []
    # Entry 0: the prepayment, settled at plan creation.
    schedule.append(
        {
            "due_date_jalali": format_jalali_label(start_date),
            "due_date": start_date.isoformat(),
            "amount_rial": first_installment_rial,
            "status": "pending",
            "paid_at": None,
            "is_prepayment": True,
        }
    )
    for index, amount in enumerate(remaining, start=1):
        due = add_jalali_months(start_date, interval_months * index)
        schedule.append(
            {
                "due_date_jalali": format_jalali_label(due),
                "due_date": due.isoformat(),
                "amount_rial": amount,
                "status": "pending",
                "paid_at": None,
                "is_prepayment": False,
            }
        )

    # The invariant: the schedule reconstructs the total exactly.
    scheduled_total = sum(int(entry["amount_rial"]) for entry in schedule)
    assert scheduled_total == total_rial, (
        f"Installment schedule imbalance: {scheduled_total} != {total_rial}"
    )
    return schedule


def next_unpaid_due_date(schedule: list[dict[str, Any]]) -> date | None:
    """The earliest unpaid due date, or ``None`` when everything is settled."""
    pending = [
        date.fromisoformat(str(entry["due_date"]))
        for entry in schedule
        if entry.get("status") != "paid" and entry.get("due_date")
    ]
    return min(pending) if pending else None


def to_response(plan: InstallmentPlan) -> InstallmentPlanResponse:
    """Client-facing view of a plan, with the schedule entries typed."""
    entries = [
        InstallmentScheduleEntry(
            due_date_jalali=str(entry.get("due_date_jalali", "")),
            due_date=date.fromisoformat(str(entry["due_date"]))
            if entry.get("due_date")
            else None,
            amount_rial=int(entry.get("amount_rial", 0)),
            status=str(entry.get("status", "pending")),
            paid_at=datetime.fromisoformat(str(entry["paid_at"]))
            if entry.get("paid_at")
            else None,
            is_prepayment=bool(entry.get("is_prepayment", False)),
        )
        for entry in (plan.schedule or [])
    ]
    return InstallmentPlanResponse(
        id=plan.id,
        order_id=plan.order_id,
        user_id=plan.user_id,
        provider=plan.provider,
        total_rial=plan.total_rial,
        num_installments=plan.num_installments,
        first_installment_rial=plan.first_installment_rial,
        remaining_rial=plan.total_rial - plan.first_installment_rial,
        schedule=entries,
        status=plan.status,
        next_due_date=plan.next_due_date,
        paid_count=plan.paid_count,
        created_at=plan.created_at,
        updated_at=plan.updated_at,
    )


# ── Capability reporting ──────────────────────────────────────────────────


def installment_options_for(provider_name: str) -> tuple[bool, tuple[int, ...]]:
    """``(supported, months)`` for a provider, without raising on unknown names.

    Used by the checkout UI: an unknown or unsupported provider simply reports
    ``(False, ())`` so the installment option is hidden rather than erroring.
    """
    try:
        provider = get_payment_provider(provider_name)
    except ValueError:
        return False, ()
    supported = bool(getattr(provider, "supports_installments", False))
    months = tuple(getattr(provider, "installment_options_months", ()) or ())
    if supported and not months:
        months = DEFAULT_INSTALLMENT_MONTHS
    return supported, months


# ── CRUD ──────────────────────────────────────────────────────────────────


async def create_plan(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    order_id: uuid.UUID,
    provider_name: str,
    num_installments: int,
    first_installment_rial: int,
    start_date: date | None = None,
    interval_months: int = 1,
) -> InstallmentPlanResponse:
    """Create an installment plan for an order.

    The order total is authoritative: the plan is built from ``order.total``,
    never from a client-supplied total. A client-supplied
    ``first_installment_rial`` is validated against it.
    """
    from app.modules.orders.domain.models import Order, OrderStatus

    supported, months = installment_options_for(provider_name)
    if not supported:
        raise ValidationError(
            detail=(
                f"درگاه «{provider_name}» پرداخت اقساطی را پشتیبانی نمی‌کند. "
                f"Gateway '{provider_name}' does not support installment plans."
            ),
            error_code="PROVIDER_NO_INSTALLMENTS",
        )
    if months and num_installments not in months:
        raise ValidationError(
            detail=(
                f"Gateway '{provider_name}' offers "
                f"{', '.join(str(m) for m in months)}-month plans, not {num_installments}"
            ),
            error_code="INVALID_INSTALLMENT_COUNT",
        )

    # Lock the order: two concurrent plan creations would both pass the
    # existing-plan check and the second would violate uq_installment_plans_order_id.
    order = await db.get(Order, order_id, with_for_update=True)
    if order is None or order.user_id != user_id:
        raise NotFoundError(resource="Order")
    if order.status != OrderStatus.PENDING:
        raise ConflictError(
            detail=f"Order {order_id} is not payable in status '{order.status.value}'",
            error_code="ORDER_NOT_PAYABLE",
        )

    existing_stmt = select(InstallmentPlan).where(InstallmentPlan.order_id == order_id)
    if (await db.execute(existing_stmt)).scalar_one_or_none() is not None:
        raise ConflictError(
            detail="این سفارش از قبل دارای طرح اقساطی است",
            error_code="INSTALLMENT_PLAN_EXISTS",
        )

    start = start_date or datetime.now(UTC).date()
    schedule = build_installment_schedule(
        total_rial=order.total,
        num_installments=num_installments,
        first_installment_rial=first_installment_rial,
        start_date=start,
        interval_months=interval_months,
    )

    plan = InstallmentPlan(
        order_id=order_id,
        user_id=user_id,
        provider=provider_name,
        total_rial=order.total,
        num_installments=num_installments,
        first_installment_rial=first_installment_rial,
        schedule=schedule,
        status=InstallmentPlanStatus.PENDING,
        next_due_date=next_unpaid_due_date(schedule),
        paid_count=0,
        created_by_gateway=False,
    )
    db.add(plan)
    await db.flush()
    await logger.ainfo(
        "installment_plan_created",
        plan_id=str(plan.id),
        order_id=str(order_id),
        provider=provider_name,
        num_installments=num_installments,
        total_rial=order.total,
    )
    return to_response(plan)


async def get_plan(
    db: AsyncSession,
    *,
    plan_id: uuid.UUID,
    user_id: uuid.UUID | None = None,
) -> InstallmentPlanResponse:
    """Fetch a plan; when ``user_id`` is given, ownership is part of the query."""
    stmt = select(InstallmentPlan).where(InstallmentPlan.id == plan_id)
    if user_id is not None:
        stmt = stmt.where(InstallmentPlan.user_id == user_id)
    plan = (await db.execute(stmt)).scalar_one_or_none()
    if plan is None:
        raise NotFoundError(resource="InstallmentPlan")
    return to_response(plan)


async def get_plan_for_order(
    db: AsyncSession,
    *,
    order_id: uuid.UUID,
    user_id: uuid.UUID | None = None,
) -> InstallmentPlanResponse | None:
    """The order's plan, or ``None`` when the order is not on installments."""
    stmt = select(InstallmentPlan).where(InstallmentPlan.order_id == order_id)
    if user_id is not None:
        stmt = stmt.where(InstallmentPlan.user_id == user_id)
    plan = (await db.execute(stmt)).scalar_one_or_none()
    return to_response(plan) if plan is not None else None


async def list_plans(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    status: InstallmentPlanStatus | None = None,
) -> list[InstallmentPlanResponse]:
    """List the user's installment plans, newest first."""
    stmt = select(InstallmentPlan).where(InstallmentPlan.user_id == user_id)
    if status is not None:
        stmt = stmt.where(InstallmentPlan.status == status)
    stmt = stmt.order_by(InstallmentPlan.created_at.desc())
    rows = (await db.execute(stmt)).scalars().all()
    return [to_response(row) for row in rows]


async def build_options_for_order(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    order_id: uuid.UUID,
    provider_name: str,
    start_date: date | None = None,
) -> Any:
    """Installment options for an order at one gateway, with full breakdowns.

    The prepayment is a fixed fraction of the total (10%, rounded *down* to a
    whole rial) so the first installment stays a round-ish number and never
    exceeds the total; the remainder is split by
    :func:`build_installment_schedule`, which is where the exactness guarantee
    lives. Every option's schedule therefore sums to ``order.total`` exactly.
    """
    from app.modules.orders.domain.models import Order
    from app.modules.payments.schemas.installment import (
        InstallmentOption,
        InstallmentOptionsResponse,
    )

    order = await db.get(Order, order_id)
    if order is None or order.user_id != user_id:
        raise NotFoundError(resource="Order")

    supported, months = installment_options_for(provider_name)
    if not supported:
        return InstallmentOptionsResponse(
            provider=provider_name,
            supported=False,
            order_total_rial=order.total,
            months=[],
            options=[],
        )

    start = start_date or datetime.now(UTC).date()
    options: list[InstallmentOption] = []
    for count in months:
        first = max(1, (order.total * 10) // 100)
        if first >= order.total:
            # A tiny order cannot carry a prepayment and still have a
            # remainder to split; such an order is simply not offered.
            continue
        schedule = build_installment_schedule(
            total_rial=order.total,
            num_installments=count,
            first_installment_rial=first,
            start_date=start,
        )
        monthly = int(schedule[1]["amount_rial"]) if len(schedule) > 1 else 0
        entries = [
            InstallmentScheduleEntry(
                due_date_jalali=str(entry["due_date_jalali"]),
                due_date=date.fromisoformat(str(entry["due_date"])),
                amount_rial=int(entry["amount_rial"]),
                status=str(entry["status"]),
                paid_at=None,
                is_prepayment=bool(entry["is_prepayment"]),
            )
            for entry in schedule
        ]
        options.append(
            InstallmentOption(
                num_installments=count,
                first_installment_rial=first,
                monthly_installment_rial=monthly,
                remaining_rial=order.total - first,
                schedule=entries,
            )
        )

    return InstallmentOptionsResponse(
        provider=provider_name,
        supported=True,
        order_total_rial=order.total,
        months=list(months),
        options=options,
    )


async def mark_installment_paid(
    db: AsyncSession,
    *,
    plan_id: uuid.UUID,
    installment_index: int,
    paid_at: datetime | None = None,
) -> InstallmentPlanResponse:
    """Mark one scheduled installment paid and recompute the plan status.

    The plan row is locked so two concurrent settlements of the same
    installment cannot both write; the index is bounds-checked and an
    already-paid installment is rejected (idempotency at this level is the
    caller's, but a repeat is a programming error, not a silent no-op).
    """
    stmt = select(InstallmentPlan).where(InstallmentPlan.id == plan_id).with_for_update()
    plan = (await db.execute(stmt)).scalar_one_or_none()
    if plan is None:
        raise NotFoundError(resource="InstallmentPlan")

    schedule = [dict(entry) for entry in (plan.schedule or [])]
    if installment_index < 0 or installment_index >= len(schedule):
        raise ValidationError(
            detail=f"Installment index {installment_index} is out of range",
            error_code="INVALID_INSTALLMENT_INDEX",
        )
    if schedule[installment_index].get("status") == "paid":
        raise ConflictError(
            detail="این قسط قبلاً پرداخت شده است",
            error_code="INSTALLMENT_ALREADY_PAID",
        )

    stamp = (paid_at or datetime.now(UTC)).isoformat()
    schedule[installment_index]["status"] = "paid"
    schedule[installment_index]["paid_at"] = stamp
    plan.schedule = schedule
    plan.paid_count = sum(1 for entry in schedule if entry.get("status") == "paid")
    plan.next_due_date = next_unpaid_due_date(schedule)

    if plan.paid_count >= len(schedule):
        plan.status = InstallmentPlanStatus.COMPLETED
    elif plan.status == InstallmentPlanStatus.PENDING:
        plan.status = InstallmentPlanStatus.ACTIVE

    await db.flush()
    await logger.ainfo(
        "installment_marked_paid",
        plan_id=str(plan.id),
        installment_index=installment_index,
        paid_count=plan.paid_count,
        status=plan.status.value,
    )
    return to_response(plan)


async def cancel_plan(
    db: AsyncSession,
    *,
    plan_id: uuid.UUID,
    reason: str | None = None,
) -> InstallmentPlanResponse:
    """Cancel a plan (order canceled / admin action)."""
    stmt = select(InstallmentPlan).where(InstallmentPlan.id == plan_id).with_for_update()
    plan = (await db.execute(stmt)).scalar_one_or_none()
    if plan is None:
        raise NotFoundError(resource="InstallmentPlan")
    if plan.status == InstallmentPlanStatus.COMPLETED:
        raise ConflictError(
            detail="طرح اقساطی تکمیل‌شده قابل لغو نیست",
            error_code="INSTALLMENT_PLAN_COMPLETED",
        )
    plan.status = InstallmentPlanStatus.CANCELED
    plan.canceled_at = datetime.now(UTC)
    plan.cancel_reason = reason
    await db.flush()
    return to_response(plan)


# ── First-installment payment ─────────────────────────────────────────────
#
# The plan is a promise: the gateway (under a real credit contract) settles
# the remaining installments out of band; this application's payment path
# only ever moves the FIRST installment, which is what the customer
# authorizes at checkout. The first-installment payment is a normal payment
# row (auditable, refundable through the existing flows) with
# ``extra_data.installment_prepayment = <plan_id>``.


async def create_installment_payment(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    plan_id: uuid.UUID,
    idempotency_key: str | None = None,
    description: str = "",
) -> Any:
    """Create the gateway payment for a plan's first installment.

    Returns the ``(payment, gateway_url)`` pair so the client can redirect.
    Rules mirror ``payment_service.create_payment``: one live payment per
    order, amount == first installment exactly, provider resolved through the
    same settings override path.
    """
    from app.modules.payments.application import payment_service
    from app.modules.payments.domain.models import (
        Payment,
        PaymentStatus,
        PaymentTransactionType,
    )

    if idempotency_key:
        existing_stmt = (
            select(Payment)
            .where(Payment.idempotency_key == idempotency_key)
        )
        existing = (await db.execute(existing_stmt)).scalar_one_or_none()
        if existing is not None:
            if str((existing.extra_data or {}).get("installment_prepayment", "")) != str(plan_id):
                raise ConflictError(
                    detail="Idempotency key already used for another payment",
                    error_code="IDEMPOTENCY_KEY_CONFLICT",
                )
            return existing, existing.gateway_url

    # Lock the plan first: two concurrent first-installment creates must not
    # both pass the status guard below.
    plan_stmt = select(InstallmentPlan).where(InstallmentPlan.id == plan_id).with_for_update()
    plan = (await db.execute(plan_stmt)).scalar_one_or_none()
    if plan is None or plan.user_id != user_id:
        raise NotFoundError(resource="InstallmentPlan")
    if plan.status != InstallmentPlanStatus.PENDING:
        raise ConflictError(
            detail=(
                f"طرح اقساطی در وضعیت «{plan.status.value}» است؛ پیش‌پرداخت قبلاً آغاز شده"
            ),
            error_code="INSTALLMENT_NOT_PENDING",
        )

    from app.modules.orders.domain.models import Order, OrderStatus

    order = await db.get(Order, plan.order_id, with_for_update=True)
    if order is None or order.user_id != user_id:
        raise NotFoundError(resource="Order")
    if order.status != OrderStatus.PENDING:
        raise ConflictError(
            detail=f"Order {order.id} is not payable in status '{order.status.value}'",
            error_code="ORDER_NOT_PAYABLE",
        )

    # One live payment per order (same rule as create_payment).
    active_payment_stmt = (
        select(Payment.id)
        .where(
            Payment.order_id == plan.order_id,
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

    from app.modules.payments.domain.models import PaymentProvider as PaymentProviderEnum

    try:
        provider_enum = PaymentProviderEnum(plan.provider)
    except ValueError:
        raise ValidationError(
            detail=f"Unsupported payment provider: {plan.provider}",
            error_code="INVALID_PROVIDER",
        ) from None

    payment = Payment(
        order_id=plan.order_id,
        amount=plan.first_installment_rial,
        provider=provider_enum,
        status=PaymentStatus.PENDING,
        idempotency_key=idempotency_key,
        extra_data={"installment_prepayment": str(plan.id)},
    )
    db.add(payment)
    try:
        await db.flush()
    except IntegrityError:
        if idempotency_key:
            existing = (
                await db.execute(
                    select(Payment).where(Payment.idempotency_key == idempotency_key)
                )
            ).scalar_one_or_none()
            if existing is not None:
                return existing, existing.gateway_url
        raise

    gateway_provider, override_merchant_id = await payment_service._resolve_gateway(
        db, plan.provider
    )
    callback_url = payment_service._build_callback_url(plan.provider, payment.id)
    gateway_result = await gateway_provider.create_payment(
        amount=plan.first_installment_rial,
        order_id=plan.order_id,
        callback_url=callback_url,
        description=description or "پیش‌پرداخت اقساط اول سفارش",
    )

    await payment_service._record_transaction(
        db,
        payment_id=payment.id,
        amount=plan.first_installment_rial,
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
    await db.flush()

    if not gateway_result.success:
        raise PaymentError(
            detail=gateway_result.error_message or "Payment gateway error",
            error_code="GATEWAY_ERROR",
        )

    await logger.ainfo(
        "installment_prepayment_created",
        payment_id=str(payment.id),
        plan_id=str(plan.id),
        amount=plan.first_installment_rial,
    )
    return payment, payment.gateway_url


async def settle_installment_prepayment(
    db: AsyncSession,
    *,
    plan_id: uuid.UUID,
    payment_id: uuid.UUID,
) -> InstallmentPlanResponse:
    """Record that a completed payment settled the plan's prepayment.

    Called from ``payment_service.verify_payment`` after the payment row is
    completed (and thus locked by the caller). The plan row is locked here,
    so two concurrent verifies of the same prepayment serialise; the
    PENDING→ACTIVE transition happens exactly once because the second caller
    re-reads an ACTIVE plan and returns without touching it.
    """
    plan_stmt = select(InstallmentPlan).where(InstallmentPlan.id == plan_id).with_for_update()
    plan = (await db.execute(plan_stmt)).scalar_one_or_none()
    if plan is None:
        raise NotFoundError(resource="InstallmentPlan")

    if plan.status in (InstallmentPlanStatus.ACTIVE, InstallmentPlanStatus.COMPLETED):
        await logger.ainfo(
            "installment_prepayment_already_settled",
            plan_id=str(plan.id),
            payment_id=str(payment_id),
        )
        return to_response(plan)

    schedule = [dict(entry) for entry in (plan.schedule or [])]
    if not schedule or schedule[0].get("status") == "paid":
        raise ConflictError(
            detail="این قسط قبلاً پرداخت شده است",
            error_code="INSTALLMENT_ALREADY_PAID",
        )

    schedule[0]["status"] = "paid"
    schedule[0]["paid_at"] = datetime.now(UTC).isoformat()
    plan.schedule = schedule
    plan.paid_count = 1
    plan.first_payment_id = payment_id
    plan.next_due_date = next_unpaid_due_date(schedule)
    plan.status = (
        InstallmentPlanStatus.COMPLETED
        if plan.paid_count >= len(schedule)
        else InstallmentPlanStatus.ACTIVE
    )
    await db.flush()

    await logger.ainfo(
        "installment_prepayment_settled",
        plan_id=str(plan.id),
        payment_id=str(payment_id),
        status=plan.status.value,
    )
    return to_response(plan)
