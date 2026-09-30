"""Read-only payment reconciliation scanner for the audit bounded context.

Scope (see ``docs/architecture/clean-room-operational-capability-and-reconciliation.md``)
----------------------------------------------------------------------------------------
The scanner *reads* business records from the payments, orders and wallet
bounded contexts and writes **only**:

* rows in ``reconciliation_findings`` (its own table), and
* audit-trail entries in ``audit_logs``.

It never calls a gateway, never retries a callback, never captures or refunds
money, never creates a wallet transaction, never mutates a payment / order /
refund / webhook / inventory row, and never invokes an external provider. The
read-only property is structural: every statement in this module is a
``SELECT``, plus the deduplicated finding upsert and the audit-log insert.

Detectors are deliberately restricted to conditions **provable** from local
columns, so a finding never depends on an external provider being reachable:

1. ``PAYMENT_AMOUNT_MISMATCH`` — ``payments.amount`` disagrees with the order
   total it was created against.
2. ``PAYMENT_ORDER_STATUS_MISMATCH`` — a COMPLETED payment whose order never
   left PENDING (the transition in ``verify_payment`` did not land).
3. ``REFUND_TOTAL_EXCEEDS_PAYMENT`` — non-rejected refunds for one payment sum
   to more than the payment itself.
4. ``WEBHOOK_UNPROCESSED`` — a webhook event stayed unprocessed past the
   documented grace period.

Detectors are split from persistence on purpose: :func:`detect_*` are pure
functions over already-loaded rows and are unit-testable without a database,
while :func:`scan` owns the (idempotent) persistence.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.config.settings import get_settings
from app.modules.audit.application import audit_service
from app.modules.audit.domain.reconciliation import (
    FindingSeverity,
    FindingStatus,
    FindingType,
    ReconciliationFinding,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

#: Default grace period before an unprocessed webhook event is reported. Long
#: enough that normal processing (inline on the callback request) and provider
#: retries have settled; short enough to surface a genuinely stuck callback.
DEFAULT_WEBHOOK_GRACE_MINUTES = 60

#: Upper bound on rows examined per detector in one pass. The scanner is a
#: periodic background sweep, not a bulk migration; each pass advances the
#: backlog and reports truncation instead of scanning unbounded tables.
DEFAULT_SCAN_LIMIT = 500

#: Payment ``extra_data.purpose`` marker for wallet top-ups. These legitimately
#: carry ``order_id = NULL`` and have no order total to agree with.
_WALLET_TOPUP_PURPOSE = "wallet_topup"

#: Refund statuses that represent money the platform has committed to return.
#: A REJECTED refund moved nothing and must not count toward the total.
_COMMITTED_REFUND_STATUSES = ("PENDING", "APPROVED", "PROCESSED")


@dataclass(frozen=True, slots=True)
class FindingCandidate:
    """A detected mismatch, before it is persisted or deduplicated."""

    dedupe_key: str
    finding_type: FindingType
    severity: FindingSeverity
    entity_type: str
    entity_id: str
    expected_amount: int | None
    actual_amount: int | None
    details: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ScanResult:
    """Outcome of one scanner pass."""

    detected: int
    created: int
    updated: int
    truncated: bool
    findings: tuple[FindingCandidate, ...]


# ── Dedupe keys ───────────────────────────────────────────────────────────


def payment_amount_dedupe_key(payment_id: uuid.UUID) -> str:
    return f"payment_amount_mismatch:{payment_id}"


def payment_order_status_dedupe_key(payment_id: uuid.UUID) -> str:
    return f"payment_order_status_mismatch:{payment_id}"


def refund_total_dedupe_key(payment_id: uuid.UUID) -> str:
    return f"refund_total_exceeds_payment:{payment_id}"


def webhook_unprocessed_dedupe_key(provider: str, event_id: str) -> str:
    return f"webhook_unprocessed:{provider}:{event_id}"


# ── Pure detectors ────────────────────────────────────────────────────────


def _is_order_backed_payment(payment: Any) -> bool:
    """True when the payment is bound to an order and is not a wallet top-up.

    Wallet top-ups carry ``order_id = NULL``; some legacy rows keep an order id
    AND the top-up marker, and those have no order total to compare against.
    """
    if getattr(payment, "order_id", None) is None:
        return False
    extra = getattr(payment, "extra_data", None) or {}
    return extra.get("purpose") != _WALLET_TOPUP_PURPOSE


def detect_payment_amount_mismatch(
    payments: Iterable[Any],
    order_totals: dict[uuid.UUID, int],
) -> list[FindingCandidate]:
    """Payment amount must equal the order total it was created against.

    ``create_payment`` refuses a mismatch, so a difference here means the
    payment row or the order row was changed after creation — either way the
    two authoritative money columns disagree and an operator must look.
    """
    results: list[FindingCandidate] = []
    for payment in payments:
        if not _is_order_backed_payment(payment):
            continue
        order_total = order_totals.get(payment.order_id)
        if order_total is None or order_total == payment.amount:
            continue
        results.append(
            FindingCandidate(
                dedupe_key=payment_amount_dedupe_key(payment.id),
                finding_type=FindingType.PAYMENT_AMOUNT_MISMATCH,
                severity=FindingSeverity.CRITICAL,
                entity_type="payment",
                entity_id=str(payment.id),
                expected_amount=int(order_total),
                actual_amount=int(payment.amount),
                details={
                    "order_id": str(payment.order_id),
                    "provider": _enum_value(payment.provider),
                    "payment_status": _enum_value(payment.status),
                    "reason_code": "payment_amount_differs_from_order_total",
                },
            )
        )
    return results


def detect_payment_order_status_mismatch(
    payments: Iterable[Any],
    order_statuses: dict[uuid.UUID, str],
) -> list[FindingCandidate]:
    """A COMPLETED payment must not sit on an order that is still PENDING.

    ``verify_payment`` sets the payment COMPLETED and moves the order out of
    PENDING in the *same* transaction, and explicitly refuses when the order is
    in any other state. A COMPLETED payment on a still-PENDING order therefore
    means the transition did not land — money is captured but the order never
    advanced. Only PENDING is reported: every other status is reachable either
    by the normal confirmation or by a legitimate later transition.

    The COMPLETED precondition is checked here rather than left to the caller,
    so the detector is correct for any input slice.
    """
    results: list[FindingCandidate] = []
    for payment in payments:
        if not _is_order_backed_payment(payment):
            continue
        if _enum_value(payment.status) != "COMPLETED":
            continue
        order_status = order_statuses.get(payment.order_id)
        if order_status != "PENDING":
            continue
        results.append(
            FindingCandidate(
                dedupe_key=payment_order_status_dedupe_key(payment.id),
                finding_type=FindingType.PAYMENT_ORDER_STATUS_MISMATCH,
                severity=FindingSeverity.HIGH,
                entity_type="payment",
                entity_id=str(payment.id),
                expected_amount=None,
                actual_amount=int(payment.amount),
                details={
                    "order_id": str(payment.order_id),
                    "order_status": order_status,
                    "payment_status": _enum_value(payment.status),
                    "provider": _enum_value(payment.provider),
                    "reason_code": "completed_payment_on_pending_order",
                },
            )
        )
    return results


def detect_refund_total_exceeds_payment(
    refunds: Iterable[Any],
    payments: dict[uuid.UUID, Any],
) -> list[FindingCandidate]:
    """Committed refunds for one payment must not exceed that payment.

    ``refund_payment`` enforces this under a row lock, so an excess is a real
    over-return (double refund, a manual row, or a concurrent path that
    bypassed the lock) and never a normal partial-refund sequence.
    """
    totals: dict[uuid.UUID, int] = {}
    for refund in refunds:
        if _enum_value(refund.status) not in _COMMITTED_REFUND_STATUSES:
            continue
        totals[refund.payment_id] = totals.get(refund.payment_id, 0) + int(refund.amount)

    results: list[FindingCandidate] = []
    for payment_id, refunded_total in totals.items():
        payment = payments.get(payment_id)
        if payment is None:
            continue
        if refunded_total <= int(payment.amount):
            continue
        results.append(
            FindingCandidate(
                dedupe_key=refund_total_dedupe_key(payment_id),
                finding_type=FindingType.REFUND_TOTAL_EXCEEDS_PAYMENT,
                severity=FindingSeverity.CRITICAL,
                entity_type="payment",
                entity_id=str(payment_id),
                expected_amount=int(payment.amount),
                actual_amount=int(refunded_total),
                details={
                    "order_id": str(payment.order_id) if payment.order_id else None,
                    "payment_amount": int(payment.amount),
                    "refunded_total": int(refunded_total),
                    "refund_count": sum(
                        1
                        for r in refunds
                        if r.payment_id == payment_id
                        and _enum_value(r.status) in _COMMITTED_REFUND_STATUSES
                    ),
                    "reason_code": "committed_refunds_exceed_payment_amount",
                },
            )
        )
    return results


def detect_webhook_unprocessed(
    webhooks: Iterable[Any],
    *,
    cutoff: datetime,
    now: datetime,
) -> list[FindingCandidate]:
    """Report webhook events still unprocessed after the grace period.

    ``processed`` is set by the callback handler whether verification succeeded
    or the payment was already completed; a failed verify records ``error`` and
    leaves ``processed = False``. Anything older than the grace period is stuck
    and needs an operator, which is exactly the case the reconciliation runbook
    describes.
    """
    results: list[FindingCandidate] = []
    for event in webhooks:
        if getattr(event, "processed", False):
            continue
        created_at = _as_aware(getattr(event, "created_at", None))
        if created_at is None or created_at >= cutoff:
            continue
        results.append(
            FindingCandidate(
                dedupe_key=webhook_unprocessed_dedupe_key(event.provider, event.event_id),
                finding_type=FindingType.WEBHOOK_UNPROCESSED,
                severity=FindingSeverity.MEDIUM,
                entity_type="webhook_event",
                entity_id=f"{event.provider}:{event.event_id}",
                expected_amount=None,
                actual_amount=None,
                details={
                    "provider": event.provider,
                    "event_id": event.event_id,
                    "payment_id": str(event.payment_id) if event.payment_id else None,
                    "age_minutes": int((now - created_at).total_seconds() // 60),
                    "has_error": bool(getattr(event, "error", None)),
                    "reason_code": "webhook_unprocessed_beyond_grace_period",
                },
            )
        )
    return results


def _enum_value(value: Any) -> Any:
    """Return ``value.value`` for enums, else the value itself."""
    return getattr(value, "value", value)


def _as_aware(value: datetime | None) -> datetime | None:
    """Normalize a possibly-naive datetime to UTC-aware for comparisons."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


