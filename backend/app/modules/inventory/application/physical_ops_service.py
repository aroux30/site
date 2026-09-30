"""Inventory physical operations: cycle counts, transfers, and blind receipts.

All quantity mutations deliberately delegate to ``inventory_service``.  The
inventory transaction ledger is therefore the sole source of truth: operations
store workflow state and never write ``InventoryItem.available`` directly.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Iterable

import structlog
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.core.exceptions.handlers import ConflictError, NotFoundError, ValidationError
from app.modules.inventory.application import inventory_service
from app.modules.inventory.domain.models import (
    DEFAULT_WAREHOUSE_ID,
    InventoryItem,
    Receipt,
    ReceiptLine,
    ReceiptStatus,
    StockCount,
    StockCountLine,
    StockCountScope,
    StockCountStatus,
    TransactionType,
    TransferStatus,
    WarehouseTransfer,
    WarehouseTransferLine,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger()


# ---------------------------------------------------------------------------
# Small shared helpers
# ---------------------------------------------------------------------------


def _as_uuid(value: uuid.UUID | str, *, field: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{field} must be a valid UUID") from exc


def _positive_int(value: int, *, field: str) -> int:
    # bool is an int subclass but is not an operational quantity.
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValidationError(f"{field} must be a positive integer")
    return value


def _non_negative_int(value: int, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValidationError(f"{field} must be a non-negative integer")
    return value


def _normalize_lines(
    lines: Iterable[tuple[uuid.UUID | str, int]], *, field: str = "lines"
) -> list[tuple[uuid.UUID, int]]:
    """Validate and coalesce variant rows before persistent workflow creation."""
    normalized: dict[uuid.UUID, int] = {}
    for raw_variant_id, raw_quantity in lines:
        variant_id = _as_uuid(raw_variant_id, field=f"{field}.product_variant_id")
        quantity = _positive_int(raw_quantity, field=f"{field}.quantity")
        normalized[variant_id] = normalized.get(variant_id, 0) + quantity
    if not normalized:
        raise ValidationError(f"{field} must contain at least one line")
    return list(normalized.items())


async def _flush(db: AsyncSession) -> None:
    """Keep an explicit flush boundary before an API response or next action."""
    await db.flush()


# ---------------------------------------------------------------------------
# Stock counts
# ---------------------------------------------------------------------------


def _validated_scope_filter(
    scope: StockCountScope, scope_filter: dict[str, Any] | None
) -> tuple[dict[str, Any], list[uuid.UUID] | None, uuid.UUID | None]:
    """Normalize the JSON snapshot selector without trusting client shape."""
    raw = dict(scope_filter or {})
    if scope == StockCountScope.FULL:
        if raw:
            raise ValidationError("full stock counts cannot include a scope filter")
        return {}, None, None

    if scope == StockCountScope.CATEGORY:
        category_id = raw.get("category_id")
        if category_id is None:
            raise ValidationError("category stock counts require scope_filter.category_id")
        parsed = _as_uuid(category_id, field="scope_filter.category_id")
        return {"category_id": str(parsed)}, None, parsed

    if scope == StockCountScope.PRODUCT_LIST:
        values = raw.get("product_variant_ids")
        if not isinstance(values, list) or not values:
            raise ValidationError(
                "product-list stock counts require a non-empty scope_filter.product_variant_ids"
            )
        ids: list[uuid.UUID] = []
        seen: set[uuid.UUID] = set()
        for value in values:
            parsed = _as_uuid(value, field="scope_filter.product_variant_ids")
            if parsed not in seen:
                ids.append(parsed)
                seen.add(parsed)
        return {"product_variant_ids": [str(value) for value in ids]}, ids, None

    raise ValidationError("Unsupported stock-count scope")


async def _snapshot_items(
    db: AsyncSession,
    *,
    warehouse_id: uuid.UUID,
    scope: StockCountScope,
    variant_ids: list[uuid.UUID] | None,
    category_id: uuid.UUID | None,
) -> list[InventoryItem]:
    """Fetch stock rows for a count, scoped to one warehouse and selection."""
    stmt = select(InventoryItem).where(InventoryItem.warehouse_id == warehouse_id)
    if scope == StockCountScope.PRODUCT_LIST:
        assert variant_ids is not None  # validated above
        stmt = stmt.where(InventoryItem.variant_id.in_(variant_ids))
    elif scope == StockCountScope.CATEGORY:
        assert category_id is not None  # validated above
        from app.modules.catalog.domain.models import Product, ProductVariant

        stmt = (
            stmt.join(ProductVariant, ProductVariant.id == InventoryItem.variant_id)
            .join(Product, Product.id == ProductVariant.product_id)
            .where(Product.category_id == category_id)
        )
    # Lock the selected stock rows until the header/line snapshot is flushed,
    # so a count starts from one coherent ledger state rather than a moving
    # mixture of rows.
    result = await db.execute(stmt.order_by(InventoryItem.variant_id).with_for_update())
    return list(result.scalars().all())


async def create_stock_count(
    db: AsyncSession,
    *,
    warehouse_id: uuid.UUID | None,
    scope: StockCountScope,
    scope_filter: dict[str, Any] | None,
    created_by: uuid.UUID | None,
) -> StockCount:
    """Create a count session and freeze current available quantities as lines."""
    resolved_warehouse_id = warehouse_id or DEFAULT_WAREHOUSE_ID
    normalized_filter, variant_ids, category_id = _validated_scope_filter(scope, scope_filter)
    items = await _snapshot_items(
        db,
        warehouse_id=resolved_warehouse_id,
        scope=scope,
        variant_ids=variant_ids,
        category_id=category_id,
    )

    count = StockCount(
        warehouse_id=resolved_warehouse_id,
        status=StockCountStatus.DRAFT,
        scope=scope,
        scope_filter=normalized_filter,
        created_by=created_by,
        line_count=len(items),
    )
    db.add(count)
    await _flush(db)

    count.lines = []
    for item in items:
        # This v1 count reconciles the ledger's available bucket. Reservations
        # and committed units are protected by their existing flows and must
        # never be adjusted by physical operations.
        line = StockCountLine(
            count_id=count.id,
            product_variant_id=item.variant_id,
            system_qty=item.available,
        )
        count.lines.append(line)
        db.add(line)
    await _flush(db)
    await logger.ainfo(
        "stock_count_created",
        count_id=str(count.id),
        warehouse_id=str(resolved_warehouse_id),
        scope=scope.value,
        line_count=len(items),
    )
    return count


async def get_stock_count(db: AsyncSession, count_id: uuid.UUID) -> StockCount:
    stmt = (
        select(StockCount)
        .options(selectinload(StockCount.lines))
        .where(StockCount.id == _as_uuid(count_id, field="count_id"))
    )
    count = (await db.execute(stmt)).scalar_one_or_none()
    if count is None:
        raise NotFoundError("StockCount")
    return count


async def list_stock_counts(
    db: AsyncSession,
    *,
    status: StockCountStatus | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[StockCount], int]:
    base = select(StockCount)
    count_base = select(func.count(StockCount.id))
    if status is not None:
        base = base.where(StockCount.status == status)
        count_base = count_base.where(StockCount.status == status)
    total = (await db.execute(count_base)).scalar_one()
    rows = await db.execute(
        base.options(selectinload(StockCount.lines))
        .order_by(StockCount.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(rows.scalars().all()), total


async def start_stock_count(db: AsyncSession, count_id: uuid.UUID) -> StockCount:
    count = await get_stock_count(db, count_id)
    if count.status == StockCountStatus.COUNTING:
        return count
    if count.status != StockCountStatus.DRAFT:
        raise ConflictError(f"Stock count is already {count.status.value}")
    count.status = StockCountStatus.COUNTING
    count.started_at = datetime.now(UTC)
    await _flush(db)
    return count


async def enter_stock_count_lines(
    db: AsyncSession,
    *,
    count_id: uuid.UUID,
    lines: Iterable[tuple[uuid.UUID | str, int, str | None]],
) -> StockCount:
    """Enter one or more physical quantities; count must be actively counting."""
    count = await get_stock_count(db, count_id)
    if count.status == StockCountStatus.DRAFT:
        count.status = StockCountStatus.COUNTING
        count.started_at = datetime.now(UTC)
    if count.status != StockCountStatus.COUNTING:
        raise ConflictError(f"Cannot enter lines for a {count.status.value} stock count")

    by_variant = {line.product_variant_id: line for line in count.lines}
    updates = list(lines)
    if not updates:
        raise ValidationError("lines must contain at least one line")
    seen: set[uuid.UUID] = set()
    for raw_variant_id, counted_qty, note in updates:
        variant_id = _as_uuid(raw_variant_id, field="lines.product_variant_id")
        if variant_id in seen:
            raise ValidationError("Each product variant may appear only once per request")
        seen.add(variant_id)
        _non_negative_int(counted_qty, field="lines.counted_qty")
        line = by_variant.get(variant_id)
        if line is None:
            raise ValidationError("Product variant is not part of this stock-count snapshot")
        line.counted_qty = counted_qty
        line.note = note.strip() if isinstance(note, str) and note.strip() else None

    _recalculate_stock_count_stats(count)
    await _flush(db)
    return count


def _recalculate_stock_count_stats(count: StockCount) -> None:
    lines = list(count.lines)
    completed = [line for line in lines if line.counted_qty is not None]
    variances = [line.variance for line in completed if line.variance not in (None, 0)]
    count.line_count = len(lines)
    count.counted_line_count = len(completed)
    count.variance_line_count = len(variances)
    count.variance_quantity = sum(abs(variance) for variance in variances if variance is not None)


async def review_stock_count(db: AsyncSession, count_id: uuid.UUID) -> StockCount:
    count = await get_stock_count(db, count_id)
    if count.status == StockCountStatus.REVIEW:
        return count
    if count.status != StockCountStatus.COUNTING:
        raise ConflictError(f"Cannot review a {count.status.value} stock count")
    _recalculate_stock_count_stats(count)
    if count.counted_line_count != count.line_count:
        raise ValidationError("Every stock-count line must have a counted quantity before review")
    count.status = StockCountStatus.REVIEW
    await _flush(db)
    return count


async def post_stock_count(db: AsyncSession, count_id: uuid.UUID) -> StockCount:
    """Post each frozen variance through the normal adjustment/ledger path.

    A status guard makes repeated calls idempotent after a successful post. The
    entire handler runs within the request transaction, so a failed adjustment
    rolls all adjustments and the status transition back together.
    """
    count = await get_stock_count(db, count_id)
    if count.status == StockCountStatus.POSTED:
        return count
    if count.status != StockCountStatus.REVIEW:
        raise ConflictError(f"Cannot post a {count.status.value} stock count")
    _recalculate_stock_count_stats(count)
    if count.counted_line_count != count.line_count:
        raise ValidationError("Every stock-count line must have a counted quantity before posting")

    for line in count.lines:
        variance = line.variance
        if variance:
            # Stock-count snapshots deliberately cover the available bucket;
            # reservations and committed quantities remain exclusively under
            # their existing order flows.  ``adjust_stock`` takes the row lock
            # and writes the audit entry, so no physical operation writes a
            # quantity directly.
            await inventory_service.adjust_stock(
                db,
                variant_id=line.product_variant_id,
                quantity=variance,
                tx_type=TransactionType.ADJUSTED,
                reference_type="stock_count",
                reference_id=count.id,
                notes=line.note or f"Cycle count variance for session {count.id}",
                warehouse_id=count.warehouse_id,
            )

    count.status = StockCountStatus.POSTED
    count.posted_at = datetime.now(UTC)
    await _flush(db)
    await logger.ainfo(
        "stock_count_posted",
        count_id=str(count.id),
        variance_lines=count.variance_line_count,
        variance_quantity=count.variance_quantity,
    )
    return count


async def cancel_stock_count(db: AsyncSession, count_id: uuid.UUID) -> StockCount:
    count = await get_stock_count(db, count_id)
    if count.status == StockCountStatus.CANCELLED:
        return count
    if count.status == StockCountStatus.POSTED:
        raise ConflictError("Posted stock counts cannot be cancelled; use a new corrective count")
    count.status = StockCountStatus.CANCELLED
    await _flush(db)
    return count


# ---------------------------------------------------------------------------
# Warehouse transfers
# ---------------------------------------------------------------------------


async def get_transfer(db: AsyncSession, transfer_id: uuid.UUID) -> WarehouseTransfer:
    stmt = (
        select(WarehouseTransfer)
        .options(selectinload(WarehouseTransfer.lines))
        .where(WarehouseTransfer.id == _as_uuid(transfer_id, field="transfer_id"))
    )
    transfer = (await db.execute(stmt)).scalar_one_or_none()
    if transfer is None:
        raise NotFoundError("WarehouseTransfer")
    return transfer


async def list_transfers(
    db: AsyncSession,
    *,
    status: TransferStatus | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[WarehouseTransfer], int]:
    base = select(WarehouseTransfer)
    count_base = select(func.count(WarehouseTransfer.id))
    if status is not None:
        base = base.where(WarehouseTransfer.status == status)
        count_base = count_base.where(WarehouseTransfer.status == status)
    total = (await db.execute(count_base)).scalar_one()
    rows = await db.execute(
        base.options(selectinload(WarehouseTransfer.lines))
        .order_by(WarehouseTransfer.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(rows.scalars().all()), total


async def create_transfer(
    db: AsyncSession,
    *,
    from_warehouse_id: uuid.UUID,
    to_warehouse_id: uuid.UUID,
    lines: Iterable[tuple[uuid.UUID | str, int]],
    idempotency_key: str | None,
    notes: str | None,
    created_by: uuid.UUID | None,
) -> WarehouseTransfer:
    from_id = _as_uuid(from_warehouse_id, field="from_warehouse_id")
    to_id = _as_uuid(to_warehouse_id, field="to_warehouse_id")
    if from_id == to_id:
        raise ValidationError("Cannot transfer stock to the same warehouse")
    normalized_lines = _normalize_lines(lines)
    key = idempotency_key.strip() if idempotency_key and idempotency_key.strip() else None
    if key:
        existing_stmt = (
            select(WarehouseTransfer)
            .options(selectinload(WarehouseTransfer.lines))
            .where(WarehouseTransfer.idempotency_key == key)
        )
        existing = (await db.execute(existing_stmt)).scalar_one_or_none()
        if existing is not None:
            return existing

    transfer = WarehouseTransfer(
        from_warehouse_id=from_id,
        to_warehouse_id=to_id,
        status=TransferStatus.DRAFT,
        notes=notes.strip() if notes and notes.strip() else None,
        idempotency_key=key,
        created_by=created_by,
    )
    db.add(transfer)
    await _flush(db)
    transfer.lines = []
    for variant_id, quantity in normalized_lines:
        line = WarehouseTransferLine(
            transfer_id=transfer.id,
            product_variant_id=variant_id,
            quantity=quantity,
        )
        db.add(line)
        transfer.lines.append(line)
    await _flush(db)
    return transfer


async def ship_transfer(db: AsyncSession, transfer_id: uuid.UUID) -> WarehouseTransfer:
    """Ship a transfer: debit the source only; receipt credits destination later."""
    transfer = await get_transfer(db, transfer_id)
    if transfer.status == TransferStatus.SHIPPED:
        return transfer
    if transfer.status != TransferStatus.DRAFT:
        raise ConflictError(f"Cannot ship a {transfer.status.value} transfer")

    for line in transfer.lines:
        # Deliberately reuse the typed transaction / lock machinery. A negative
        # ADJUSTED movement supplies the in-transit debit without touching the
        # destination before its physical receipt.
        await inventory_service.adjust_stock(
            db,
            variant_id=line.product_variant_id,
            quantity=-line.quantity,
            tx_type=TransactionType.ADJUSTED,
            reference_type="warehouse_transfer_shipment",
            reference_id=transfer.id,
            notes=transfer.notes or f"Transfer shipped to warehouse {transfer.to_warehouse_id}",
            warehouse_id=transfer.from_warehouse_id,
        )
    transfer.status = TransferStatus.SHIPPED
    transfer.shipped_at = datetime.now(UTC)
    await _flush(db)
    return transfer


async def receive_transfer(db: AsyncSession, transfer_id: uuid.UUID) -> WarehouseTransfer:
    """Receive an in-transit transfer by creating destination ledger entries."""
    transfer = await get_transfer(db, transfer_id)
    if transfer.status == TransferStatus.RECEIVED:
        return transfer
    if transfer.status != TransferStatus.SHIPPED:
        raise ConflictError(f"Cannot receive a {transfer.status.value} transfer")

    for line in transfer.lines:
        await _receive_into_warehouse(
            db,
            variant_id=line.product_variant_id,
            quantity=line.quantity,
            warehouse_id=transfer.to_warehouse_id,
            reference_type="warehouse_transfer_receipt",
            reference_id=transfer.id,
            notes=transfer.notes or f"Transfer received from warehouse {transfer.from_warehouse_id}",
        )
    transfer.status = TransferStatus.RECEIVED
    transfer.received_at = datetime.now(UTC)
    await _flush(db)
    return transfer


async def cancel_transfer(db: AsyncSession, transfer_id: uuid.UUID) -> WarehouseTransfer:
    transfer = await get_transfer(db, transfer_id)
    if transfer.status == TransferStatus.CANCELLED:
        return transfer
    if transfer.status != TransferStatus.DRAFT:
        raise ConflictError("Only draft transfers can be cancelled; shipped stock must be received")
    transfer.status = TransferStatus.CANCELLED
    await _flush(db)
    return transfer


# ---------------------------------------------------------------------------
# Blind receipts
# ---------------------------------------------------------------------------


async def get_receipt(db: AsyncSession, receipt_id: uuid.UUID) -> Receipt:
    stmt = (
        select(Receipt)
        .options(selectinload(Receipt.lines))
        .where(Receipt.id == _as_uuid(receipt_id, field="receipt_id"))
    )
    receipt = (await db.execute(stmt)).scalar_one_or_none()
    if receipt is None:
        raise NotFoundError("Receipt")
    return receipt


async def list_receipts(
    db: AsyncSession,
    *,
    status: ReceiptStatus | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[Receipt], int]:
    base = select(Receipt)
    count_base = select(func.count(Receipt.id))
    if status is not None:
        base = base.where(Receipt.status == status)
        count_base = count_base.where(Receipt.status == status)
    total = (await db.execute(count_base)).scalar_one()
    rows = await db.execute(
        base.options(selectinload(Receipt.lines))
        .order_by(Receipt.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(rows.scalars().all()), total


async def create_receipt(
    db: AsyncSession,
    *,
    warehouse_id: uuid.UUID | None,
    lines: Iterable[tuple[uuid.UUID | str, int]],
    notes: str | None,
    created_by: uuid.UUID | None,
) -> Receipt:
    receipt = Receipt(
        warehouse_id=warehouse_id or DEFAULT_WAREHOUSE_ID,
        status=ReceiptStatus.DRAFT,
        notes=notes.strip() if notes and notes.strip() else None,
        created_by=created_by,
    )
    normalized_lines = _normalize_lines(lines)
    db.add(receipt)
    await _flush(db)
    receipt.lines = []
    for variant_id, quantity in normalized_lines:
        line = ReceiptLine(
            receipt_id=receipt.id,
            product_variant_id=variant_id,
            quantity=quantity,
        )
        db.add(line)
        receipt.lines.append(line)
    await _flush(db)
    return receipt


async def receive_receipt(db: AsyncSession, receipt_id: uuid.UUID) -> Receipt:
    receipt = await get_receipt(db, receipt_id)
    if receipt.status == ReceiptStatus.RECEIVED:
        return receipt
    if receipt.status != ReceiptStatus.DRAFT:
        raise ConflictError(f"Cannot receive a {receipt.status.value} receipt")
    for line in receipt.lines:
        await _receive_into_warehouse(
            db,
            variant_id=line.product_variant_id,
            quantity=line.quantity,
            warehouse_id=receipt.warehouse_id,
            reference_type="inventory_receipt",
            reference_id=receipt.id,
            notes=receipt.notes or "Blind receiving v1",
        )
    receipt.status = ReceiptStatus.RECEIVED
    receipt.received_at = datetime.now(UTC)
    await _flush(db)
    return receipt


async def cancel_receipt(db: AsyncSession, receipt_id: uuid.UUID) -> Receipt:
    receipt = await get_receipt(db, receipt_id)
    if receipt.status == ReceiptStatus.CANCELLED:
        return receipt
    if receipt.status != ReceiptStatus.DRAFT:
        raise ConflictError("Received receipts cannot be cancelled; use a correcting adjustment")
    receipt.status = ReceiptStatus.CANCELLED
    await _flush(db)
    return receipt


async def _receive_into_warehouse(
    db: AsyncSession,
    *,
    variant_id: uuid.UUID,
    quantity: int,
    warehouse_id: uuid.UUID,
    reference_type: str,
    reference_id: uuid.UUID,
    notes: str | None,
) -> InventoryItem:
    """Receive stock into a warehouse, creating an empty stock row if needed.

    ``adjust_stock`` owns validation, row locking, and the typed ledger entry;
    only the idempotent destination-row creation belongs here because regular
    receipts may introduce a SKU to a warehouse for the first time.
    """
    try:
        return await inventory_service.adjust_stock(
            db,
            variant_id=variant_id,
            quantity=quantity,
            tx_type=TransactionType.RECEIVED,
            reference_type=reference_type,
            reference_id=reference_id,
            notes=notes,
            warehouse_id=warehouse_id,
        )
    except NotFoundError:
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        await db.execute(
            pg_insert(InventoryItem)
            .values(
                variant_id=variant_id,
                warehouse_id=warehouse_id,
                available=0,
                reserved=0,
                committed=0,
                damaged=0,
                incoming=0,
            )
            .on_conflict_do_nothing()
        )
        await _flush(db)
        return await inventory_service.adjust_stock(
            db,
            variant_id=variant_id,
            quantity=quantity,
            tx_type=TransactionType.RECEIVED,
            reference_type=reference_type,
            reference_id=reference_id,
            notes=notes,
            warehouse_id=warehouse_id,
        )
