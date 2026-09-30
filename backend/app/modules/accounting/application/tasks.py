"""Celery sweeps that close the two sources with no live outbox event.

The live feed is event-driven (``application/events.py``): orders, payments and
refunds publish outbox messages and the worker posts their journal entries.
Two sources do **not** publish outbox events today — wallet withdrawals and
vendor settlements — and the additive-only rule forbids editing those modules
to add one. They are covered by the sweep below instead, which reads their
committed rows and posts entries idempotently (the same
``(source_type, source_id, entry_type)`` uniqueness that makes outbox
redelivery safe also makes a repeated sweep safe).

``backfill_order_entries`` fills the historical gap: orders and payments that
pre-date the feed get their entries in batches.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

import structlog
from sqlalchemy import select

from app.core.database.session import async_session_factory
from app.modules.accounting.application import journal_service
from app.modules.accounting.application.posting_rules import (
    settlement_payment_lines,
    wallet_withdrawal_lines,
)
from app.modules.accounting.domain.models import JournalEntryStatus, JournalSourceType
from app.modules.wallet.domain.models import WalletTransaction, WalletTransactionType
from app.worker.celery_app import celery_app

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_BATCH_LIMIT = 200


async def _sweep_wallet_withdrawals_async(*, batch_size: int = _BATCH_LIMIT) -> dict[str, Any]:
    """Post entries for wallet withdrawals that have none yet."""
    posted = 0
    skipped = 0

    async with async_session_factory() as db:
        stmt = (
            select(WalletTransaction)
            .where(WalletTransaction.type == WalletTransactionType.WITHDRAWAL)
            .order_by(WalletTransaction.created_at.asc())
            .limit(batch_size)
        )
        withdrawals = list((await db.execute(stmt)).scalars().all())

        for tx in withdrawals:
            existing = await journal_service.find_entry_by_source(
                db,
                source_type=JournalSourceType.WALLET,
                source_id=str(tx.id),
                entry_type="withdrawal",
            )
            if existing is not None:
                skipped += 1
                continue
            description = tx.description or f"برداشت از کیف پول (تراکنش {tx.id})"
            await journal_service.create_entry(
                db,
                source_type=JournalSourceType.WALLET,
                source_id=str(tx.id),
                entry_type="withdrawal",
                description=description,
                line_specs=wallet_withdrawal_lines(
                    amount_rial=int(tx.amount or 0), description=description
                ),
                entry_date=tx.created_at,
                status=JournalEntryStatus.POSTED,
            )
            posted += 1

        await db.commit()

    return {"status": "success", "scanned": len(withdrawals), "posted": posted, "skipped": skipped}


async def _sweep_paid_settlements_async(*, batch_size: int = _BATCH_LIMIT) -> dict[str, Any]:
    """Post entries for paid vendor settlements that have none yet."""
    from app.modules.vendors.domain.models import VendorSettlement, SettlementStatus

    posted = 0
    skipped = 0

    async with async_session_factory() as db:
        stmt = (
            select(VendorSettlement)
            .where(VendorSettlement.status == SettlementStatus.PAID)
            .order_by(VendorSettlement.created_at.asc())
            .limit(batch_size)
        )
        settlements = list((await db.execute(stmt)).scalars().all())

        for settlement in settlements:
            existing = await journal_service.find_entry_by_source(
                db,
                source_type=JournalSourceType.SETTLEMENT,
                source_id=str(settlement.id),
                entry_type="settlement",
            )
            if existing is not None:
                skipped += 1
                continue
            amount = int(settlement.amount or 0)
            if amount <= 0:
                skipped += 1
                continue
            description = f"تسویه با فروشنده (سند {settlement.id})"
            await journal_service.create_entry(
                db,
                source_type=JournalSourceType.SETTLEMENT,
                source_id=str(settlement.id),
                entry_type="settlement",
                description=description,
                line_specs=settlement_payment_lines(amount_rial=amount, description=description),
                entry_date=settlement.paid_at or settlement.created_at,
                status=JournalEntryStatus.POSTED,
            )
            posted += 1

        await db.commit()

    return {
        "status": "success",
        "scanned": len(settlements),
        "posted": posted,
        "skipped": skipped,
    }


async def _backfill_orders_async(*, batch_size: int = _BATCH_LIMIT) -> dict[str, Any]:
    """Post revenue entries for orders that pre-date the feed (one batch).

    Selection is anti-joined against existing ``order``-sourced entries, and
    ``create_entry`` dedupes on the same key, so overlapping runs and reruns
    cannot double-post.
    """
    from app.modules.accounting.application import events as accounting_events
    from app.modules.accounting.domain.models import JournalEntry
    from app.modules.orders.domain.models import Order, OrderStatus

    paid_statuses = (
        OrderStatus.CONFIRMED,
        OrderStatus.PROCESSING,
        OrderStatus.PACKING,
        OrderStatus.SHIPPED,
        OrderStatus.DELIVERED,
        OrderStatus.COMPLETED,
        OrderStatus.PARTIALLY_REFUNDED,
    )

    posted = 0
    skipped = 0

    async with async_session_factory() as db:
        covered_subq = (
            select(JournalEntry.source_id)
            .where(JournalEntry.source_type == JournalSourceType.ORDER)
            .scalar_subquery()
        )
        stmt = (
            select(Order.id)
            .where(Order.status.in_(paid_statuses))
            .where(Order.id.not_in(covered_subq))
            .order_by(Order.created_at.asc())
            .limit(batch_size)
        )
        order_ids = list((await db.execute(stmt)).scalars().all())

        for order_id in order_ids:
            result = await accounting_events.handle_accounting_event(
                db,
                event_type="OrderCreated",
                payload={"order_id": str(order_id)},
                message_id=f"backfill:{order_id}",
            )
            if result and result.get("status") == "posted":
                posted += 1
            else:
                skipped += 1

        await db.commit()

    return {
        "status": "success",
        "scanned": len(order_ids),
        "posted": posted,
        "skipped": skipped,
        "remaining_hint": len(order_ids) == batch_size,
    }


@celery_app.task(name="app.modules.accounting.application.tasks.sweep_wallet_withdrawals")
def sweep_wallet_withdrawals(batch_size: int = _BATCH_LIMIT) -> dict[str, Any]:
    """Post journal entries for wallet withdrawals (idempotent batch)."""
    return asyncio.run(_sweep_wallet_withdrawals_async(batch_size=batch_size))


@celery_app.task(name="app.modules.accounting.application.tasks.sweep_paid_settlements")
def sweep_paid_settlements(batch_size: int = _BATCH_LIMIT) -> dict[str, Any]:
    """Post journal entries for paid vendor settlements (idempotent batch)."""
    return asyncio.run(_sweep_paid_settlements_async(batch_size=batch_size))


@celery_app.task(name="app.modules.accounting.application.tasks.backfill_order_entries")
def backfill_order_entries(batch_size: int = _BATCH_LIMIT) -> dict[str, Any]:
    """Backfill revenue entries for historical paid orders (one batch per run)."""
    return asyncio.run(_backfill_orders_async(batch_size=batch_size))
