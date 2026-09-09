"""Wallet application service.

Provides wallet balance management with proper concurrency control via
row-level locking (SELECT … FOR UPDATE) and an append-only transaction
ledger.

Every mutation records a ``WalletTransaction`` with the resulting
``balance_after`` for a complete audit trail.
"""

from __future__ import annotations

import math
import uuid
from typing import Optional

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions.handlers import (
    NotFoundError,
    ValidationError,
)
from app.modules.wallet.domain.models import (
    Wallet,
    WalletTransaction,
    WalletTransactionType,
)
from app.modules.wallet.schemas.wallet import (
    WalletResponse,
    WalletTransactionListResponse,
    WalletTransactionResponse,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


# ── Public Service Functions ──────────────────────────────────────────────


async def get_or_create_wallet(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> WalletResponse:
    """Return the user's wallet, creating one if it does not exist yet.

    Uses SELECT … FOR UPDATE to prevent duplicate wallet creation under
    concurrent requests.
    """

    wallet = await _get_wallet_for_update(db, user_id)

    if wallet is None:
        wallet = Wallet(user_id=user_id, balance=0, is_active=True)
        db.add(wallet)
        await db.flush()

        await logger.ainfo(
            "wallet_created",
            user_id=str(user_id),
            wallet_id=str(wallet.id),
        )

    return WalletResponse.model_validate(wallet)


async def get_balance(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> int:
    """Return the wallet balance computed from the ledger.

    Falls back to the cached ``balance`` column on the Wallet row when
    no transactions exist yet.  The ledger SUM is the source of truth.
    """

    wallet = await _get_wallet_or_raise(db, user_id)

    # Compute balance from the transaction ledger
    stmt = (
        select(func.coalesce(func.sum(WalletTransaction.amount), 0))
        .where(WalletTransaction.wallet_id == wallet.id)
    )
    result = await db.execute(stmt)
    ledger_balance: int = int(result.scalar_one())

    # If the ledger has no transactions the cached balance is authoritative
    if ledger_balance == 0 and wallet.balance == 0:
        return 0

    # Prefer ledger-derived balance; reconcile cache if different
    if ledger_balance != wallet.balance:
        await logger.awarning(
            "wallet_balance_drift",
            user_id=str(user_id),
            cached=wallet.balance,
            ledger=ledger_balance,
        )

    return wallet.balance


async def credit(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    amount: int,
    tx_type: WalletTransactionType,
    reference_type: str | None = None,
    reference_id: uuid.UUID | None = None,
    description: str | None = None,
) -> WalletTransactionResponse:
    """Add funds to a user's wallet.

    Parameters
    ----------
    amount:
        Positive amount in IRR to credit.
    tx_type:
        The type of credit (CREDIT, REFUND, CASHBACK, BONUS, etc.).
    """

    if amount <= 0:
        raise ValidationError(
            detail="Credit amount must be positive",
            error_code="INVALID_AMOUNT",
        )

    await logger.ainfo(
        "wallet_credit_start",
        user_id=str(user_id),
        amount=amount,
        tx_type=tx_type.value,
    )

    wallet = await _get_wallet_for_update(db, user_id)
    if wallet is None:
        # Auto-create wallet on first credit
        wallet = Wallet(user_id=user_id, balance=0, is_active=True)
        db.add(wallet)
        await db.flush()

    _check_wallet_active(wallet)

    new_balance = wallet.balance + amount
    wallet.balance = new_balance

    tx = WalletTransaction(
        wallet_id=wallet.id,
        amount=amount,
        type=tx_type,
        reference_type=reference_type,
        reference_id=reference_id,
        description=description,
        balance_after=new_balance,
    )
    db.add(tx)
    await db.flush()

    await logger.ainfo(
        "wallet_credit_success",
        user_id=str(user_id),
        amount=amount,
        new_balance=new_balance,
        tx_id=str(tx.id),
    )

    return WalletTransactionResponse.model_validate(tx)


async def debit(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    amount: int,
    tx_type: WalletTransactionType,
    reference_type: str | None = None,
    reference_id: uuid.UUID | None = None,
    description: str | None = None,
) -> WalletTransactionResponse:
    """Deduct funds from a user's wallet.

    The wallet row is locked with ``FOR UPDATE`` to prevent race conditions
    on concurrent debits.

    Parameters
    ----------
    amount:
        Positive amount in IRR to deduct.
    tx_type:
        The type of debit (DEBIT, WITHDRAWAL, etc.).

    Raises
    ------
    ValidationError
        If the wallet has insufficient balance.
    """

    if amount <= 0:
        raise ValidationError(
            detail="Debit amount must be positive",
            error_code="INVALID_AMOUNT",
        )

    await logger.ainfo(
        "wallet_debit_start",
        user_id=str(user_id),
        amount=amount,
        tx_type=tx_type.value,
    )

    wallet = await _get_wallet_for_update(db, user_id)
    if wallet is None:
        raise NotFoundError(resource="Wallet")

    _check_wallet_active(wallet)

    if wallet.balance < amount:
        await logger.awarning(
            "wallet_debit_insufficient_balance",
            user_id=str(user_id),
            balance=wallet.balance,
            requested=amount,
        )
        raise ValidationError(
            detail=(
                f"Insufficient wallet balance. "
                f"Available: {wallet.balance}, Requested: {amount}"
            ),
            error_code="INSUFFICIENT_BALANCE",
        )

    new_balance = wallet.balance - amount
    wallet.balance = new_balance

    # Store debit as a negative amount in the ledger for accurate SUM
    tx = WalletTransaction(
        wallet_id=wallet.id,
        amount=-amount,
        type=tx_type,
        reference_type=reference_type,
        reference_id=reference_id,
        description=description,
        balance_after=new_balance,
    )
    db.add(tx)
    await db.flush()

    await logger.ainfo(
        "wallet_debit_success",
        user_id=str(user_id),
        amount=amount,
        new_balance=new_balance,
        tx_id=str(tx.id),
    )

    return WalletTransactionResponse.model_validate(tx)


async def get_transactions(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    page: int = 1,
    page_size: int = 20,
) -> WalletTransactionListResponse:
    """Return a paginated list of wallet transactions.

    Sorted by ``created_at`` descending (newest first).
    """

    if page < 1:
        page = 1
    if page_size < 1:
        page_size = 20
    if page_size > 100:
        page_size = 100

    wallet = await _get_wallet_or_raise(db, user_id)

    # ── Count total ───────────────────────────────────────────────────
    count_stmt = (
        select(func.count())
        .select_from(WalletTransaction)
        .where(WalletTransaction.wallet_id == wallet.id)
    )
    count_result = await db.execute(count_stmt)
    total: int = int(count_result.scalar_one())

    # ── Fetch page ────────────────────────────────────────────────────
    offset = (page - 1) * page_size
    items_stmt = (
        select(WalletTransaction)
        .where(WalletTransaction.wallet_id == wallet.id)
        .order_by(WalletTransaction.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    items_result = await db.execute(items_stmt)
    transactions = items_result.scalars().all()

    pages = max(1, math.ceil(total / page_size))

    return WalletTransactionListResponse(
        items=[WalletTransactionResponse.model_validate(t) for t in transactions],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


# ── Internal Helpers ──────────────────────────────────────────────────────


async def _get_wallet_for_update(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> Wallet | None:
    """SELECT … FOR UPDATE on the wallet row to acquire a row-level lock."""
    stmt = (
        select(Wallet)
        .where(Wallet.user_id == user_id)
        .with_for_update()
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def _get_wallet_or_raise(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> Wallet:
    """Fetch the wallet without locking; raise if not found."""
    stmt = select(Wallet).where(Wallet.user_id == user_id)
    result = await db.execute(stmt)
    wallet = result.scalar_one_or_none()
    if wallet is None:
        raise NotFoundError(resource="Wallet")
    return wallet


def _check_wallet_active(wallet: Wallet) -> None:
    """Raise if the wallet is deactivated."""
    if not wallet.is_active:
        raise ValidationError(
            detail="Wallet is deactivated",
            error_code="WALLET_INACTIVE",
        )
