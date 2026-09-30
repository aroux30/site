"""Stale reservation cleanup — closes the stock-leak loop (QA B27).

``expire_stale_reservations`` in ``inventory_service`` only releases
PENDING reservations, and nothing ever called it.  Two leaks therefore
locked stock forever:

1. PENDING reservations of abandoned carts (never released);
2. CONFIRMED reservations of orders that never got paid — checkout
   confirms stock at order-creation time, so an abandoned payment kept
   ``committed`` units locked while ``available`` stayed at zero.

``release_stale_reservations`` runs both passes and is wired into the
periodic background task in ``app.main`` (plus one run at startup).
All statements are fully parameterized (bound parameters only).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import structlog
from sqlalchemy import Integer, String, bindparam, text

from app.modules.inventory.application.inventory_service import (
    _payment_window_minutes,
    expire_stale_reservations,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# CONFIRMED reservations past their TTL whose order is missing, still
# unpaid, or already CANCELED (a canceled order's stuck CONFIRMED hold used
# to leak committed stock forever because nothing picked it up).
# Enum columns persist the member NAME (uppercase).
_FETCH_STALE_CONFIRMED_SQL = text(
    """
    SELECT r.id, r.inventory_item_id, r.quantity, r.order_id
    FROM inventory_reservations r
    LEFT JOIN orders o ON o.id = r.order_id
    WHERE r.status = CAST(:confirmed AS VARCHAR)
      AND r.expires_at <= now()
      AND (
        r.order_id IS NULL
        OR (
          o.status IN (CAST(:pending AS VARCHAR), CAST(:canceled AS VARCHAR))
          -- Releasing on `o.status` alone is not enough: a customer who pays
          -- while the hold is still alive flips the order to CONFIRMED, but a
          -- webhook can lag, and an order that was paid and then reverted to a
          -- pending state was equally sellable. The only safe test is whether
          -- the order is *older than its own payment window* -- past that point
          -- nobody can still pay it, so the stock is genuinely free.
          AND o.created_at + make_interval(mins => :window) <= now()
        )
      )
    ORDER BY r.expires_at
    LIMIT 500
    FOR UPDATE OF r
    """
).bindparams(
    bindparam("confirmed", type_=String),
    bindparam("pending", type_=String),
    bindparam("canceled", type_=String),
)

# Return committed units to available stock.
_RELEASE_ITEM_SQL = text(
    """
    UPDATE inventory_items
    SET committed = GREATEST(committed - CAST(:qty AS INTEGER), 0),
        available = available + CAST(:qty AS INTEGER),
        updated_at = now()
    WHERE id = CAST(:item_id AS UUID)
    """
).bindparams(bindparam("qty", type_=Integer))

_EXPIRE_RESERVATION_SQL = text(
    """
    UPDATE inventory_reservations
    SET status = CAST(:expired AS VARCHAR), updated_at = now()
    WHERE id = CAST(:rid AS UUID)
    """
)

_AUDIT_INSERT_SQL = text(
    """
    INSERT INTO inventory_transactions
        (id, inventory_item_id, quantity, type, reference_type, reference_id,
         notes, created_at, updated_at)
    VALUES (CAST(:id AS UUID), CAST(:item_id AS UUID), CAST(:qty AS INTEGER),
            CAST(:type AS VARCHAR), CAST(:ref_type AS VARCHAR),
            CAST(:rid AS UUID), :notes, now(), now())
    """
)


async def release_stale_reservations(db: AsyncSession) -> int:
    """Release every reservation whose TTL has passed.

    Pass 1 delegates to ``expire_stale_reservations`` (PENDING holds).
    Pass 2 releases CONFIRMED reservations of unpaid, canceled, or order-less
    holds, returning their ``committed`` units to ``available``.
    Reservations of paid/processed orders are never touched.
    Returns the total number of reservations released.
    """
    released = await expire_stale_reservations(db)

    rows = (
        await db.execute(
            _FETCH_STALE_CONFIRMED_SQL,
            {
                "confirmed": "CONFIRMED",
                "pending": "PENDING",
                "canceled": "CANCELED",
                "window": _payment_window_minutes(),
            },
        )
    ).mappings().all()

    for row in rows:
        item_id: UUID = row["inventory_item_id"]
        qty: int = int(row["quantity"])
        reservation_id: UUID = row["id"]
        order_id = row["order_id"]

        # Re-check the order status under an order row lock: a gateway
        # verify may have confirmed the order between the SELECT above and
        # now — in that case the stock is legitimately sold and must stay
        # committed.
        if order_id is not None:
            status_row = (
                await db.execute(
                    text("SELECT status FROM orders WHERE id = CAST(:oid AS UUID) FOR UPDATE"),
                    {"oid": str(order_id)},
                )
            ).first()
            if status_row is None or status_row[0] not in ("PENDING", "CANCELED"):
                continue

        await db.execute(
            _RELEASE_ITEM_SQL,
            {"qty": qty, "item_id": str(item_id)},
        )
        await db.execute(
            _EXPIRE_RESERVATION_SQL,
            {"expired": "EXPIRED", "rid": str(reservation_id)},
        )
        await db.execute(
            _AUDIT_INSERT_SQL,
            {
                "id": str(uuid4()),
                "item_id": str(item_id),
                "qty": qty,
                "type": "RELEASED",
                "ref_type": "reservation_expired_unpaid",
                "rid": str(reservation_id),
                "notes": "Confirmed stock released: order never paid before reservation TTL",
            },
        )
        released += 1

    if rows:
        await logger.ainfo(
            "confirmed_reservations_released_unpaid",
            count=len(rows),
            total_released=released,
        )

    return released
