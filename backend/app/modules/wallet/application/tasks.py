"""Wallet background Celery tasks."""

from __future__ import annotations

import asyncio
from typing import Any

import structlog
from sqlalchemy import func, select

from app.core.database.session import async_session_factory
from app.modules.wallet.domain.models import Wallet, WalletTransaction
from app.worker.celery_app import celery_app

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


async def _reconcile_wallet_balances_async() -> dict[str, Any]:
    """Re-sync every wallet's cached ``balance`` column with its ledger SUM.

    The ledger is the source of truth; the cached column is a hot-path
    mirror.  Drift is corrected here and logged so it is always observable.
    """
    reconciled = 0
    drifted = 0

    async with async_session_factory() as db:
        try:
            wallet_ids = (await db.scalars(select(Wallet.id))).all()
            for wallet_id in wallet_ids:
                ledger_sum = int(
                    await db.scalar(
                        select(func.coalesce(func.sum(WalletTransaction.amount), 0)).where(
                            WalletTransaction.wallet_id == wallet_id
                        )
                    )
                )
                wallet = await db.get(Wallet, wallet_id)
                if wallet is None:
                    continue
                if ledger_sum is None:
                    ledger_sum = 0
                if wallet.balance != ledger_sum:
                    await logger.awarning(
                        "wallet_reconcile_drift_fixed",
                        wallet_id=str(wallet_id),
                        cached=wallet.balance,
                        ledger=ledger_sum,
                    )
                    wallet.balance = ledger_sum
                    drifted += 1
                reconciled += 1
            await db.commit()
        except Exception as exc:
            await db.rollback()
            await logger.aerror("wallet_reconcile_failed", error=str(exc))
            return {"status": "error", "message": str(exc)}

    if drifted:
        await logger.awarning("wallet_reconcile_drifted_wallets", count=drifted)
    return {"status": "success", "reconciled": reconciled, "drifted": drifted}


@celery_app.task(name="app.modules.wallet.application.tasks.reconcile_wallet_balances")
def reconcile_wallet_balances() -> dict[str, Any]:
    """Celery task entrypoint: nightly wallet ledger/cache reconciliation."""
    return asyncio.run(_reconcile_wallet_balances_async())
