"""Fiscal invoice application service.

Owns the lifecycle of :class:`Invoice` documents:

- ``create_draft_for_order`` — snapshot an order's totals/customer/lines into
  a draft document. Idempotent per order via ``invoice:{order_id}:invoice``
  and ``invoice:{order_id}:credit:{event_key}`` idempotency keys.
- ``post`` — allocate the gapless fiscal number, set the period, chain the
  hash to the previous posted document, archive the rendered HTML snapshot.
- ``cancel`` — void a draft or posted-before-payment document with a reason.
- ``issue_credit_note_for_refund`` — additive outbox listener target: build
  a credit note against the order's posted invoice when a refund event
  arrives. Never touches the refund path's own transaction.

Immutability: any mutation helper raises :class:`ConflictError` once the
document has left ``draft``.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.core.exceptions.handlers import ConflictError, NotFoundError, ValidationError
from app.modules.invoicing.application.hashing import (
    GENESIS_HASH,
    compute_document_hash,
    verify_document,
)
from app.modules.invoicing.application.numbering import allocate_next_number
from app.modules.invoicing.domain.models import (
    INVOICE_TRANSITIONS,
    Invoice,
    InvoiceLine,
    InvoiceStatus,
    InvoiceType,
)
from app.modules.orders.domain.models import Order
from app.modules.users.domain.models import User

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Snapshot builders
# ---------------------------------------------------------------------------


def _totals_snapshot(order: Order) -> dict[str, int]:
    """Integer-Rial totals snapshot, following the order's stored columns."""
    return {
        "currency": "IRR",
        "subtotal": int(order.subtotal or 0),
        "discount": int(order.discount_amount or 0),
        "tax": int(order.tax or 0),
        "shipping": int(order.shipping_cost or 0),
        "total": int(order.total or 0),
    }


def _customer_snapshot(order: Order, user: User | None) -> dict[str, Any]:
    snap = order.shipping_address_snapshot or {}
    profile = getattr(user, "profile", None) if user else None

    name = ""
    if profile and (getattr(profile, "first_name", None) or getattr(profile, "last_name", None)):
        name = f"{getattr(profile, 'first_name', '') or ''} {getattr(profile, 'last_name', '') or ''}".strip()
    if not name:
        name = snap.get("recipient_name") or snap.get("receiver_name") or snap.get("name") or ""

    return {
        "user_id": str(order.user_id),
        "name": name or None,
        "phone": (getattr(user, "phone", None) if user else None) or snap.get("phone"),
        "national_code": (getattr(profile, "national_code", None) if profile else None)
        or snap.get("national_code"),
        "province": snap.get("province"),
        "city": snap.get("city"),
        "address": snap.get("full_address") or snap.get("address"),
        "postal_code": snap.get("postal_code"),
    }


def _line_snapshots(order: Order) -> list[dict[str, Any]]:
    lines: list[dict[str, Any]] = []
    for idx, item in enumerate(order.items or [], start=1):
        name = item.product_name
        if item.variant_info:
            name = f"{name} ({item.variant_info})"
        lines.append(
            {
                "position": idx,
                "product_name": name,
                "sku": item.sku or None,
                "quantity": int(item.quantity),
                "unit_price": int(item.unit_price),
                "total_price": int(item.total_price),
            }
        )
    return lines


# ---------------------------------------------------------------------------
# Draft creation
# ---------------------------------------------------------------------------


async def _get_order_with_lines(db: AsyncSession, order_id: uuid.UUID) -> Order:
    stmt = (
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.id == order_id)
    )
    order = (await db.execute(stmt)).scalar_one_or_none()
    if order is None:
        raise NotFoundError("Order")
    return order


async def _find_by_idempotency_key(db: AsyncSession, key: str) -> Invoice | None:
    stmt = select(Invoice).where(Invoice.idempotency_key == key)
    return (await db.execute(stmt)).scalar_one_or_none()


