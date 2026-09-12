"""Inventory application service — stock management with row-level locking."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import func, select

from app.core.exceptions.handlers import ConflictError, NotFoundError, ValidationError
from app.modules.inventory.domain.models import (
    InventoryItem,
    InventoryReservation,
    InventoryTransaction,
    ReservationStatus,
    TransactionType,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger()


# ── Helpers ────────────────────────────────────────────────────────────────


async def _get_item_for_update(
    db: AsyncSession,
    variant_id: uuid.UUID,
) -> InventoryItem:
    """Fetch the inventory row with ``SELECT … FOR UPDATE``."""
    stmt = select(InventoryItem).where(InventoryItem.variant_id == variant_id).with_for_update()
    result = await db.execute(stmt)
    item = result.scalar_one_or_none()
    if item is None:
        raise NotFoundError(
            resource="InventoryItem",
            detail=f"No inventory record for variant {variant_id}",
        )
    return item


async def _record_transaction(
    db: AsyncSession,
    inventory_item_id: uuid.UUID,
    quantity: int,
    tx_type: TransactionType,
    reference_type: str | None = None,
    reference_id: uuid.UUID | None = None,
    notes: str | None = None,
) -> InventoryTransaction:
    txn = InventoryTransaction(
        inventory_item_id=inventory_item_id,
        quantity=quantity,
        type=tx_type,
        reference_type=reference_type,
        reference_id=reference_id,
        notes=notes,
    )
    db.add(txn)
    return txn


# ── Public API ─────────────────────────────────────────────────────────────


async def get_inventory(
    db: AsyncSession,
    variant_id: uuid.UUID,
) -> InventoryItem:
    """Return inventory record for a given product variant."""
    stmt = select(InventoryItem).where(InventoryItem.variant_id == variant_id)
    result = await db.execute(stmt)
    item = result.scalar_one_or_none()
    if item is None:
        raise NotFoundError(
            resource="InventoryItem",
            detail=f"No inventory record for variant {variant_id}",
        )
    return item


async def get_inventory_list(
    db: AsyncSession,
    *,
    page: int = 1,
    page_size: int = 50,
    low_stock_only: bool = False,
    track_inventory: bool | None = None,
) -> tuple[list[InventoryItem], int]:
    """Return a paginated list of inventory items with optional filters."""
    base = select(InventoryItem)
    count_base = select(func.count(InventoryItem.id))

    if low_stock_only:
        condition = InventoryItem.available <= InventoryItem.low_stock_threshold
        base = base.where(condition)
        count_base = count_base.where(condition)
    if track_inventory is not None:
        base = base.where(InventoryItem.track_inventory == track_inventory)
        count_base = count_base.where(InventoryItem.track_inventory == track_inventory)

    total = (await db.execute(count_base)).scalar_one()
    items_result = await db.execute(
        base.order_by(InventoryItem.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(items_result.scalars().all()), total


async def adjust_stock(
    db: AsyncSession,
    variant_id: uuid.UUID,
    quantity: int,
    tx_type: TransactionType,
    reference_type: str | None = None,
    reference_id: uuid.UUID | None = None,
    notes: str | None = None,
) -> InventoryItem:
    """Adjust stock levels with full audit trail.

    Uses ``SELECT … FOR UPDATE`` to prevent race conditions.  The caller
    must ensure the session is inside a transaction (the default ``get_db``
    dependency already commits on success / rolls back on error).
    """
    item = await _get_item_for_update(db, variant_id)

    # Apply adjustment based on type
    if tx_type == TransactionType.RECEIVED:
        if quantity <= 0:
            raise ValidationError("Received quantity must be positive")
        item.available += quantity
        item.incoming = max(0, item.incoming - quantity)

    elif tx_type == TransactionType.DAMAGED:
        if quantity <= 0:
            raise ValidationError("Damaged quantity must be positive")
        if item.available < quantity:
            raise ConflictError(
                detail=f"Cannot mark {quantity} as damaged; only {item.available} available"
            )
        item.available -= quantity
        item.damaged += quantity

    elif tx_type == TransactionType.ADJUSTED:
        # Generic adjustment — positive adds, negative removes
        new_available = item.available + quantity
        if new_available < 0:
            raise ConflictError(
                detail=f"Adjustment would bring available stock to {new_available}"
            )
        item.available = new_available

    elif tx_type == TransactionType.RETURNED:
        if quantity <= 0:
            raise ValidationError("Return quantity must be positive")
        item.available += quantity
        item.committed = max(0, item.committed - quantity)

    elif tx_type == TransactionType.SOLD:
        if quantity <= 0:
            raise ValidationError("Sold quantity must be positive")
        if item.committed < quantity:
            raise ConflictError(detail=f"Cannot sell {quantity}; only {item.committed} committed")
        item.committed -= quantity

    else:
        raise ValidationError(f"Unsupported transaction type for manual adjustment: {tx_type}")

    await _record_transaction(
        db,
        inventory_item_id=item.id,
        quantity=quantity,
        tx_type=tx_type,
        reference_type=reference_type,
        reference_id=reference_id,
        notes=notes,
    )

    await db.flush()
    await logger.ainfo(
        "inventory_adjusted",
        variant_id=str(variant_id),
        type=tx_type.value,
        quantity=quantity,
        new_available=item.available,
    )
    return item


async def reserve_stock(
    db: AsyncSession,
    variant_id: uuid.UUID,
    quantity: int,
    cart_id: uuid.UUID | None = None,
    order_id: uuid.UUID | None = None,
    ttl_minutes: int = 15,
) -> InventoryReservation:
    """Create a time-limited stock reservation.

    Decrements ``available`` and increments ``reserved``.  If the reservation
    is not confirmed within *ttl_minutes* it should be released by a
    background job.
    """
    if quantity <= 0:
        raise ValidationError("Reserve quantity must be positive")

    item = await _get_item_for_update(db, variant_id)

    if item.available < quantity and not item.backorder_allowed:
        raise ConflictError(
            detail=(
                f"Insufficient stock for variant {variant_id}: "
                f"requested {quantity}, available {item.available}"
            ),
        )

    item.available -= quantity
    item.reserved += quantity

    reservation = InventoryReservation(
        inventory_item_id=item.id,
        order_id=order_id,
        cart_id=cart_id,
        quantity=quantity,
        expires_at=datetime.now(UTC) + timedelta(minutes=ttl_minutes),
        status=ReservationStatus.PENDING,
    )
    db.add(reservation)

    await _record_transaction(
        db,
        inventory_item_id=item.id,
        quantity=quantity,
        tx_type=TransactionType.RESERVED,
        reference_type="cart" if cart_id else "order",
        reference_id=cart_id or order_id,
        notes=f"Reserved for {ttl_minutes} minutes",
    )

    await db.flush()
    await logger.ainfo(
        "stock_reserved",
        variant_id=str(variant_id),
        quantity=quantity,
        reservation_id=str(reservation.id),
        expires_at=reservation.expires_at.isoformat(),
    )
    return reservation


async def release_reservation(
    db: AsyncSession,
    reservation_id: uuid.UUID,
) -> InventoryReservation:
    """Release a pending reservation — returns reserved stock to available."""
    stmt = (
        select(InventoryReservation)
        .where(InventoryReservation.id == reservation_id)
        .with_for_update()
    )
    result = await db.execute(stmt)
    reservation = result.scalar_one_or_none()
    if reservation is None:
        raise NotFoundError(resource="InventoryReservation")

    if reservation.status != ReservationStatus.PENDING:
        raise ConflictError(
            detail=f"Reservation {reservation_id} is already {reservation.status.value}"
        )

    # Restore stock
    item_stmt = (
        select(InventoryItem)
        .where(InventoryItem.id == reservation.inventory_item_id)
        .with_for_update()
    )
    item_result = await db.execute(item_stmt)
    item = item_result.scalar_one()

    item.available += reservation.quantity
    item.reserved = max(0, item.reserved - reservation.quantity)

    reservation.status = ReservationStatus.RELEASED

    await _record_transaction(
        db,
        inventory_item_id=item.id,
        quantity=reservation.quantity,
        tx_type=TransactionType.RELEASED,
        reference_type="reservation",
        reference_id=reservation.id,
    )

    await db.flush()
    await logger.ainfo(
        "reservation_released",
        reservation_id=str(reservation_id),
        quantity=reservation.quantity,
    )
    return reservation


async def confirm_reservation(
    db: AsyncSession,
    reservation_id: uuid.UUID,
    order_id: uuid.UUID | None = None,
) -> InventoryReservation:
    """Confirm a reservation — moves stock from reserved to committed.

    When ``order_id`` is supplied the reservation is linked to the order so
    ``restock_order`` can find and release exactly these units later (and
    the fallback restock path can skip the variants already covered).
    """
    stmt = (
        select(InventoryReservation)
        .where(InventoryReservation.id == reservation_id)
        .with_for_update()
    )
    result = await db.execute(stmt)
    reservation = result.scalar_one_or_none()
    if reservation is None:
        raise NotFoundError(resource="InventoryReservation")

    if reservation.status != ReservationStatus.PENDING:
        raise ConflictError(
            detail=f"Reservation {reservation_id} is already {reservation.status.value}"
        )

    item_stmt = (
        select(InventoryItem)
        .where(InventoryItem.id == reservation.inventory_item_id)
        .with_for_update()
    )
    item_result = await db.execute(item_stmt)
    item = item_result.scalar_one()

    item.reserved = max(0, item.reserved - reservation.quantity)
    item.committed += reservation.quantity

    reservation.status = ReservationStatus.CONFIRMED

    await db.flush()
    await logger.ainfo(
        "reservation_confirmed",
        reservation_id=str(reservation_id),
        quantity=reservation.quantity,
    )
    return reservation


async def check_availability(
    db: AsyncSession,
    variant_id: uuid.UUID,
    quantity: int,
) -> bool:
    """Return ``True`` if *quantity* units are available (or backorder is allowed)."""
    stmt = select(InventoryItem).where(InventoryItem.variant_id == variant_id)
    result = await db.execute(stmt)
    item = result.scalar_one_or_none()
    if item is None:
        return False
    if not item.track_inventory:
        return True
    if item.backorder_allowed:
        return True
    return item.available >= quantity


async def get_low_stock_items(
    db: AsyncSession,
    threshold: int | None = None,
    *,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[InventoryItem], int]:
    """Return items whose available stock is at or below their threshold.

    If *threshold* is provided it overrides the per-item ``low_stock_threshold``.
    """
    if threshold is not None:
        condition = InventoryItem.available <= threshold
    else:
        condition = InventoryItem.available <= InventoryItem.low_stock_threshold

    count_stmt = select(func.count(InventoryItem.id)).where(condition)
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = (
        select(InventoryItem)
        .where(condition)
        .order_by(InventoryItem.available.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return list(rows), total


async def get_transactions(
    db: AsyncSession,
    variant_id: uuid.UUID,
    *,
    page: int = 1,
    page_size: int = 50,
    tx_type: TransactionType | None = None,
) -> tuple[list[InventoryTransaction], int]:
    """Return paginated transaction history for a variant."""
    # First get the inventory item
    item_stmt = select(InventoryItem.id).where(InventoryItem.variant_id == variant_id)
    item_result = await db.execute(item_stmt)
    inventory_item_id = item_result.scalar_one_or_none()
    if inventory_item_id is None:
        raise NotFoundError(
            resource="InventoryItem",
            detail=f"No inventory record for variant {variant_id}",
        )

    base = select(InventoryTransaction).where(
        InventoryTransaction.inventory_item_id == inventory_item_id
    )
    count_base = select(func.count(InventoryTransaction.id)).where(
        InventoryTransaction.inventory_item_id == inventory_item_id
    )

    if tx_type is not None:
        base = base.where(InventoryTransaction.type == tx_type)
        count_base = count_base.where(InventoryTransaction.type == tx_type)

    total = (await db.execute(count_base)).scalar_one()
    rows_result = await db.execute(
        base.order_by(InventoryTransaction.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(rows_result.scalars().all()), total


async def expire_stale_reservations(db: AsyncSession) -> int:
    """Release all reservations whose ``expires_at`` has passed.

    Intended to be called by a periodic background task (e.g. Celery beat).
    Returns the number of reservations released.
    """
    now = datetime.now(UTC)

    stmt = (
        select(InventoryReservation)
        .where(
            InventoryReservation.status == ReservationStatus.PENDING,
            InventoryReservation.expires_at <= now,
        )
        .with_for_update()
    )
    result = await db.execute(stmt)
    expired = list(result.scalars().all())

    released_count = 0
    for reservation in expired:
        item_stmt = (
            select(InventoryItem)
            .where(InventoryItem.id == reservation.inventory_item_id)
            .with_for_update()
        )
        item_result = await db.execute(item_stmt)
        item = item_result.scalar_one_or_none()
        if item is None:
            continue

        item.available += reservation.quantity
        item.reserved = max(0, item.reserved - reservation.quantity)
        reservation.status = ReservationStatus.EXPIRED

        await _record_transaction(
            db,
            inventory_item_id=item.id,
            quantity=reservation.quantity,
            tx_type=TransactionType.RELEASED,
            reference_type="reservation_expired",
            reference_id=reservation.id,
        )
        released_count += 1

    if released_count:
        await db.flush()
        await logger.ainfo("stale_reservations_expired", count=released_count)

    return released_count


async def restock_order(db: AsyncSession, order_id: uuid.UUID) -> int:
    """Return committed stock for a cancelled / unpaid order to available.

    Releases every CONFIRMED reservation attached to the order (committed →
    available) and, as a fallback for reservations that were never created,
    restores committed counts from the order line items.  Returns the number
    of units restocked.  Safe to call once per order — the order state
    machine prevents a second CANCELED transition.
    """
    from app.modules.orders.domain.models import OrderItem

    # Validate and normalize the identifier before it reaches the query layer.
    safe_order_id = uuid.UUID(str(order_id))

    reservation_stmt = (
        select(InventoryReservation).filter_by(order_id=safe_order_id).with_for_update()
    )
    reservations = list((await db.scalars(reservation_stmt)).all())

    restocked = 0
    handled_variant_ids: set[uuid.UUID] = set()

    for reservation in reservations:
        item_stmt = (
            select(InventoryItem).filter_by(id=reservation.inventory_item_id).with_for_update()
        )
        item = await db.scalar(item_stmt)

        if reservation.status == ReservationStatus.CONFIRMED:
            if item is not None:
                item.committed = max(0, item.committed - reservation.quantity)
                item.available += reservation.quantity
                restocked += reservation.quantity

                await _record_transaction(
                    db,
                    inventory_item_id=item.id,
                    quantity=reservation.quantity,
                    tx_type=TransactionType.RELEASED,
                    reference_type="order_cancellation",
                    reference_id=reservation.id,
                    notes="Stock returned to available on order cancellation",
                )
            reservation.status = ReservationStatus.RELEASED
        elif reservation.status == ReservationStatus.PENDING:
            if item is not None:
                item.reserved = max(0, item.reserved - reservation.quantity)
                item.available += reservation.quantity
                restocked += reservation.quantity

                await _record_transaction(
                    db,
                    inventory_item_id=item.id,
                    quantity=reservation.quantity,
                    tx_type=TransactionType.RELEASED,
                    reference_type="order_cancellation",
                    reference_id=reservation.id,
                    notes="Pending reservation released on order cancellation",
                )
            reservation.status = ReservationStatus.RELEASED

    # Fallback: order items with no reservation row (data drift) — only
    # restock when committed stock still covers the quantity.
    items_stmt = select(OrderItem).filter_by(order_id=safe_order_id)
    order_items = (await db.scalars(items_stmt)).all()
    for order_item in order_items:
        if order_item.variant_id in handled_variant_ids:
            continue
        handled_variant_ids.add(order_item.variant_id)
        item_stmt = (
            select(InventoryItem).filter_by(variant_id=order_item.variant_id).with_for_update()
        )
        item = await db.scalar(item_stmt)
        if item is not None and item.committed >= order_item.quantity:
            item.committed -= order_item.quantity
            item.available += order_item.quantity
            restocked += order_item.quantity

            await _record_transaction(
                db,
                inventory_item_id=item.id,
                quantity=order_item.quantity,
                tx_type=TransactionType.RELEASED,
                reference_type="order_cancellation",
                reference_id=order_id,
                notes="Fallback restock for order item without reservation",
            )

    if restocked:
        await db.flush()
        await logger.ainfo(
            "order_restocked",
            order_id=str(order_id),
            units_restocked=restocked,
        )
    return restocked


async def restock_returned_items(
    db: AsyncSession,
    entries: list[tuple[uuid.UUID, int]],
) -> int:
    """Return inspected-and-passed return items to available inventory.

    Each entry is ``(variant_id, quantity)``.  Committed stock is moved back
    to available (the order's committed units are still held when an order is
    delivered/completed, so returning them from ``committed`` is correct).
    Returns the number of units restocked.
    """
    restocked = 0
    for variant_id, quantity in entries:
        safe_variant_id = uuid.UUID(str(variant_id))
        safe_quantity = int(quantity)
        if safe_quantity <= 0:
            continue
        item_stmt = select(InventoryItem).filter_by(variant_id=safe_variant_id).with_for_update()
        item = await db.scalar(item_stmt)
        if item is None or item.committed < safe_quantity:
            await logger.awarning(
                "return_restock_skipped",
                variant_id=str(safe_variant_id),
                quantity=safe_quantity,
                committed=item.committed if item is not None else None,
            )
            continue
        item.committed -= safe_quantity
        item.available += safe_quantity
        restocked += safe_quantity

        await _record_transaction(
            db,
            inventory_item_id=item.id,
            quantity=safe_quantity,
            tx_type=TransactionType.RETURNED,
            reference_type="return_restock",
            reference_id=safe_variant_id,
            notes="Stock returned to available after passed return inspection",
        )

    if restocked:
        await db.flush()
        await logger.ainfo("return_items_restocked", units_restocked=restocked)
    return restocked
