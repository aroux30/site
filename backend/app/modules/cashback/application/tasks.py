"""Cashback background Celery tasks.

Processes pending cashback awards for completed orders and credits them
to the user's digital wallet.
"""

from __future__ import annotations

import asyncio
from typing import Any

import structlog
from sqlalchemy import select

from app.core.database.session import async_session_factory
from app.modules.cashback.application.cashback_service import CashbackService
from app.modules.cashback.domain.models import (
    CashbackTransaction,
    CashbackTransactionStatus,
)
from app.modules.orders.domain.models import Order, OrderStatus
from app.modules.wallet.application import wallet_service
from app.modules.wallet.domain.models import WalletTransactionType
from app.worker.celery_app import celery_app

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


async def _process_pending_cashback_async() -> dict[str, Any]:
    """Async execution logic for processing pending cashback.

    1. Checks eligible completed orders without cashback transactions yet,
       calculating cashback awards according to active cashback rules.
    2. Identifies all pending cashback transactions for completed orders,
       issues wallet credit, and marks transactions as CREDITED.
    """
    credited_count = 0
    total_amount = 0

    async with async_session_factory() as db:
        try:
            # 1. Discover completed orders that have not yet had cashback calculated
            existing_tx_subquery = select(CashbackTransaction.order_id).distinct()
            orders_stmt = (
                select(Order)
                .where(
                    Order.status.in_([OrderStatus.COMPLETED, OrderStatus.DELIVERED]),
                    Order.id.not_in(existing_tx_subquery),
                )
                .limit(100)
            )
            orders_res = await db.execute(orders_stmt)
            unprocessed_orders = list(orders_res.scalars().all())

            for order in unprocessed_orders:
                await CashbackService.calculate_cashback(
                    db,
                    user_id=order.user_id,
                    order_id=order.id,
                    order_total=order.total,
                    payment_method=order.payment_method if hasattr(order, "payment_method") else None,
                )

            # 2. Process all pending cashback transactions where the order is completed
            pending_stmt = (
                select(CashbackTransaction, Order)
                .join(Order, CashbackTransaction.order_id == Order.id)
                .where(CashbackTransaction.status == CashbackTransactionStatus.PENDING)
                .with_for_update(of=CashbackTransaction)
            )
            pending_res = await db.execute(pending_stmt)
            pending_pairs = list(pending_res.all())

            for txn, order in pending_pairs:
                if order.status in (OrderStatus.COMPLETED, OrderStatus.DELIVERED):
                    # Credit wallet
                    await wallet_service.credit(
                        db,
                        user_id=txn.user_id,
                        amount=txn.amount,
                        tx_type=WalletTransactionType.CASHBACK,
                        reference_type="cashback_transaction",
                        reference_id=txn.id,
                        description=f"Cashback reward for order {order.order_number}",
                    )
                    txn.status = CashbackTransactionStatus.CREDITED
                    credited_count += 1
                    total_amount += txn.amount
                elif order.status in (OrderStatus.CANCELED, OrderStatus.REFUNDED):
                    # Expire cashback for cancelled/refunded orders
                    txn.status = CashbackTransactionStatus.EXPIRED

            await db.commit()
            await logger.ainfo(
                "pending_cashback_processed",
                credited_count=credited_count,
                total_amount=total_amount,
            )
        except Exception:
            await db.rollback()
            await logger.aexception("process_pending_cashback_failed")
            raise

    return {
        "status": "success",
        "transactions_credited": credited_count,
        "total_amount_credited": total_amount,
    }


@celery_app.task(name="app.modules.cashback.application.tasks.process_pending_cashback")
def process_pending_cashback() -> dict[str, Any]:
    """Check completed orders eligible for cashback, create wallet credit,

    and mark cashback transaction 'credited'.
    """
    return asyncio.run(_process_pending_cashback_async())