async def get_invoice_for_order(
    db: AsyncSession, order_id: uuid.UUID, doc_type: InvoiceType = InvoiceType.INVOICE
) -> Invoice | None:
    stmt = (
        select(Invoice)
        .options(selectinload(Invoice.lines))
        .where(Invoice.order_id == order_id, Invoice.type == doc_type)
        .order_by(Invoice.created_at.desc())
    )
    return (await db.execute(stmt)).scalars().first()


async def create_draft_for_order(
    db: AsyncSession,
    *,
    order_id: uuid.UUID,
    created_by: uuid.UUID | None = None,
) -> tuple[Invoice, bool]:
    """Create (or return the existing) draft invoice for an order.

    Idempotent: the key ``invoice:{order_id}:invoice`` pins one primary
    invoice per order; a repeat call returns ``(existing, False)``.
    """
    idem_key = f"invoice:{order_id}:invoice"
    existing = await _find_by_idempotency_key(db, idem_key)
    if existing is not None:
        return existing, False

    order = await _get_order_with_lines(db, order_id)
    user = await db.get(User, order.user_id)

    invoice = Invoice(
        order_id=order.id,
        type=InvoiceType.INVOICE,
        status=InvoiceStatus.DRAFT,
        totals=_totals_snapshot(order),
        customer=_customer_snapshot(order, user),
        idempotency_key=idem_key,
        created_by=created_by,
    )
    db.add(invoice)
    await db.flush()

    for line in _line_snapshots(order):
        db.add(InvoiceLine(invoice_id=invoice.id, **line))
    await db.flush()
    await db.refresh(invoice, attribute_names=["lines"])

    await logger.ainfo("invoice_draft_created", invoice_id=str(invoice.id), order_id=str(order_id))
    return invoice, True


# ---------------------------------------------------------------------------
# Lifecycle transitions
# ---------------------------------------------------------------------------


def _ensure_transition(invoice: Invoice, target: InvoiceStatus) -> None:
    if target not in INVOICE_TRANSITIONS.get(invoice.status, frozenset()):
        raise ConflictError(
            detail=f"Cannot transition invoice from '{invoice.status.value}' to '{target.value}'.",
            error_code="INVALID_INVOICE_TRANSITION",
        )


def ensure_mutable(invoice: Invoice) -> None:
    """Reject any edit once the document has been posted (fiscal immutability)."""
    if not invoice.is_mutable:
        raise ConflictError(
            detail="Posted invoices are immutable fiscal documents and cannot be edited.",
            error_code="INVOICE_IMMUTABLE",
        )


async def _latest_posted_hash(
    db: AsyncSession, *, doc_type: InvoiceType, fiscal_period: str
) -> str:
    """Hash of the latest posted document in this period/type chain."""
    stmt = (
        select(Invoice.hash)
        .where(
            Invoice.type == doc_type,
            Invoice.fiscal_period == fiscal_period,
            Invoice.status.in_([InvoiceStatus.POSTED, InvoiceStatus.PAID]),
        )
        .order_by(Invoice.posted_at.desc(), Invoice.created_at.desc())
        .limit(1)
    )
    latest = (await db.execute(stmt)).scalar_one_or_none()
    return latest or GENESIS_HASH