# ── Persistence ───────────────────────────────────────────────────────────


async def scan(
    db: AsyncSession,
    *,
    now: datetime | None = None,
    limit: int = DEFAULT_SCAN_LIMIT,
) -> ScanResult:
    """Run every detector once and persist the findings, deduplicated.

    Safe under at-least-once execution: the dedupe key is unique, so a second
    pass over an unchanged condition bumps ``occurrence_count`` and
    ``last_detected_at`` on the same row instead of creating a duplicate.

    A finding an operator already RESOLVED or DISMISSED keeps that status and
    keeps accumulating occurrences. Re-opening a finding automatically would
    silently overturn an explicit operator decision; the occurrence counter
    and ``last_detected_at`` are what surface "this is still happening".
    """
    moment = now or datetime.now(UTC)
    candidates, truncated = await _collect_candidates(db, now=moment, limit=limit)

    created = 0
    updated = 0
    for candidate in candidates:
        was_created = await upsert_finding(db, candidate, now=moment)
        if was_created:
            created += 1
        else:
            updated += 1

    await logger.ainfo(
        "reconciliation_scan_completed",
        detected=len(candidates),
        created=created,
        updated=updated,
        truncated=truncated,
    )

    return ScanResult(
        detected=len(candidates),
        created=created,
        updated=updated,
        truncated=truncated,
        findings=tuple(candidates),
    )


