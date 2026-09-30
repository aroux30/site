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
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import func, select

from app.core.exceptions.handlers import (
    NotFoundError,
    PaymentError,
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

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


# ── Public Service Functions ──────────────────────────────────────────────


async def get_or_create_wallet(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> WalletResponse:
    """Return the user's wallet, creating one if it does not exist yet.

    Concurrency: ``SELECT … FOR UPDATE`` cannot lock a row that does not exist
    yet, so two concurrent first-time requests would both observe "no wallet"
    and both INSERT — the loser failing on ``uq_wallets_user_id``. The insert
    is therefore an ``ON CONFLICT DO NOTHING`` upsert followed by a locked
    re-read, which makes first-time creation safe under concurrency instead of
    relying on a check-then-insert that has no row to lock.
    """

    wallet = await _get_wallet_for_update(db, user_id)
    if wallet is not None:
        return WalletResponse.model_validate(wallet)

    # Insert-or-ignore: the winner creates the row, the loser's INSERT
    # conflicts and does nothing (no exception, no duplicate).
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    stmt = (
        pg_insert(Wallet)
        .values(user_id=user_id, balance=0, is_active=True)
        .on_conflict_do_nothing(index_elements=["user_id"])
    )
    await db.execute(stmt)
    await db.flush()

    wallet = await _get_wallet_for_update(db, user_id)
    if wallet is None:  # pragma: no cover - defensive: insert then read-back
        raise NotFoundError(resource="Wallet")

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
    stmt = select(func.coalesce(func.sum(WalletTransaction.amount), 0)).where(
        WalletTransaction.wallet_id == wallet.id
    )
    result = await db.execute(stmt)
    ledger_balance: int = int(result.scalar_one())

    # If the ledger has no transactions the cached balance is authoritative
    if ledger_balance == 0 and wallet.balance == 0:
        return 0

    # The ledger SUM is the source of truth; the cached column is a mirror.
    # Re-sync the cache on drift — but only under a row lock, so a
    # reconciliation write can never clobber a concurrent credit/debit.
    if ledger_balance != wallet.balance:
        locked = await _get_wallet_for_update(db, user_id)
        if locked is not None and locked.balance != ledger_balance:
            await logger.awarning(
                "wallet_balance_drift_reconciled",
                user_id=str(user_id),
                cached=locked.balance,
                ledger=ledger_balance,
            )
            locked.balance = ledger_balance
            await db.flush()

    return ledger_balance


async def check_sufficient_balance(
    db: AsyncSession,
    user_id: uuid.UUID,
    amount: int,
) -> None:
    """Raise if the wallet cannot cover ``amount``, holding the row lock.

    Locking the wallet row (FOR UPDATE) closes the check-then-debit gap: a
    second concurrent payment waits here until the first transaction commits
    or rolls back, so both can never pass the balance check at once. The
    debit itself re-checks under the same lock.
    """
    wallet = await _get_wallet_for_update(db, user_id)
    if wallet is None:
        raise PaymentError(
            detail="Wallet not found for this user",
            error_code="WALLET_NOT_FOUND",
        )

    stmt = select(func.coalesce(func.sum(WalletTransaction.amount), 0)).where(
        WalletTransaction.wallet_id == wallet.id
    )
    result = await db.execute(stmt)
    ledger_balance: int = int(result.scalar_one())

    if ledger_balance < amount:
        raise PaymentError(
            detail="Insufficient wallet balance for this payment",
            error_code="INSUFFICIENT_WALLET_BALANCE",
        )


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
        # Auto-create on first credit. Insert-or-ignore rather than
        # check-then-insert: FOR UPDATE cannot lock a missing row, so two
        # concurrent first credits would otherwise collide on
        # uq_wallets_user_id.
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        await db.execute(
            pg_insert(Wallet)
            .values(user_id=user_id, balance=0, is_active=True)
            .on_conflict_do_nothing(index_elements=["user_id"])
        )
        await db.flush()
        wallet = await _get_wallet_for_update(db, user_id)
        if wallet is None:  # pragma: no cover - defensive
            raise NotFoundError(resource="Wallet")

    _check_wallet_active(wallet)

    # Derive the new balance from the LEDGER, not the cached column, so a
    # pre-existing drift cannot be compounded into a credit (which would
    # mint money out of an inconsistency). The row is locked (FOR UPDATE),
    # so the SUM below cannot race a concurrent mutation of this wallet.
    ledger_balance = int(
        await db.scalar(
            select(func.coalesce(func.sum(WalletTransaction.amount), 0)).where(
                WalletTransaction.wallet_id == wallet.id
            )
        )
    )
    if ledger_balance != wallet.balance:
        await logger.awarning(
            "wallet_balance_drift_detected_on_credit",
            user_id=str(user_id),
            cached=wallet.balance,
            ledger=ledger_balance,
        )

    new_balance = ledger_balance + amount
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

    # Sufficiency is decided from the LEDGER SUM, not the cached column.
    # The ledger is the single source of financial truth; the cached
    # ``balance`` is only a hot-path mirror. If the two ever disagree, a
    # cached value that drifted high would let a debit overspend real money,
    # and one that drifted low would reject a legitimate debit — so the
    # authority must be the same here as in ``check_sufficient_balance``.
    # The wallet row is already locked (FOR UPDATE), so this read cannot race
    # a concurrent credit/debit on the same wallet.
    ledger_balance = int(
        await db.scalar(
            select(func.coalesce(func.sum(WalletTransaction.amount), 0)).where(
                WalletTransaction.wallet_id == wallet.id
            )
        )
    )
    if ledger_balance != wallet.balance:
        await logger.awarning(
            "wallet_balance_drift_detected_on_debit",
            user_id=str(user_id),
            cached=wallet.balance,
            ledger=ledger_balance,
        )

    if ledger_balance < amount:
        await logger.awarning(
            "wallet_debit_insufficient_balance",
            user_id=str(user_id),
            balance=ledger_balance,
            cached_balance=wallet.balance,
            requested=amount,
        )
        raise ValidationError(
            detail=(
                f"Insufficient wallet balance. Available: {ledger_balance}, Requested: {amount}"
            ),
            error_code="INSUFFICIENT_BALANCE",
        )

    new_balance = ledger_balance - amount
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


# ── Double-Entry Journal (ERP Phase 2) ────────────────────────────────────
#
# Every financial event produces a debit+credit pair that balances to zero.
# The two system wallets below are single users whose wallets act as the
# system-of-record accounts (pattern: Odoo journal + Akaunting double entry).
# Each WalletTransaction already stores a signed amount, so the balance
# invariant is: debit_tx.amount + credit_tx.amount == 0, asserted before
# flush — never after.

SYSTEM_USER_PLATFORM_REVENUE = uuid.UUID("00000000-0000-0000-0000-000000000001")
SYSTEM_USER_ESCROW = uuid.UUID("00000000-0000-0000-0000-000000000002")

_JOURNAL_REFERENCE_TYPE = "journal_entry"


async def _get_or_create_system_wallet(db: AsyncSession, user_id: uuid.UUID) -> Wallet:
    """Return the locked system wallet row, creating it idempotently.

    Same insert-or-ignore + FOR UPDATE pattern as ``credit``: a missing row
    cannot be locked, so two concurrent first calls collide on
    uq_wallets_user_id unless we on_conflict_do_nothing first.
    """
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    await db.execute(
        pg_insert(Wallet)
        .values(user_id=user_id, balance=0, is_active=True)
        .on_conflict_do_nothing(index_elements=["user_id"])
    )
    await db.flush()
    wallet = await _get_wallet_for_update(db, user_id)
    if wallet is None:  # pragma: no cover - defensive
        raise NotFoundError(resource="Wallet")
    return wallet


async def record_journal_entry(
    db: AsyncSession,
    *,
    debit_user_id: uuid.UUID,
    credit_user_id: uuid.UUID,
    amount: int,
    description: str,
    reference_type: str | None = None,
    reference_id: uuid.UUID | None = None,
) -> tuple[uuid.UUID, uuid.UUID]:
    """Write a balanced debit+credit pair across two wallets, atomically.

    Both sides share a fresh ``journal_entry_id`` (the same UUID for both
    rows) so the pair is provably linked. The zero-balance invariant is
    asserted before flush: debit_tx.amount + credit_tx.amount == 0.

    The two wallets are locked in a deterministic order (ascending user_id)
    so two concurrent transfers A→B and B→A cannot deadlock. Amounts are
    positive IRR integers only (BigInteger); a debit rows stores ``-amount``
    and the credit row stores ``+amount`` so the ledger SUM stays correct.
    """
    if amount <= 0:
        raise ValidationError(
            detail="Journal amount must be a positive integer (IRR)",
            error_code="INVALID_AMOUNT",
        )
    if debit_user_id == credit_user_id:
        raise ValidationError(
            detail="Cannot journal between the same wallet",
            error_code="INVALID_JOURNAL_PAIR",
        )

    journal_entry_id = uuid.uuid4()

    # Lock both wallets in ascending user_id order to prevent deadlock.
    first, second = sorted([debit_user_id, credit_user_id], key=lambda u: str(u))
    for uid in (first, second):
        await _get_or_create_system_wallet(db, uid)

    debit_wallet = await _get_wallet_for_update(db, debit_user_id)
    credit_wallet = await _get_wallet_for_update(db, credit_user_id)
    if debit_wallet is None or credit_wallet is None:  # pragma: no cover
        raise NotFoundError(resource="Wallet")
    _check_wallet_active(debit_wallet)
    _check_wallet_active(credit_wallet)

    # Ledger SUM is the source of truth (same rule as credit/debit).
    debit_ledger = int(
        await db.scalar(
            select(func.coalesce(func.sum(WalletTransaction.amount), 0)).where(
                WalletTransaction.wallet_id == debit_wallet.id
            )
        )
    )
    credit_ledger = int(
        await db.scalar(
            select(func.coalesce(func.sum(WalletTransaction.amount), 0)).where(
                WalletTransaction.wallet_id == credit_wallet.id
            )
        )
    )

    if debit_ledger < amount:
        raise ValidationError(
            detail=(
                f"Insufficient balance for journal entry. "
                f"Available: {debit_ledger}, Requested: {amount}"
            ),
            error_code="INSUFFICIENT_BALANCE",
        )

    debit_new = debit_ledger - amount
    credit_new = credit_ledger + amount
    debit_wallet.balance = debit_new
    credit_wallet.balance = credit_new

    # type uses the two enum members that exist (DEBIT/CREDIT), matching
    # debit()/credit() semantics — the pair link is the shared
    # journal_entry_id + reference_type, not a TRANSFER enum member
    # (which does not exist and would need a DB migration).
    debit_tx = WalletTransaction(
        wallet_id=debit_wallet.id,
        amount=-amount,
        type=WalletTransactionType.DEBIT,
        reference_type=_JOURNAL_REFERENCE_TYPE,
        reference_id=journal_entry_id,
        description=description,
        balance_after=debit_new,
    )
    credit_tx = WalletTransaction(
        wallet_id=credit_wallet.id,
        amount=amount,
        type=WalletTransactionType.CREDIT,
        reference_type=_JOURNAL_REFERENCE_TYPE,
        reference_id=journal_entry_id,
        description=description,
        balance_after=credit_new,
    )

    # Zero-balance invariant — enforced in code BEFORE the rows flush.
    assert debit_tx.amount + credit_tx.amount == 0, (
        f"Journal imbalance: {debit_tx.amount} + {credit_tx.amount} != 0"
    )

    db.add(debit_tx)
    db.add(credit_tx)
    await db.flush()

    await logger.ainfo(
        "wallet_journal_entry_recorded",
        journal_entry_id=str(journal_entry_id),
        debit_user_id=str(debit_user_id),
        credit_user_id=str(credit_user_id),
        amount=amount,
        reference_type=reference_type,
        reference_id=str(reference_id) if reference_id else None,
    )
    return journal_entry_id, debit_tx.id


# ── Internal Helpers ──────────────────────────────────────────────────────


async def _get_wallet_for_update(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> Wallet | None:
    """SELECT … FOR UPDATE on the wallet row to acquire a row-level lock."""
    stmt = select(Wallet).where(Wallet.user_id == user_id).with_for_update()
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
