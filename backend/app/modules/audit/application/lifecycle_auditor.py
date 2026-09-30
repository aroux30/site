"""Read-only cross-axis lifecycle auditor for physical orders.

Contract: ``docs/architecture/quality-gates.md``.

The order table intentionally carries one customer-facing lifecycle status.
That keeps the checkout API simple, but the underlying truth has independent
axes:

* payment rows say whether money was captured or returned;
* shipment rows say where physical items are; and
* refund rows say whether money was actually returned.

This auditor derives those axes from authoritative rows and records only
**provable contradictions** as durable reconciliation findings. It never
changes an order, payment, refund, shipment, inventory row, provider state, or
wallet balance. The only writes are to ``reconciliation_findings`` and the
caller-owned audit trail.

Conservative rules
------------------
A finding is emitted only when the current platform semantics make it
unambiguous:

``ORDER_CANCELED_WITH_SHIPMENT``
    A terminally cancelled order still has a physical shipment that is pending,
    processing, shipped, in transit, or delivered. The shipping service refuses
    to create a shipment for cancelled/refunded orders and the order state
    machine never transitions from a shipped state to cancelled, so this is
    corruption or a bypassed write path.

``ORDER_DELIVERED_SHIPMENT_OPEN``
    An order reports delivered while it has at least one physical shipment that
    is still pending, processing, shipped, or in transit. No-shipment orders
    are deliberately skipped: digital goods can legitimately be delivered
    without a physical shipment.

``ORDER_REFUNDED_UNDERREFUND``
    An order reports fully refunded but its processed order-backed refund rows
    total less than its nonzero order total. Pending or approved refunds do not
    count because they have not moved money yet.

The rules are intentionally narrower than a travel-style multi-axis state
machine: a false financial alert consumes an operator's time, so this auditor
reports only what the local records can prove.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import func, select

from app.modules.audit.application.reconciliation_service import upsert_finding
from app.modules.audit.domain.reconciliation import (
    FindingSeverity,
    FindingType,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

DEFAULT_LIFECYCLE_AUDIT_LIMIT = 500

#: Order statuses any detector can act on. Every detector below fires only on a
#: terminally-resolved order (cancelled, delivered, refunded), so the audit
#: query is filtered to these. Without the filter the bounded slice spent its
#: whole budget on brand-new ``pending`` orders — on a real database 494 of the
#: newest 500 — and almost none of the orders that could contradict were ever
#: looked at. ``truncated`` then means "more auditable orders than the cap",
#: which is the only reading an operator can act on.
_AUDITED_ORDER_STATUSES = ("canceled", "delivered", "refunded")

#: Shipment states that represent a physical package that has not completed a
#: normal return-to-sender flow. Stored as strings so pure detectors can run on
#: ORM enum values or test doubles alike.
_ACTIVE_SHIPMENT_STATUSES = frozenset(
    {"pending", "processing", "shipped", "in_transit", "delivered"}
)
_OPEN_SHIPMENT_STATUSES = frozenset({"pending", "processing", "shipped", "in_transit"})


@dataclass(frozen=True, slots=True)
class LifecycleFindingCandidate:
    """A detected lifecycle contradiction before persistence."""

    dedupe_key: str
    finding_type: FindingType
    severity: FindingSeverity
    entity_type: str
    entity_id: str
    expected_amount: int | None
    actual_amount: int | None
    details: dict[str, Any]


@dataclass(frozen=True, slots=True)
class LifecycleAuditResult:
    """Outcome of one bounded, idempotent lifecycle audit pass."""

    detected: int
    created: int
    updated: int
    truncated: bool
    findings: tuple[LifecycleFindingCandidate, ...]


def _value(value: Any) -> str:
    """Return an Enum value or normalise a string-like status."""
    return str(getattr(value, "value", value)).lower()


def canceled_with_shipment_key(order_id: uuid.UUID) -> str:
    return f"order_canceled_with_shipment:{order_id}"


def delivered_open_shipment_key(order_id: uuid.UUID) -> str:
    return f"order_delivered_shipment_open:{order_id}"


def refunded_underrefund_key(order_id: uuid.UUID) -> str:
    return f"order_refunded_underrefund:{order_id}"


def detect_canceled_orders_with_shipments(
    orders: Iterable[Any],
    shipment_statuses: dict[uuid.UUID, list[str]],
) -> list[LifecycleFindingCandidate]:
    """Find terminally cancelled orders with outgoing physical shipments."""
    results: list[LifecycleFindingCandidate] = []
    for order in orders:
        if _value(getattr(order, "status", "")) != "canceled":
            continue
        statuses = shipment_statuses.get(order.id, [])
        active = sorted(status for status in statuses if status in _ACTIVE_SHIPMENT_STATUSES)
        if not active:
            continue
        results.append(
            LifecycleFindingCandidate(
                dedupe_key=canceled_with_shipment_key(order.id),
                finding_type=FindingType.ORDER_CANCELED_WITH_SHIPMENT,
                severity=FindingSeverity.HIGH,
                entity_type="order",
                entity_id=str(order.id),
                expected_amount=None,
                actual_amount=None,
                details={
                    "order_status": "canceled",
                    "shipment_statuses": active,
                    "shipment_count": len(statuses),
                    "reason_code": "canceled_order_has_active_physical_shipment",
                },
            )
        )
    return results


def detect_delivered_orders_with_open_shipments(
    orders: Iterable[Any],
    shipment_statuses: dict[uuid.UUID, list[str]],
) -> list[LifecycleFindingCandidate]:
    """Find delivered orders whose physical shipments remain in progress.

    Orders with no physical shipment are skipped: a digital delivery is not a
    contradiction. Partial shipments are intentionally audited here because an
    order-level ``delivered`` status promises the customer the whole order is
    delivered, not merely one package.
    """
    results: list[LifecycleFindingCandidate] = []
    for order in orders:
        if _value(getattr(order, "status", "")) != "delivered":
            continue
        statuses = shipment_statuses.get(order.id, [])
        open_shipments = sorted(status for status in statuses if status in _OPEN_SHIPMENT_STATUSES)
        if not statuses or not open_shipments:
            continue
        results.append(
            LifecycleFindingCandidate(
                dedupe_key=delivered_open_shipment_key(order.id),
                finding_type=FindingType.ORDER_DELIVERED_SHIPMENT_OPEN,
                severity=FindingSeverity.HIGH,
                entity_type="order",
                entity_id=str(order.id),
                expected_amount=None,
                actual_amount=None,
                details={
                    "order_status": "delivered",
                    "shipment_statuses": sorted(statuses),
                    "open_shipment_statuses": open_shipments,
                    "reason_code": "delivered_order_has_nonterminal_physical_shipment",
                },
            )
        )
    return results


def detect_refunded_orders_with_underrefund(
    orders: Iterable[Any],
    processed_refunds_by_order: dict[uuid.UUID, int],
) -> list[LifecycleFindingCandidate]:
    """Find fully refunded orders whose processed refund total is insufficient."""
    results: list[LifecycleFindingCandidate] = []
    for order in orders:
        if _value(getattr(order, "status", "")) != "refunded":
            continue
        total = int(getattr(order, "total", 0) or 0)
        # Zero-total orders require no payment refund and are not contradictory.
        if total <= 0:
            continue
        refunded = int(processed_refunds_by_order.get(order.id, 0))
        if refunded >= total:
            continue
        results.append(
            LifecycleFindingCandidate(
                dedupe_key=refunded_underrefund_key(order.id),
                finding_type=FindingType.ORDER_REFUNDED_UNDERREFUND,
                severity=FindingSeverity.CRITICAL,
                entity_type="order",
                entity_id=str(order.id),
                expected_amount=total,
                actual_amount=refunded,
                details={
                    "order_status": "refunded",
                    "order_total": total,
                    "processed_refund_total": refunded,
                    "shortfall": total - refunded,
                    "reason_code": "refunded_order_processed_refunds_below_order_total",
                },
            )
        )
    return results


async def audit_order_lifecycle(
    db: AsyncSession,
    *,
    now: datetime | None = None,
    limit: int = DEFAULT_LIFECYCLE_AUDIT_LIMIT,
) -> LifecycleAuditResult:
    """Audit a bounded order slice and idempotently persist lifecycle findings.

    All business rows are read through ``SELECT``. The only mutation is the
    finding upsert, which is safe under at-least-once Celery execution because
    its stable key is unique.
    """
    from app.modules.orders.domain.models import Order
    from app.modules.payments.domain.models import Refund, RefundStatus
    from app.modules.shipping.domain.models import Shipment

    moment = now or datetime.now(UTC)
    orders = (
        await db.execute(
            select(Order)
            .where(func.lower(Order.status).in_(_AUDITED_ORDER_STATUSES))
            .order_by(Order.created_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    order_ids = [order.id for order in orders]

    shipment_statuses: dict[uuid.UUID, list[str]] = {}
    processed_refunds_by_order: dict[uuid.UUID, int] = {}
    if order_ids:
        shipment_rows = (
            await db.execute(
                select(Shipment.order_id, Shipment.status).where(Shipment.order_id.in_(order_ids))
            )
        ).all()
        for order_id, status in shipment_rows:
            shipment_statuses.setdefault(order_id, []).append(_value(status))

        refund_rows = (
            await db.execute(
                select(Refund.order_id, Refund.amount)
                .where(Refund.order_id.in_(order_ids))
                .where(Refund.status == RefundStatus.PROCESSED)
            )
        ).all()
        for order_id, amount in refund_rows:
            if order_id is not None:
                processed_refunds_by_order[order_id] = (
                    processed_refunds_by_order.get(order_id, 0) + int(amount)
                )

    candidates: list[LifecycleFindingCandidate] = []
    candidates += detect_canceled_orders_with_shipments(orders, shipment_statuses)
    candidates += detect_delivered_orders_with_open_shipments(orders, shipment_statuses)
    candidates += detect_refunded_orders_with_underrefund(orders, processed_refunds_by_order)
    candidates.sort(key=lambda item: (item.finding_type.value, item.dedupe_key))

    created = 0
    updated = 0
    for candidate in candidates:
        was_created = await upsert_finding(db, candidate, now=moment)
        if was_created:
            created += 1
        else:
            updated += 1

    truncated = len(orders) >= limit
    await logger.ainfo(
        "order_lifecycle_audit_completed",
        detected=len(candidates),
        created=created,
        updated=updated,
        truncated=truncated,
    )
    return LifecycleAuditResult(
        detected=len(candidates),
        created=created,
        updated=updated,
        truncated=truncated,
        findings=tuple(candidates),
    )