async def _collect_candidates(
    db: AsyncSession,
    *,
    now: datetime,
    limit: int,
) -> tuple[list[FindingCandidate], bool]:
    """Load the bounded working set and run every pure detector over it."""
    from app.modules.orders.domain.models import Order
    from app.modules.payments.domain.models import (
        Payment,
        PaymentWebhookEvent,
        Refund,
    )

    settings = get_settings()
    grace_minutes = int(
        getattr(settings, "RECONCILIATION_WEBHOOK_GRACE_MINUTES", DEFAULT_WEBHOOK_GRACE_MINUTES)
    )
    cutoff = now - timedelta(minutes=grace_minutes)

    # ── Order-backed payments and their order totals ──────────────────
    payment_rows = (
        await db.execute(
            select(Payment)
            .where(Payment.order_id.is_not(None))
            .order_by(Payment.created_at.desc())
            .limit(limit)
        )
    ).scalars().all()

    order_ids = [p.order_id for p in payment_rows if p.order_id is not None]
    order_totals: dict[uuid.UUID, int] = {}
    order_statuses: dict[uuid.UUID, str] = {}
    if order_ids:
        for order_id, total, status in (
            await db.execute(
                select(Order.id, Order.total, Order.status).where(Order.id.in_(order_ids))
            )
        ).all():
            order_totals[order_id] = int(total)
            order_statuses[order_id] = _enum_value(status)

    # ── Refunds for the payments in the working set ────────────────────
    payment_ids = [p.id for p in payment_rows]
    refund_rows: Sequence[Any] = []
    if payment_ids:
        refund_rows = (
            await db.execute(
                select(Refund)
                .where(Refund.payment_id.in_(payment_ids))
                .order_by(Refund.created_at.desc())
                .limit(limit)
            )
        ).scalars().all()

    # ── Unprocessed webhooks past the grace period ────────────────────
    webhook_rows = (
        await db.execute(
            select(PaymentWebhookEvent)
            .where(PaymentWebhookEvent.processed.is_(False))
            .where(PaymentWebhookEvent.created_at < cutoff)
            .order_by(PaymentWebhookEvent.created_at.asc())
            .limit(limit)
        )
    ).scalars().all()

    payments_by_id = {p.id: p for p in payment_rows}
    candidates: list[FindingCandidate] = []
    candidates += detect_payment_amount_mismatch(payment_rows, order_totals)
    candidates += detect_payment_order_status_mismatch(payment_rows, order_statuses)
    candidates += detect_refund_total_exceeds_payment(refund_rows, payments_by_id)
    candidates += detect_webhook_unprocessed(webhook_rows, cutoff=cutoff, now=now)

    truncated = (
        len(payment_rows) >= limit or len(refund_rows) >= limit or len(webhook_rows) >= limit
    )

    # Stable order so a scan's output (and its logs) are reproducible.
    candidates.sort(key=lambda c: (c.finding_type.value, c.dedupe_key))
    return candidates, truncated


