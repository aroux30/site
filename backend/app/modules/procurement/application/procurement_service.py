"""Procurement service: supplier CRUD and the purchase-order lifecycle.

Lifecycle (ERPNext reference, rebuilt clean-room):

    draft -> sent -> partially_received -> received -> closed
      |         |            |                |
      +---------+------------+-----------------> cancelled
                                              (only before any receipt)

Rules:

- **Idempotent transitions.** Re-sending a sent PO, re-closing a closed PO,
  and re-cancelling a cancelled PO return the current state unchanged
  instead of raising. Conflicting transitions raise ``ConflictError``.
- **Receiving** accepts per-line quantities, never lets ``qty_received``
  exceed ``qty_ordered`` (DB check constraint mirrors the guard), posts the
  received units through the existing physical-ops receipt machinery
  (``create_receipt`` + ``receive_receipt`` — inventory ledger writes stay
  centralized in ``inventory_service.adjust_stock``), and records the
  link in ``purchase_order_receipts``. A PO auto-advances
  sent -> partially_received -> received; ``received`` auto-closes is
  deliberately *not* done — closing is an explicit admin action so a
  fully received PO can still be reviewed before it becomes terminal.
- **Idempotency key** on creation: the same key returns the existing PO.
- **Totals** are recomputed from lines on every mutation, integer Rial,
  tax = floor(subtotal * bps / 10_000).

Receiving is *additive* to the inventory module: the ``Receipt`` table is
untouched; the linkage lives in the procurement-owned
``purchase_order_receipts`` join table.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Iterable, NamedTuple

import structlog
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.core.exceptions.handlers import ConflictError, NotFoundError, ValidationError
from app.modules.inventory.application import physical_ops_service
from app.modules.inventory.domain.models import (
    DEFAULT_WAREHOUSE_ID,
    InventoryItem,
    ReorderRule,
)
from app.modules.procurement.domain.models import (
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseOrderReceipt,
    PurchaseOrderSequence,
    PurchaseOrderStatus,
    RECEIVABLE_PO_STATUSES,
    Supplier,
    SupplierProduct,
    TERMINAL_PO_STATUSES,
)
from app.modules.orders.application.invoice_service import gregorian_to_jalali

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_BPS_DENOMINATOR = 10_000


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _flush(db: AsyncSession) -> None:
    await db.flush()


def _clean_text(value: str | None, *, field: str, required: bool = False) -> str | None:
    cleaned = value.strip() if value else None
    if required and not cleaned:
        raise ValidationError(f"{field} is required")
    return cleaned


def _require_terminal_free(po: PurchaseOrder) -> None:
    if po.status in TERMINAL_PO_STATUSES:
        raise ConflictError(f"Cannot modify a {po.status.value} purchase order")


def recalculate_totals(po: PurchaseOrder) -> None:
    """Recompute integer-Rial subtotal/tax/total from the current lines."""
    subtotal = 0
    tax = 0
    for line in po.lines:
        line_subtotal = line.qty_ordered * line.unit_price_rial
        subtotal += line_subtotal
        tax += (line_subtotal * line.tax_basis_points) // _BPS_DENOMINATOR
    po.subtotal_rial = subtotal
    po.tax_rial = tax
    po.total_rial = subtotal + tax


# ---------------------------------------------------------------------------
# Suppliers
# ---------------------------------------------------------------------------


async def create_supplier(
    db: AsyncSession,
    *,
    name: str,
    code: str,
    contact_info: dict[str, Any] | None = None,
    payment_terms_days: int = 0,
    is_active: bool = True,
) -> Supplier:
    name_clean = _clean_text(name, field="name", required=True)
    code_clean = _clean_text(code, field="code", required=True)
    if payment_terms_days < 0:
        raise ValidationError("payment_terms_days cannot be negative")

    existing = (
        await db.execute(select(Supplier).where(Supplier.code == code_clean))
    ).scalar_one_or_none()
    if existing is not None:
        raise ConflictError(f"A supplier with code {code_clean!r} already exists")

    supplier = Supplier(
        name=name_clean,
        code=code_clean,
        contact_info=contact_info or {},
        payment_terms_days=payment_terms_days,
        is_active=is_active,
    )
    db.add(supplier)
    await _flush(db)
    await logger.ainfo("supplier_created", supplier_id=str(supplier.id), code=code_clean)
    return supplier


async def get_supplier(db: AsyncSession, supplier_id: uuid.UUID) -> Supplier:
    supplier = (
        await db.execute(select(Supplier).where(Supplier.id == supplier_id))
    ).scalar_one_or_none()
    if supplier is None:
        raise NotFoundError(resource="Supplier", detail=f"Supplier {supplier_id} not found")
    return supplier


async def list_suppliers(
    db: AsyncSession,
    *,
    is_active: bool | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[Supplier], int]:
    base = select(Supplier)
    count_base = select(func.count(Supplier.id))
    if is_active is not None:
        base = base.where(Supplier.is_active.is_(is_active))
        count_base = count_base.where(Supplier.is_active.is_(is_active))
    if search and search.strip():
        term = f"%{search.strip()}%"
        from sqlalchemy import or_

        cond = or_(Supplier.name.ilike(term), Supplier.code.ilike(term))
        base = base.where(cond)
        count_base = count_base.where(cond)
    total = (await db.execute(count_base)).scalar_one()
    rows = await db.execute(
        base.order_by(Supplier.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(rows.scalars().all()), total


async def update_supplier(
    db: AsyncSession,
    supplier_id: uuid.UUID,
    *,
    name: str | None = None,
    code: str | None = None,
    contact_info: dict[str, Any] | None = None,
    payment_terms_days: int | None = None,
    is_active: bool | None = None,
) -> Supplier:
    supplier = await get_supplier(db, supplier_id)
    if name is not None:
        supplier.name = _clean_text(name, field="name", required=True)
    if code is not None:
        code_clean = _clean_text(code, field="code", required=True)
        clash = (
            await db.execute(
                select(Supplier).where(
                    Supplier.code == code_clean, Supplier.id != supplier.id
                )
            )
        ).scalar_one_or_none()
        if clash is not None:
            raise ConflictError(f"A supplier with code {code_clean!r} already exists")
        supplier.code = code_clean
    if contact_info is not None:
        supplier.contact_info = contact_info
    if payment_terms_days is not None:
        if payment_terms_days < 0:
            raise ValidationError("payment_terms_days cannot be negative")
        supplier.payment_terms_days = payment_terms_days
    if is_active is not None:
        supplier.is_active = is_active
    await _flush(db)
    await logger.ainfo("supplier_updated", supplier_id=str(supplier.id))
    return supplier


# ---------------------------------------------------------------------------
# Preferred-supplier links (used by the suggest endpoint)
# ---------------------------------------------------------------------------


async def set_preferred_supplier(
    db: AsyncSession,
    *,
    variant_id: uuid.UUID,
    supplier_id: uuid.UUID,
    supplier_sku: str | None = None,
    last_unit_price_rial: int = 0,
) -> SupplierProduct:
    """Mark ``supplier_id`` as the preferred supplier for ``variant_id``.

    Clears the flag on any other supplier link for the variant (one
    preferred supplier per variant), upserts the pair row.
    """
    if last_unit_price_rial < 0:
        raise ValidationError("last_unit_price_rial cannot be negative")
    await get_supplier(db, supplier_id)

    links = list(
        (
            await db.execute(
                select(SupplierProduct).where(SupplierProduct.variant_id == variant_id)
            )
        )
        .scalars()
        .all()
    )
    target = next((l for l in links if l.supplier_id == supplier_id), None)
    for link in links:
        if link is not target:
            link.is_preferred = False
    if target is None:
        target = SupplierProduct(
            supplier_id=supplier_id,
            variant_id=variant_id,
            supplier_sku=supplier_sku,
            last_unit_price_rial=last_unit_price_rial,
            is_preferred=True,
        )
        db.add(target)
    else:
        target.is_preferred = True
        if supplier_sku is not None:
            target.supplier_sku = supplier_sku
        target.last_unit_price_rial = last_unit_price_rial
    await _flush(db)
    return target


# ---------------------------------------------------------------------------
# Purchase-order numbering
# ---------------------------------------------------------------------------


def _jalali_year(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    jy, _jm, _jd = gregorian_to_jalali(dt.year, dt.month, dt.day)
    return f"{jy:04d}"


async def _allocate_po_number(
    db: AsyncSession, *, supplier_id: uuid.UUID, now: datetime
) -> str:
    """Allocate the next gapless PO number for (supplier, Jalali year)."""
    year = _jalali_year(now)
    stmt = (
        select(PurchaseOrderSequence)
        .where(
            PurchaseOrderSequence.supplier_id == supplier_id,
            PurchaseOrderSequence.year == year,
        )
        .with_for_update()
    )
    seq = (await db.execute(stmt)).scalar_one_or_none()
    if seq is None:
        seq = PurchaseOrderSequence(supplier_id=supplier_id, year=year, last_value=0)
        db.add(seq)
        await _flush(db)
    seq.last_value += 1
    await _flush(db)
    return f"PO-{year}-{seq.last_value:04d}"


# ---------------------------------------------------------------------------
# Purchase orders
# ---------------------------------------------------------------------------


class POLineInput(NamedTuple):
    product_variant_id: uuid.UUID
    qty_ordered: int
    unit_price_rial: int
    tax_basis_points: int = 0
    note: str | None = None


async def _validate_line_inputs(lines: Iterable[POLineInput]) -> list[POLineInput]:
    normalized: list[POLineInput] = []
    seen: set[uuid.UUID] = set()
    for line in lines:
        if line.qty_ordered <= 0:
            raise ValidationError("qty_ordered must be a positive integer")
        if line.unit_price_rial < 0:
            raise ValidationError("unit_price_rial cannot be negative")
        if not 0 <= line.tax_basis_points <= _BPS_DENOMINATOR:
            raise ValidationError("tax_basis_points must be between 0 and 10000")
        if line.product_variant_id in seen:
            raise ValidationError("Each product variant may occur only once per purchase order")
        seen.add(line.product_variant_id)
        normalized.append(line)
    if not normalized:
        raise ValidationError("A purchase order needs at least one line")
    return normalized


async def create_purchase_order(
    db: AsyncSession,
    *,
    supplier_id: uuid.UUID,
    lines: Iterable[POLineInput],
    expected_at: datetime | None = None,
    notes: str | None = None,
    warehouse_id: uuid.UUID | None = None,
    idempotency_key: str | None = None,
    created_by: uuid.UUID | None = None,
) -> PurchaseOrder:
    supplier = await get_supplier(db, supplier_id)
    if not supplier.is_active:
        raise ConflictError("Cannot create a purchase order for an inactive supplier")

    key = _clean_text(idempotency_key, field="idempotency_key")
    if key:
        existing = (
            await db.execute(
                select(PurchaseOrder)
                .options(selectinload(PurchaseOrder.lines))
                .where(PurchaseOrder.idempotency_key == key)
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing

    normalized = await _validate_line_inputs(lines)
    now = datetime.now(UTC)

    po = PurchaseOrder(
        supplier_id=supplier.id,
        status=PurchaseOrderStatus.DRAFT,
        warehouse_id=warehouse_id or DEFAULT_WAREHOUSE_ID,
        expected_at=expected_at,
        notes=_clean_text(notes, field="notes"),
        idempotency_key=key,
        created_by=created_by,
    )
    db.add(po)
    await _flush(db)
    po.number = await _allocate_po_number(db, supplier_id=supplier.id, now=now)

    po.lines = []
    for position, line_input in enumerate(normalized, start=1):
        line = PurchaseOrderLine(
            purchase_order_id=po.id,
            product_variant_id=line_input.product_variant_id,
            position=position,
            qty_ordered=line_input.qty_ordered,
            unit_price_rial=line_input.unit_price_rial,
            tax_basis_points=line_input.tax_basis_points,
            note=_clean_text(line_input.note, field="note"),
        )
        db.add(line)
        po.lines.append(line)
    recalculate_totals(po)
    await _flush(db)
    await logger.ainfo(
        "purchase_order_created", po_id=str(po.id), number=po.number, supplier_id=str(supplier.id)
    )
    return po


async def get_purchase_order(db: AsyncSession, po_id: uuid.UUID) -> PurchaseOrder:
    stmt = (
        select(PurchaseOrder)
        .options(selectinload(PurchaseOrder.lines))
        .where(PurchaseOrder.id == po_id)
    )
    po = (await db.execute(stmt)).scalar_one_or_none()
    if po is None:
        raise NotFoundError(resource="PurchaseOrder", detail=f"Purchase order {po_id} not found")
    return po


async def list_purchase_orders(
    db: AsyncSession,
    *,
    status: PurchaseOrderStatus | None = None,
    supplier_id: uuid.UUID | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[PurchaseOrder], int]:
    base = select(PurchaseOrder)
    count_base = select(func.count(PurchaseOrder.id))
    if status is not None:
        base = base.where(PurchaseOrder.status == status)
        count_base = count_base.where(PurchaseOrder.status == status)
    if supplier_id is not None:
        base = base.where(PurchaseOrder.supplier_id == supplier_id)
        count_base = count_base.where(PurchaseOrder.supplier_id == supplier_id)
    total = (await db.execute(count_base)).scalar_one()
    rows = await db.execute(
        base.options(selectinload(PurchaseOrder.lines))
        .order_by(PurchaseOrder.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(rows.scalars().all()), total


async def update_purchase_order(
    db: AsyncSession,
    po_id: uuid.UUID,
    *,
    expected_at: datetime | None = None,
    notes: str | None = None,
    warehouse_id: uuid.UUID | None = None,
    lines: Iterable[POLineInput] | None = None,
) -> PurchaseOrder:
    """Edit a draft PO. Lines, when provided, replace the existing set."""
    po = await get_purchase_order(db, po_id)
    if po.status != PurchaseOrderStatus.DRAFT:
        raise ConflictError("Only draft purchase orders can be edited")
    if expected_at is not None:
        po.expected_at = expected_at
    if notes is not None:
        po.notes = _clean_text(notes, field="notes")
    if warehouse_id is not None:
        po.warehouse_id = warehouse_id
    if lines is not None:
        normalized = await _validate_line_inputs(lines)
        po.lines = []
        for position, line_input in enumerate(normalized, start=1):
            line = PurchaseOrderLine(
                purchase_order_id=po.id,
                product_variant_id=line_input.product_variant_id,
                position=position,
                qty_ordered=line_input.qty_ordered,
                unit_price_rial=line_input.unit_price_rial,
                tax_basis_points=line_input.tax_basis_points,
                note=_clean_text(line_input.note, field="note"),
            )
            db.add(line)
            po.lines.append(line)
        recalculate_totals(po)
    await _flush(db)
    return po


# ---------------------------------------------------------------------------
# Lifecycle transitions
# ---------------------------------------------------------------------------


async def send_purchase_order(db: AsyncSession, po_id: uuid.UUID) -> PurchaseOrder:
    """Mark a draft PO as sent to the supplier (email integration is v2)."""
    po = await get_purchase_order(db, po_id)
    if po.status == PurchaseOrderStatus.SENT:
        return po
    if po.status != PurchaseOrderStatus.DRAFT:
        raise ConflictError(f"Cannot send a {po.status.value} purchase order")
    if not po.lines:
        raise ValidationError("Cannot send a purchase order with no lines")
    po.status = PurchaseOrderStatus.SENT
    po.sent_at = datetime.now(UTC)
    await _flush(db)
    await logger.ainfo("purchase_order_sent", po_id=str(po.id), number=po.number)
    return po


async def receive_lines(
    db: AsyncSession,
    po_id: uuid.UUID,
    *,
    lines: Iterable[tuple[uuid.UUID, int]],
    notes: str | None = None,
    created_by: uuid.UUID | None = None,
) -> tuple[PurchaseOrder, uuid.UUID]:
    """Receive per-line quantities against a sent PO.

    Creates one linked inventory ``Receipt`` (via the existing physical-ops
    machinery) and posts it immediately, so stock lands in the warehouse in
    the same transaction as the PO line updates. Returns ``(po, receipt_id)``.
    """
    po = await get_purchase_order(db, po_id)
    if po.status not in RECEIVABLE_PO_STATUSES:
        raise ConflictError(f"Cannot receive against a {po.status.value} purchase order")

    requested: dict[uuid.UUID, int] = {}
    for line_id, qty in lines:
        if qty <= 0:
            raise ValidationError("Received quantities must be positive integers")
        requested[line_id] = requested.get(line_id, 0) + qty
    if not requested:
        raise ValidationError("Nothing to receive: provide at least one line quantity")

    receipt_lines: list[tuple[uuid.UUID, int]] = []
    accepted_quantities: list[tuple[uuid.UUID, int]] = []
    for line in po.lines:
        qty = requested.pop(line.id, 0)
        if qty == 0:
            continue
        if line.qty_received + qty > line.qty_ordered:
            raise ConflictError(
                f"Over-receive on line {line.id}: ordered {line.qty_ordered}, "
                f"already received {line.qty_received}, requested {qty}"
            )
        # Duplicate variants within one PO are rejected at creation, so one
        # variant maps to exactly one line here.
        receipt_lines.append((line.product_variant_id, qty))
        accepted_quantities.append((line.id, qty))
    if requested:
        raise ValidationError("Receive request references lines that do not belong to this PO")
    if not receipt_lines:
        raise ValidationError("Nothing to receive: no quantities matched PO lines")

    # Post stock through the existing blind-receipt machinery (inventory
    # module owns the ledger; procurement only orchestrates).
    # ``receive_receipt`` re-fetches the receipt by id and raises
    # NotFoundError if it is missing, so a creation that never persisted
    # cannot silently post nothing.
    receipt = await physical_ops_service.create_receipt(
        db,
        warehouse_id=po.warehouse_id,
        lines=receipt_lines,
        notes=notes or f"PO {po.number}",
        created_by=created_by,
    )
    await physical_ops_service.receive_receipt(db, receipt.id)

    accepted: dict[uuid.UUID, int] = dict(accepted_quantities)
    received_value = sum(
        line.unit_price_rial * accepted.get(line.id, 0)
        for line in po.lines
        if line.id in accepted
    )
    for line in po.lines:
        line.qty_received += accepted.pop(line.id, 0)
    link = PurchaseOrderReceipt(purchase_order_id=po.id, receipt_id=receipt.id)
    db.add(link)

    # Publish PurchaseOrderReceived outbox event to feed the general ledger
    # (debit Inventory asset, credit Accounts Payable). Runs in the same
    # transaction as the receipt.
    if received_value > 0:
        from app.shared.events.outbox_service import OutboxService

        await OutboxService.publish(
            db,
            event_type="PurchaseOrderReceived",
            aggregate_type="purchase_order",
            aggregate_id=str(po.id),
            payload={
                "po_id": str(po.id),
                "po_number": po.number,
                "receipt_id": str(receipt.id),
                "supplier_id": str(po.supplier_id),
                "amount": received_value,
            },
        )

    if all(line.qty_received >= line.qty_ordered for line in po.lines):
        po.status = PurchaseOrderStatus.RECEIVED
    else:
        po.status = PurchaseOrderStatus.PARTIALLY_RECEIVED
    await _flush(db)
    await logger.ainfo(
        "purchase_order_received_lines",
        po_id=str(po.id),
        receipt_id=str(receipt.id),
        status=po.status.value,
    )
    return po, receipt.id


async def close_purchase_order(db: AsyncSession, po_id: uuid.UUID) -> PurchaseOrder:
    """Close a PO explicitly; fully received POs close cleanly, others must
    have no pending expectation (short-close is allowed from partially
    received — the remaining quantity is abandoned)."""
    po = await get_purchase_order(db, po_id)
    if po.status == PurchaseOrderStatus.CLOSED:
        return po
    if po.status in TERMINAL_PO_STATUSES:
        raise ConflictError(f"Cannot close a {po.status.value} purchase order")
    if po.status == PurchaseOrderStatus.DRAFT:
        raise ConflictError("A draft purchase order cannot be closed; cancel it instead")
    po.status = PurchaseOrderStatus.CLOSED
    po.closed_at = datetime.now(UTC)
    await _flush(db)
    await logger.ainfo("purchase_order_closed", po_id=str(po.id), number=po.number)
    return po


async def cancel_purchase_order(db: AsyncSession, po_id: uuid.UUID) -> PurchaseOrder:
    """Cancel a PO before anything has been received against it."""
    po = await get_purchase_order(db, po_id)
    if po.status == PurchaseOrderStatus.CANCELLED:
        return po
    if po.status == PurchaseOrderStatus.CLOSED:
        raise ConflictError("A closed purchase order cannot be cancelled")
    if any(line.qty_received > 0 for line in po.lines):
        raise ConflictError(
            "Cannot cancel a purchase order with received quantities; close it instead"
        )
    po.status = PurchaseOrderStatus.CANCELLED
    po.cancelled_at = datetime.now(UTC)
    await _flush(db)
    await logger.ainfo("purchase_order_cancelled", po_id=str(po.id), number=po.number)
    return po


async def list_po_receipts(db: AsyncSession, po_id: uuid.UUID) -> list[PurchaseOrderReceipt]:
    await get_purchase_order(db, po_id)
    rows = await db.execute(
        select(PurchaseOrderReceipt)
        .where(PurchaseOrderReceipt.purchase_order_id == po_id)
        .order_by(PurchaseOrderReceipt.created_at.asc())
    )
    return list(rows.scalars().all())


# ---------------------------------------------------------------------------
# Reorder-rule integration: suggested purchase orders
# ---------------------------------------------------------------------------


class SuggestedLine(NamedTuple):
    variant_id: uuid.UUID
    warehouse_id: uuid.UUID
    available: int
    min_quantity: int
    suggested_qty: int
    preferred_supplier_id: uuid.UUID | None
    unit_price_rial: int


class SuggestedGroup(NamedTuple):
    supplier_id: uuid.UUID | None
    lines: list[SuggestedLine]


async def build_po_suggestions(
    db: AsyncSession,
    *,
    limit: int = 500,
) -> list[SuggestedGroup]:
    """Aggregate low-stock reorder rules, grouped by preferred supplier.

    A rule "fires" when the variant's available stock in the rule's
    warehouse is at or below ``min_quantity``; the suggested quantity tops
    the warehouse back up to ``reorder_to``. Rules with a preferred
    supplier (``supplier_products.is_preferred``) group under that supplier;
    the rest land in the ``supplier_id=None`` group.
    """
    rules = list(
        (
            await db.execute(
                select(ReorderRule)
                .where(ReorderRule.is_active.is_(True))
                .order_by(ReorderRule.created_at.asc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )

    # Preload preferred-supplier links for all fired variants in one query
    # (avoid N+1 per rule).
    variant_ids = list({rule.variant_id for rule in rules})
    preferred_by_variant: dict[uuid.UUID, SupplierProduct] = {}
    if variant_ids:
        links = list(
            (
                await db.execute(
                    select(SupplierProduct).where(
                        SupplierProduct.variant_id.in_(variant_ids),
                        SupplierProduct.is_preferred.is_(True),
                    )
                )
            )
            .scalars()
            .all()
        )
        preferred_by_variant = {link.variant_id: link for link in links}

    groups: dict[uuid.UUID | None, list[SuggestedLine]] = {}
    for rule in rules:
        item = (
            await db.execute(
                select(InventoryItem).where(
                    InventoryItem.variant_id == rule.variant_id,
                    InventoryItem.warehouse_id == rule.warehouse_id,
                )
            )
        ).scalar_one_or_none()
        available = item.available if item is not None else 0
        if available > rule.min_quantity:
            continue
        shortfall = rule.reorder_to - available
        if shortfall <= 0:
            continue
        preferred = preferred_by_variant.get(rule.variant_id)
        supplier_id = preferred.supplier_id if preferred is not None else None
        groups.setdefault(supplier_id, []).append(
            SuggestedLine(
                variant_id=rule.variant_id,
                warehouse_id=rule.warehouse_id,
                available=available,
                min_quantity=rule.min_quantity,
                suggested_qty=shortfall,
                preferred_supplier_id=supplier_id,
                unit_price_rial=(
                    preferred.last_unit_price_rial if preferred is not None else 0
                ),
            )
        )
    return [SuggestedGroup(supplier_id=sid, lines=ls) for sid, ls in groups.items()]


async def create_po_from_suggestions(
    db: AsyncSession,
    *,
    supplier_id: uuid.UUID,
    variant_ids: list[uuid.UUID] | None = None,
    notes: str | None = None,
    created_by: uuid.UUID | None = None,
    idempotency_key: str | None = None,
) -> PurchaseOrder:
    """Create a draft PO for ``supplier_id`` from current low-stock rules.

    ``variant_ids`` narrows the suggestion set (the preview dialog's
    selection); when omitted, every firing rule whose preferred supplier is
    this supplier is included. Variants with no preferred supplier are
    included with price 0 only when explicitly selected.
    """
    groups = await build_po_suggestions(db)
    wanted = set(variant_ids) if variant_ids else None
    chosen: list[POLineInput] = []
    for group in groups:
        for line in group.lines:
            if wanted is not None:
                if line.variant_id not in wanted:
                    continue
            elif group.supplier_id != supplier_id:
                continue
            chosen.append(
                POLineInput(
                    product_variant_id=line.variant_id,
                    qty_ordered=line.suggested_qty,
                    unit_price_rial=line.unit_price_rial,
                )
            )
    if not chosen:
        raise ValidationError("No low-stock reorder suggestions match this supplier")
    return await create_purchase_order(
        db,
        supplier_id=supplier_id,
        lines=chosen,
        notes=notes,
        idempotency_key=idempotency_key,
        created_by=created_by,
    )