async def post_invoice(
    db: AsyncSession,
    *,
    invoice_id: uuid.UUID,
    actor_id: uuid.UUID | None = None,
) -> Invoice:
    """Post a draft: allocate number, chain hash, archive the snapshot."""
    invoice = await db.get(Invoice, invoice_id, with_for_update=True)
    if invoice is None:
        raise NotFoundError("Invoice")
    _ensure_transition(invoice, InvoiceStatus.POSTED)

    now = datetime.now(UTC)
    number, period = await allocate_next_number(db, doc_type=invoice.type, issued_at=now)
    previous_hash = await _latest_posted_hash(db, doc_type=invoice.type, fiscal_period=period)

    invoice.status = InvoiceStatus.POSTED
    invoice.number = number
    invoice.fiscal_period = period
    invoice.issued_at = now
    invoice.posted_at = now
    invoice.previous_hash = previous_hash
    invoice.hash = compute_document_hash(
        number=number, issued_at=now, totals=invoice.totals, previous_hash=previous_hash
    )
    await db.flush()

    # Archive the rendered snapshot at post time (best-effort: an archival
    # failure must not roll back the fiscal posting; the doc can be
    # re-archived from the always-reproducible HTML view).
    try:
        from app.modules.invoicing.application.pdf_renderer import archive_document
        from app.modules.orders.application.invoice_service import (
            generate_invoice_html_for_order,
        )

        html = await generate_invoice_html_for_order(
            db=db,
            order_id_or_number=invoice.order_id,
            requesting_user_id=actor_id or invoice.created_by or uuid.UUID(int=0),
            user_permissions={"orders:read"},
            user_roles={"admin"},
        )
        invoice.archive_path, invoice.archive_content_type = archive_document(
            document_key=number, html=html
        )
        await db.flush()

        # Index the frozen artifact in the DMS archive so an auditor has one
        # search surface across modules. Same fail-soft contract as the
        # archiving above: the posting is already fiscal truth, and this row
        # is an index over it — a failure here must not undo the posting. The
        # row is idempotent on (kind, document_key), so a re-post or a
        # backfill cannot duplicate it.
        try:
            from app.modules.dms.application.document_service import (
                archive_document as index_document,
            )
            from app.modules.dms.domain.models import ArchivedDocumentKind

            await index_document(
                db,
                kind=(
                    ArchivedDocumentKind.CREDIT_NOTE
                    if invoice.type == InvoiceType.CREDIT_NOTE
                    else ArchivedDocumentKind.INVOICE
                ),
                document_key=number,
                entity_type="invoice",
                entity_id=invoice.id,
                archive_path=invoice.archive_path,
                content_type=invoice.archive_content_type or "text/html",
                content_hash=invoice.hash,
                fiscal_period=period,
                metadata_json={
                    "order_id": str(invoice.order_id),
                    "status": invoice.status.value,
                },
            )
            await db.flush()
        except Exception as exc:  # noqa: BLE001 — the index must not break posting
            await logger.awarning(
                "invoice_dms_index_failed",
                invoice_id=str(invoice.id),
                error=str(exc),
            )
    except Exception as exc:  # noqa: BLE001 — archival must not break posting
        await logger.awarning(
            "invoice_archive_failed", invoice_id=str(invoice.id), error=str(exc)
        )

    await logger.ainfo(
        "invoice_posted",
        invoice_id=str(invoice.id),
        number=number,
        fiscal_period=period,
    )
    return invoice


async def mark_paid(
    db: AsyncSession, *, invoice_id: uuid.UUID, paid_at: datetime | None = None
) -> Invoice:
    """Mark a posted invoice paid (called by payment-observation flows)."""
    invoice = await db.get(Invoice, invoice_id, with_for_update=True)
    if invoice is None:
        raise NotFoundError("Invoice")
    _ensure_transition(invoice, InvoiceStatus.PAID)
    invoice.status = InvoiceStatus.PAID
    invoice.paid_at = paid_at or datetime.now(UTC)
    await db.flush()
    await logger.ainfo("invoice_marked_paid", invoice_id=str(invoice.id))
    return invoice