async def upsert_finding(
    db: AsyncSession,
    candidate: FindingCandidate | Any,
    *,
    now: datetime,
) -> bool:
    """Insert a reconciliation-like finding, or bump the existing row.

    The candidate is duck-typed deliberately: the lifecycle auditor writes to
    the same durable finding table and needs the same unique-key and
    occurrence-count behaviour, without a second persistence implementation.
    Both candidate dataclasses expose the same seven fields.

    Returns ``True`` when a new row was created. The insert is a single
    ``INSERT … ON CONFLICT DO UPDATE`` so two overlapping runs cannot both
    create the row, and no read-then-write race exists.
    """
    statement = (
        pg_insert(ReconciliationFinding)
        .values(
            id=uuid.uuid4(),
            dedupe_key=candidate.dedupe_key,
            finding_type=candidate.finding_type,
            severity=candidate.severity,
            status=FindingStatus.OPEN,
            entity_type=candidate.entity_type,
            entity_id=candidate.entity_id,
            expected_amount=candidate.expected_amount,
            actual_amount=candidate.actual_amount,
            details=candidate.details,
            first_detected_at=now,
            last_detected_at=now,
            occurrence_count=1,
            created_at=now,
            updated_at=now,
        )
        .on_conflict_do_update(
            index_elements=["dedupe_key"],
            set_={
                "severity": candidate.severity,
                "expected_amount": candidate.expected_amount,
                "actual_amount": candidate.actual_amount,
                "details": candidate.details,
                "last_detected_at": now,
                "updated_at": now,
                "occurrence_count": ReconciliationFinding.occurrence_count + 1,
            },
        )
        .returning(ReconciliationFinding.id, ReconciliationFinding.occurrence_count)
    )
    row = (await db.execute(statement)).one()
    await db.flush()
    # occurrence_count == 1 only on a fresh insert: the UPDATE branch always
    # adds to an existing count of at least 1.
    return int(row.occurrence_count) == 1


# ── Queries and lifecycle ─────────────────────────────────────────────────


