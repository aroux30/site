"""Celery tasks for the invoicing module (historical backfill)."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

import structlog
from sqlalchemy import select

from app.core.database.session import async_session_factory
from app.modules.invoicing.application import invoice_service
from app.modules.invoicing.domain.models import Invoice, InvoiceType
from app.modules.orders.domain.models import Order, OrderStatus
from app.worker.celery_app import celery_app

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# Order states that represent money actually received (mirrors the payment
# lifecycle: only orders that got past payment are fiscal documents).
_PAID_ORDER_STATUSES = (
    OrderStatus.CONFIRMED,
    OrderStatus.PROCESSING,
    OrderStatus.PACKING,
    OrderStatus.SHIPPED,
    OrderStatus.DELIVERED,
    OrderStatus.COMPLETED,
    OrderStatus.PARTIALLY_REFUNDED,
    OrderStatus.REFUNDED,
    OrderStatus.RETURNED,
)

_BATCH_LIMIT = 200


async def _backfill_batch_async(*, batch_size: int = _BATCH_LIMIT) -> dict[str, Any]:
    """Create draft invoices for paid orders that do not have one yet.

    Idempotent: selection is anti-joined against existing invoices of type
    ``invoice``, and ``create_draft_for_order`` itself dedupes on the
    ``invoice:{order_id}:invoice`` idempotency key, so reruns and overlapping
    batches cannot create duplicates.
    """
    created = 0
    skipped = 0

    async with async_session_factory() as db:
        async with db.begin():
            existing_subq = (
                select(Invoice.order_id)
                .where(Invoice.type == InvoiceType.INVOICE)
                .scalar_subquery()
            )
            stmt = (
                select(Order.id)
                .where(Order.status.in_(_PAID_ORDER_STATUSES))
                .where(Order.id.not_in(existing_subq))
                .order_by(Order.created_at.asc())
                .limit(batch_size)
            )
            order_ids = list((await db.execute(stmt)).scalars().all())

            for order_id in order_ids:
                # Lock-free dedupe: the idempotency-key lookup inside
                # create_draft_for_order is the single source of truth.
                _invoice, was_created = await invoice_service.create_draft_for_order(
                    db, order_id=order_id
                )
                if was_created:
                    created += 1
                else:
                    skipped += 1

    return {
        "status": "success",
        "scanned": len(order_ids),
        "created": created,
        "skipped": skipped,
        "remaining_hint": len(order_ids) == batch_size,
    }


@celery_app.task(name="app.modules.invoicing.application.tasks.backfill_invoices_for_paid_orders")
def backfill_invoices_for_paid_orders(batch_size: int = _BATCH_LIMIT) -> dict[str, Any]:
    """Backfill draft invoices for historical paid orders (one batch per run)."""
    return asyncio.run(_backfill_batch_async(batch_size=batch_size))