async def cancel_invoice(
    db: AsyncSession,
    *,
    invoice_id: uuid.UUID,
    reason: str,
    actor_id: uuid.UUID | None = None,
) -> Invoice:
    """Cancel a draft or posted-before-payment invoice with a reason.

    Cancellation rules: ``draft`` (never issued) and ``posted`` with no
    recorded payment may be cancelled; ``paid`` invoices are terminal — they
    must be corrected by a credit note instead (mirrors the transition table
    in ``domain/models.py``).
    """
    if not reason or not reason.strip():
        raise ValidationError(
            "دلیل ابطال فاکتور الزامی است", error_code="CANCEL_REASON_REQUIRED"
        )
    invoice = await db.get(Invoice, invoice_id, with_for_update=True)
    if invoice is None:
        raise NotFoundError("Invoice")
    _ensure_transition(invoice, InvoiceStatus.CANCELLED)
    if invoice.status == InvoiceStatus.POSTED and invoice.paid_at is not None:
        raise ConflictError(
            detail="A paid invoice cannot be cancelled; issue a credit note instead.",
            error_code="INVOICE_ALREADY_PAID",
        )

    invoice.status = InvoiceStatus.CANCELLED
    invoice.cancelled_at = datetime.now(UTC)
    invoice.cancel_reason = reason.strip()
    await db.flush()
    await logger.ainfo(
        "invoice_cancelled", invoice_id=str(invoice.id), actor_id=str(actor_id) if actor_id else None
    )
    return invoice


# ---------------------------------------------------------------------------
# Credit notes (refund observation — additive, never modifies the refund path)
# ---------------------------------------------------------------------------


def credit_note_idempotency_key(order_id: uuid.UUID | str, event_key: str) -> str:
    return f"invoice:{order_id}:credit:{event_key}"


async def issue_credit_note_for_refund(
    db: AsyncSession,
    *,
    order_id: uuid.UUID,
    refund_amount: int,
    reason: str,
    event_key: str,
    created_by: uuid.UUID | None = None,
) -> tuple[Invoice, bool]:
    """Issue a credit note for a completed refund, linked to the posted invoice.

    Idempotent per refund event via ``event_key`` (e.g. the RMA id or the
    outbox message id): a redelivered event returns the existing note.
    Negative-adjusted totals: the note's ``total`` is the refunded amount
    expressed as a negative integer Rial figure, so summing invoice + notes
    yields the net fiscal position.
    """
    if refund_amount <= 0:
        raise ValidationError(
            "Credit note amount must be positive", error_code="INVALID_CREDIT_AMOUNT"
        )

    idem_key = credit_note_idempotency_key(order_id, event_key)
    existing = await _find_by_idempotency_key(db, idem_key)
    if existing is not None:
        return existing, False

    original = await get_invoice_for_order(db, order_id, InvoiceType.INVOICE)
    if original is None:
        # No fiscal invoice exists for the order (e.g. legacy order predating
        # backfill) — create one on the fly in draft so the credit note still
        # has a parent document to reference.
        original, _created = await create_draft_for_order(db, order_id=order_id)

    order = await _get_order_with_lines(db, order_id)
    user = await db.get(User, order.user_id)

    base_totals = _totals_snapshot(order)
    # The refunded amount is the authoritative reversal figure (the refund
    # path already validated it against paid-minus-refunded). Integer only.
    refund = int(refund_amount)
    totals = {
        "currency": "IRR",
        "subtotal": -min(base_totals["subtotal"], refund),
        "discount": 0,
        "tax": -min(base_totals["tax"], max(refund - base_totals["subtotal"], 0)),
        "shipping": 0,
        "total": -refund,
    }

    note = Invoice(
        order_id=order_id,
        type=InvoiceType.CREDIT_NOTE,
        status=InvoiceStatus.DRAFT,
        totals=totals,
        customer=_customer_snapshot(order, user),
        credit_for_id=original.id,
        credit_reason=reason,
        idempotency_key=idem_key,
        created_by=created_by,
    )
    db.add(note)
    await db.flush()

    # Zero/negative-adjusted lines mirroring the original snapshot.
    for line in _line_snapshots(order):
        db.add(
            InvoiceLine(
                invoice_id=note.id,
                position=line["position"],
                product_name=line["product_name"],
                sku=line["sku"],
                quantity=line["quantity"],
                unit_price=-line["unit_price"],
                total_price=-line["total_price"],
            )
        )
    await db.flush()
    await db.refresh(note, attribute_names=["lines"])

    await logger.ainfo(
        "credit_note_created",
        credit_note_id=str(note.id),
        order_id=str(order_id),
        original_invoice_id=str(original.id),
        amount=refund_amount,
    )
    return note, True