async def list_findings(
    db: AsyncSession,
    *,
    status: FindingStatus | None = None,
    finding_type: FindingType | None = None,
    severity: FindingSeverity | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[ReconciliationFinding], int]:
    """Return ``(items, total)`` for the filtered, paginated finding list."""
    stmt = select(ReconciliationFinding)
    count_stmt = select(func.count(ReconciliationFinding.id))

    if status is not None:
        stmt = stmt.where(ReconciliationFinding.status == status)
        count_stmt = count_stmt.where(ReconciliationFinding.status == status)
    if finding_type is not None:
        stmt = stmt.where(ReconciliationFinding.finding_type == finding_type)
        count_stmt = count_stmt.where(ReconciliationFinding.finding_type == finding_type)
    if severity is not None:
        stmt = stmt.where(ReconciliationFinding.severity == severity)
        count_stmt = count_stmt.where(ReconciliationFinding.severity == severity)

    total = int((await db.execute(count_stmt)).scalar() or 0)
    offset = (page - 1) * page_size
    stmt = (
        stmt.order_by(
            ReconciliationFinding.last_detected_at.desc(),
            ReconciliationFinding.id.desc(),
        )
        .offset(offset)
        .limit(page_size)
    )
    items = list((await db.execute(stmt)).scalars().all())
    return items, total


async def summarize_findings(db: AsyncSession) -> dict[str, Any]:
    """Aggregate counts by status, severity and type, plus the latest detection."""
    by_status = {s.value: 0 for s in FindingStatus}
    for value, count in (
        await db.execute(
            select(ReconciliationFinding.status, func.count(ReconciliationFinding.id)).group_by(
                ReconciliationFinding.status
            )
        )
    ).all():
        by_status[_enum_value(value)] = int(count)

    by_severity = {s.value: 0 for s in FindingSeverity}
    for value, count in (
        await db.execute(
            select(
                ReconciliationFinding.severity, func.count(ReconciliationFinding.id)
            ).group_by(ReconciliationFinding.severity)
        )
    ).all():
        by_severity[_enum_value(value)] = int(count)

    by_type = {t.value: 0 for t in FindingType}
    for value, count in (
        await db.execute(
            select(
                ReconciliationFinding.finding_type, func.count(ReconciliationFinding.id)
            ).group_by(ReconciliationFinding.finding_type)
        )
    ).all():
        by_type[_enum_value(value)] = int(count)

    return {
        "total": sum(by_status.values()),
        "open": by_status[FindingStatus.OPEN.value],
        "by_status": by_status,
        "by_severity": by_severity,
        "by_type": by_type,
        "last_detected_at": (
            await db.execute(select(func.max(ReconciliationFinding.last_detected_at)))
        ).scalar(),
    }


async def get_finding(db: AsyncSession, finding_id: uuid.UUID) -> ReconciliationFinding | None:
    return await db.get(ReconciliationFinding, finding_id)


async def _apply_lifecycle(
    db: AsyncSession,
    *,
    finding_id: uuid.UUID,
    status: FindingStatus,
    notes: str,
    actor_id: uuid.UUID | None,
) -> ReconciliationFinding | None:
    """Set a finding's lifecycle status, with an audit-trail entry.

    Only the finding row changes. The underlying payment / order / refund /
    webhook record is never touched: resolving a finding records an operator
    decision, it does not repair the data (that stays a separate, audited,
    financially consequential action).
    """
    finding = await db.get(ReconciliationFinding, finding_id, with_for_update=True)
    if finding is None:
        return None

    finding.status = status
    finding.resolution_notes = notes
    finding.resolved_at = datetime.now(UTC)
    finding.resolved_by = actor_id
    await db.flush()

    await audit_service.log_action(
        db,
        actor_id=actor_id,
        action=f"RECONCILIATION_FINDING_{status.value}",
        resource="reconciliation_finding",
        resource_id=finding.id,
        after={
            "status": status.value,
            "finding_type": _enum_value(finding.finding_type),
            "dedupe_key": finding.dedupe_key,
            "entity_type": finding.entity_type,
            "entity_id": finding.entity_id,
        },
        extra_data={"resolution_notes": notes},
    )
    return finding


async def resolve_finding(
    db: AsyncSession,
    *,
    finding_id: uuid.UUID,
    notes: str,
    actor_id: uuid.UUID | None = None,
) -> ReconciliationFinding | None:
    """Mark a finding RESOLVED with the operator's note."""
    return await _apply_lifecycle(
        db,
        finding_id=finding_id,
        status=FindingStatus.RESOLVED,
        notes=notes,
        actor_id=actor_id,
    )


async def dismiss_finding(
    db: AsyncSession,
    *,
    finding_id: uuid.UUID,
    notes: str,
    actor_id: uuid.UUID | None = None,
) -> ReconciliationFinding | None:
    """Mark a finding DISMISSED with the operator's reason."""
    return await _apply_lifecycle(
        db,
        finding_id=finding_id,
        status=FindingStatus.DISMISSED,
        notes=notes,
        actor_id=actor_id,
    )