# ---------------------------------------------------------------------------
# Listing / detail / chain verification
# ---------------------------------------------------------------------------


async def list_invoices(
    db: AsyncSession,
    *,
    status: InvoiceStatus | None = None,
    fiscal_period: str | None = None,
    doc_type: InvoiceType | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Invoice], int]:
    stmt = select(Invoice).options(selectinload(Invoice.lines))
    count_stmt = select(func.count()).select_from(Invoice)
    if status is not None:
        stmt = stmt.where(Invoice.status == status)
        count_stmt = count_stmt.where(Invoice.status == status)
    if fiscal_period:
        stmt = stmt.where(Invoice.fiscal_period == fiscal_period)
        count_stmt = count_stmt.where(Invoice.fiscal_period == fiscal_period)
    if doc_type is not None:
        stmt = stmt.where(Invoice.type == doc_type)
        count_stmt = count_stmt.where(Invoice.type == doc_type)

    total = (await db.execute(count_stmt)).scalar_one()
    stmt = stmt.order_by(Invoice.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    rows = list((await db.execute(stmt)).scalars().all())
    return rows, int(total)


async def get_invoice(db: AsyncSession, invoice_id: uuid.UUID) -> Invoice:
    stmt = (
        select(Invoice)
        .options(selectinload(Invoice.lines))
        .where(Invoice.id == invoice_id)
    )
    invoice = (await db.execute(stmt)).scalar_one_or_none()
    if invoice is None:
        raise NotFoundError("Invoice")
    return invoice


async def verify_chain(
    db: AsyncSession,
    *,
    doc_type: InvoiceType | None = None,
    fiscal_period: str | None = None,
) -> dict[str, Any]:
    """Recompute the hash chain and report the first broken link.

    Documents are checked in posting order per (period, type): each posted
    document's ``previous_hash`` must equal the running hash of the previous
    valid link, and its own stored ``hash`` must recompute exactly. The first
    mismatch is reported with the document id/number; anything after it is
    "unverifiable" rather than "valid" (a broken prefix poisons the suffix).
    """
    stmt = (
        select(Invoice)
        .where(Invoice.status.in_([InvoiceStatus.POSTED, InvoiceStatus.PAID, InvoiceStatus.CANCELLED]))
        .where(Invoice.number.is_not(None))
        .order_by(
            Invoice.fiscal_period.asc(),
            Invoice.type.asc(),
            Invoice.posted_at.asc(),
            Invoice.created_at.asc(),
        )
    )
    if doc_type is not None:
        stmt = stmt.where(Invoice.type == doc_type)
    if fiscal_period:
        stmt = stmt.where(Invoice.fiscal_period == fiscal_period)

    docs = list((await db.execute(stmt)).scalars().all())

    checked = 0
    running: dict[tuple[str, str], str] = {}  # (period, type) -> last valid hash
    first_broken: dict[str, Any] | None = None

    for doc in docs:
        chain_key = (doc.fiscal_period or "", doc.type.value)
        expected_prev = running.get(chain_key, GENESIS_HASH)
        prev_ok = (doc.previous_hash or GENESIS_HASH) == expected_prev
        own_ok = verify_document(
            number=doc.number or "",
            issued_at=doc.issued_at or datetime.fromtimestamp(0, UTC),
            totals=doc.totals or {},
            previous_hash=doc.previous_hash or GENESIS_HASH,
            expected_hash=doc.hash or "",
        )
        checked += 1
        if prev_ok and own_ok:
            running[chain_key] = doc.hash or GENESIS_HASH
            continue
        first_broken = {
            "invoice_id": str(doc.id),
            "number": doc.number,
            "fiscal_period": doc.fiscal_period,
            "type": doc.type.value,
            "previous_hash_ok": prev_ok,
            "own_hash_ok": own_ok,
        }
        break

    return {
        "valid": first_broken is None,
        "documents_checked": checked,
        "first_broken": first_broken,
    }
