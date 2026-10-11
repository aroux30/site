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
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import func, select

from app.core.exceptions.handlers import (
    ConflictError,
    NotFoundError,
    PaymentError,
    ValidationError,
)
from app.modules.wallet.domain.models import (
    Wallet,
    WalletTransaction,
    WalletTransactionType,
    WalletTransfer,
    WalletWithdrawalRequest,
    WithdrawalStatus,
)
from app.modules.wallet.schemas.wallet import (
    WalletAdminListResponse,
    WalletResponse,
    WalletTransactionListResponse,
    WalletTransactionResponse,
    WalletTransferListResponse,
    WalletTransferResponse,
    WalletWithdrawalListResponse,
    WalletWithdrawalResponse,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


# ── Module switches ───────────────────────────────────────────────────────
#
# Each wallet capability is independently toggleable via a ``site_options``
# text row ("1"/"0"), read at request time — never cached, so an operator's
# change takes effect on the next request. This mirrors the enforced toggles
# elsewhere (registration_enabled, media_watermark_enabled). The master
# ``wallet_enabled`` gates every capability below it.
_TRUTHY = {"1", "true", "yes", "on", "فعال", "بله"}

_WALLET_SWITCH_KEYS = {
    "wallet_enabled",
    "wallet_deposit_enabled",
    "wallet_withdraw_enabled",
    "wallet_transfer_enabled",
    "wallet_admin_adjust_enabled",
}


async def _switch_enabled(db: AsyncSession, key: str, *, default: bool = True) -> bool:
    """Return whether a wallet switch is on, reading ``site_options`` live.

    Unknown/absent keys fall back to ``default`` so a database that predates
    the seed keeps the feature available rather than silently disabling it.
    """
    from app.modules.settings.application.site_options_service import SiteOptionsService

    raw = await SiteOptionsService.get(db, key, "1" if default else "0")
    return str(raw or "").strip().lower() in _TRUTHY


async def _require_switch(db: AsyncSession, key: str) -> None:
    """Raise a Persian 403-equivalent if a wallet switch is off."""
    if not await _switch_enabled(db, key):
        raise ValidationError(
            detail="این بخش از کیف پول در حال حاضر غیرفعال است. لطفاً بعداً تلاش کنید.",
            error_code="WALLET_FEATURE_DISABLED",
        )


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
        return await _wallet_response(db, wallet)

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
    return await _wallet_response(db, wallet)


async def _wallet_response(db: AsyncSession, wallet: Wallet) -> WalletResponse:
    """Build a WalletResponse, attaching the current module switch state.

    The storefront uses ``features`` to HIDE the deposit/withdraw/transfer
    entry points when a switch is off, rather than showing a button whose only
    outcome is an error. All three read as enabled when their switch row is
    absent, so an un-migrated database keeps the full wallet.
    """
    from app.modules.wallet.schemas.wallet import WalletFeatures

    master = await _switch_enabled(db, "wallet_enabled")
    features = WalletFeatures(
        enabled=master,
        deposit=master and await _switch_enabled(db, "wallet_deposit_enabled"),
        withdraw=master and await _switch_enabled(db, "wallet_withdraw_enabled"),
        transfer=master and await _switch_enabled(db, "wallet_transfer_enabled"),
    )
    return WalletResponse.model_validate(wallet).model_copy(update={"features": features})


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
            detail="کیف پول برای این کاربر یافت نشد.",
            error_code="WALLET_NOT_FOUND",
        )

    stmt = select(func.coalesce(func.sum(WalletTransaction.amount), 0)).where(
        WalletTransaction.wallet_id == wallet.id
    )
    result = await db.execute(stmt)
    ledger_balance: int = int(result.scalar_one())

    if ledger_balance < amount:
        raise PaymentError(
            detail="موجودی کیف پول برای این پرداخت کافی نیست.",
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
            detail="مبلغ واریز باید یک عدد صحیح مثبت (ریال) باشد.",
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
            detail="مبلغ برداشت باید یک عدد صحیح مثبت (ریال) باشد.",
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
                f"موجودی کیف پول کافی نیست. موجودی قابل استفاده: {ledger_balance} ریال، "
                f"مبلغ درخواستی: {amount} ریال."
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
    debit_type: WalletTransactionType = WalletTransactionType.DEBIT,
    credit_type: WalletTransactionType = WalletTransactionType.CREDIT,
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
            detail="مبلغ سند حسابداری باید یک عدد صحیح مثبت (ریال) باشد.",
            error_code="INVALID_AMOUNT",
        )
    if debit_user_id == credit_user_id:
        raise ValidationError(
            detail="ثبت سند بین یک کیف پول با خودش امکان‌پذیر نیست.",
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
                f"موجودی برای ثبت سند کافی نیست. موجودی قابل استفاده: {debit_ledger} ریال، "
                f"مبلغ درخواستی: {amount} ریال."
            ),
            error_code="INSUFFICIENT_BALANCE",
        )

    debit_new = debit_ledger - amount
    credit_new = credit_ledger + amount
    debit_wallet.balance = debit_new
    credit_wallet.balance = credit_new

    # The pair link is the shared journal_entry_id + reference_type. Callers
    # may pass a more specific type for each leg (e.g. TRANSFER_OUT /
    # TRANSFER_IN for a P2P transfer) so the customer's history reads
    # correctly; the default keeps generic DEBIT/CREDIT semantics.
    debit_tx = WalletTransaction(
        wallet_id=debit_wallet.id,
        amount=-amount,
        type=debit_type,
        reference_type=_JOURNAL_REFERENCE_TYPE,
        reference_id=journal_entry_id,
        description=description,
        balance_after=debit_new,
    )
    credit_tx = WalletTransaction(
        wallet_id=credit_wallet.id,
        amount=amount,
        type=credit_type,
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


# ── Peer-to-peer transfers ────────────────────────────────────────────────

_TRANSFER_REFERENCE_TYPE = "p2p_transfer"


async def _resolve_recipient(db: AsyncSession, phone: str) -> uuid.UUID:
    """Resolve a normalized phone number to an active user id."""
    from app.modules.users.domain.models import User

    stmt = select(User).where(User.phone == phone)
    user = (await db.execute(stmt)).scalar_one_or_none()
    if user is None or user.deleted_at is not None:
        raise ValidationError(
            detail="کاربری با این شماره موبایل یافت نشد.",
            error_code="RECIPIENT_NOT_FOUND",
        )
    return user.id


async def transfer(
    db: AsyncSession,
    *,
    from_user_id: uuid.UUID,
    recipient_phone: str,
    amount: int,
    note: str | None = None,
    idempotency_key: str | None = None,
) -> WalletTransferResponse:
    """Transfer funds from one customer's wallet to another's.

    The money movement is a single balanced journal entry
    (``TRANSFER_OUT`` + ``TRANSFER_IN`` sharing one ``journal_entry_id``), so
    it is atomic and the ledger stays zero-sum. Idempotency is claimed by the
    ``wallet_transfers.idempotency_key`` unique constraint *before* any money
    moves: a replay returns the original transfer and never debits twice.
    """
    await _require_switch(db, "wallet_transfer_enabled")
    await _require_switch(db, "wallet_enabled")

    if amount <= 0:
        raise ValidationError(
            detail="مبلغ انتقال باید یک عدد صحیح مثبت (ریال) باشد.",
            error_code="INVALID_AMOUNT",
        )

    # Idempotent replay: return the original transfer unchanged.
    if idempotency_key:
        existing = (
            await db.execute(
                select(WalletTransfer).where(
                    WalletTransfer.idempotency_key == idempotency_key
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            if existing.from_user_id != from_user_id:
                # A key reused by a different user must never leak another
                # user's transfer.
                raise NotFoundError(resource="WalletTransfer")
            return WalletTransferResponse.model_validate(existing)

    to_user_id = await _resolve_recipient(db, recipient_phone)
    if to_user_id == from_user_id:
        raise ValidationError(
            detail="انتقال به کیف پول خودتان امکان‌پذیر نیست.",
            error_code="SELF_TRANSFER",
        )

    # The recipient wallet must exist and be active. _get_or_create_system_wallet
    # creates a missing wallet row idempotently (a brand-new recipient has none
    # yet); the active check then rejects a deactivated wallet.
    recipient_wallet = await _get_or_create_system_wallet(db, to_user_id)
    _check_wallet_active(recipient_wallet)

    # Claim the idempotency key BEFORE moving money: insert the transfer row
    # first, so a concurrent replay collides on the unique constraint here —
    # with no money moved — instead of after the journal entry. The insert
    # runs inside a SAVEPOINT so a collision does not abort the caller's whole
    # transaction (the established pattern in cashback/gamification).
    from sqlalchemy.exc import IntegrityError

    transfer_row = WalletTransfer(
        from_user_id=from_user_id,
        to_user_id=to_user_id,
        amount=amount,
        fee=0,
        note=note,
        idempotency_key=idempotency_key,
    )
    try:
        async with db.begin_nested():
            db.add(transfer_row)
            await db.flush()
    except IntegrityError:
        if idempotency_key:
            existing = (
                await db.execute(
                    select(WalletTransfer).where(
                        WalletTransfer.idempotency_key == idempotency_key
                    )
                )
            ).scalar_one_or_none()
            if existing is not None:
                return WalletTransferResponse.model_validate(existing)
        raise

    journal_entry_id, _debit_tx_id = await record_journal_entry(
        db,
        debit_user_id=from_user_id,
        credit_user_id=to_user_id,
        amount=amount,
        description="انتقال موجودی کیف پول",
        reference_type=_TRANSFER_REFERENCE_TYPE,
        reference_id=transfer_row.id,
        debit_type=WalletTransactionType.TRANSFER_OUT,
        credit_type=WalletTransactionType.TRANSFER_IN,
    )
    transfer_row.journal_entry_id = journal_entry_id
    await db.flush()

    await _publish_wallet_event(
        db,
        event_type="WalletTransferSent",
        aggregate_id=str(transfer_row.id),
        payload={
            "user_id": str(from_user_id),
            "counterparty_user_id": str(to_user_id),
            "amount": amount,
            "transfer_id": str(transfer_row.id),
            "direction": "out",
        },
    )
    await _publish_wallet_event(
        db,
        event_type="WalletTransferReceived",
        aggregate_id=str(transfer_row.id),
        payload={
            "user_id": str(to_user_id),
            "counterparty_user_id": str(from_user_id),
            "amount": amount,
            "transfer_id": str(transfer_row.id),
            "direction": "in",
        },
    )

    await logger.ainfo(
        "wallet_transfer_completed",
        from_user_id=str(from_user_id),
        to_user_id=str(to_user_id),
        amount=amount,
        transfer_id=str(transfer_row.id),
    )
    return WalletTransferResponse.model_validate(transfer_row)


# ── Withdrawal requests (submit → hold → admin review → manual payout) ─────


async def request_withdrawal(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    amount: int,
    iban: str | None = None,
    card_number: str | None = None,
    account_holder_name: str | None = None,
    idempotency_key: str | None = None,
) -> WalletWithdrawalResponse:
    """Submit a withdrawal request and hold the funds immediately.

    The funds leave the spendable balance at submission time (a
    ``WITHDRAWAL_HOLD`` ledger debit linked via ``wallet_transaction_id``), so
    a customer cannot spend the same balance twice while an admin reviews the
    request. Rejection credits the funds back; approval + manual payout only
    advance the status.
    """
    await _require_switch(db, "wallet_withdraw_enabled")
    await _require_switch(db, "wallet_enabled")

    if amount <= 0:
        raise ValidationError(
            detail="مبلغ برداشت باید یک عدد صحیح مثبت (ریال) باشد.",
            error_code="INVALID_AMOUNT",
        )
    if not (iban or card_number):
        raise ValidationError(
            detail="وارد کردن شماره شبا یا شماره کارت مقصد الزامی است.",
            error_code="WITHDRAWAL_DESTINATION_REQUIRED",
        )

    # Idempotent replay.
    if idempotency_key:
        existing = (
            await db.execute(
                select(WalletWithdrawalRequest).where(
                    WalletWithdrawalRequest.idempotency_key == idempotency_key
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            if existing.user_id != user_id:
                raise NotFoundError(resource="WalletWithdrawalRequest")
            return WalletWithdrawalResponse.model_validate(existing)

    from sqlalchemy.exc import IntegrityError

    request_row = WalletWithdrawalRequest(
        user_id=user_id,
        amount=amount,
        status=WithdrawalStatus.PENDING_REVIEW,
        iban=iban,
        card_number=card_number,
        account_holder_name=account_holder_name,
        idempotency_key=idempotency_key,
    )
    try:
        async with db.begin_nested():
            db.add(request_row)
            await db.flush()
    except IntegrityError:
        if idempotency_key:
            existing = (
                await db.execute(
                    select(WalletWithdrawalRequest).where(
                        WalletWithdrawalRequest.idempotency_key == idempotency_key
                    )
                )
            ).scalar_one_or_none()
            if existing is not None:
                return WalletWithdrawalResponse.model_validate(existing)
        raise

    # Hold the funds. If the balance is insufficient, debit() raises and the
    # whole transaction (including this request row) rolls back — no orphan.
    hold_tx = await debit(
        db,
        user_id=user_id,
        amount=amount,
        tx_type=WalletTransactionType.WITHDRAWAL_HOLD,
        reference_type="withdrawal_hold",
        reference_id=request_row.id,
        description="بلوکه‌سازی مبلغ درخواست برداشت",
    )
    request_row.wallet_transaction_id = hold_tx.id
    await db.flush()

    await _publish_wallet_event(
        db,
        event_type="WalletWithdrawalRequested",
        aggregate_id=str(request_row.id),
        payload={
            "user_id": str(user_id),
            "amount": amount,
            "request_id": str(request_row.id),
        },
    )
    await logger.ainfo(
        "wallet_withdrawal_requested",
        user_id=str(user_id),
        amount=amount,
        request_id=str(request_row.id),
    )
    return WalletWithdrawalResponse.model_validate(request_row)


async def get_withdrawals(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    page: int = 1,
    page_size: int = 20,
) -> WalletWithdrawalListResponse:
    """Paginated list of the caller's own withdrawal requests, newest first."""
    if page < 1:
        page = 1
    if page_size < 1:
        page_size = 20
    if page_size > 100:
        page_size = 100

    total = int(
        await db.scalar(
            select(func.count())
            .select_from(WalletWithdrawalRequest)
            .where(WalletWithdrawalRequest.user_id == user_id)
        )
        or 0
    )
    rows = (
        (
            await db.execute(
                select(WalletWithdrawalRequest)
                .where(WalletWithdrawalRequest.user_id == user_id)
                .order_by(WalletWithdrawalRequest.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .scalars()
        .all()
    )
    return WalletWithdrawalListResponse(
        items=[WalletWithdrawalResponse.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
        pages=max(1, math.ceil(total / page_size)),
    )


async def review_withdrawal(
    db: AsyncSession,
    *,
    request_id: uuid.UUID,
    admin_id: uuid.UUID,
    is_approved: bool,
    admin_notes: str | None = None,
) -> WalletWithdrawalResponse:
    """Admin approve/reject of a pending withdrawal request.

    Approving only marks the request APPROVED (the money already left the
    wallet at hold time); the admin then records the out-of-band bank payout
    via :func:`mark_withdrawal_paid`. Rejecting credits the held funds back to
    the wallet with a ``WITHDRAWAL_REVERSAL`` entry.
    """
    stmt = (
        select(WalletWithdrawalRequest)
        .where(WalletWithdrawalRequest.id == request_id)
        .with_for_update()
    )
    request_row = (await db.execute(stmt)).scalar_one_or_none()
    if request_row is None:
        raise NotFoundError(resource="WalletWithdrawalRequest")

    if request_row.status != WithdrawalStatus.PENDING_REVIEW:
        raise ConflictError(
            detail=f"این درخواست قبلاً تعیین وضعیت شده است: {request_row.status.value}"
        )

    request_row.reviewed_by = admin_id
    request_row.reviewed_at = datetime.now(UTC)
    request_row.admin_notes = admin_notes

    if is_approved:
        request_row.status = WithdrawalStatus.APPROVED
        event_type = "WalletWithdrawalApproved"
    else:
        request_row.status = WithdrawalStatus.REJECTED
        # Return the held funds to the customer's wallet.
        await credit(
            db,
            user_id=request_row.user_id,
            amount=request_row.amount,
            tx_type=WalletTransactionType.WITHDRAWAL_REVERSAL,
            reference_type="withdrawal_reject",
            reference_id=request_row.id,
            description="بازگشت مبلغ درخواست برداشت ردشده",
        )
        event_type = "WalletWithdrawalRejected"

    await db.flush()
    await _publish_wallet_event(
        db,
        event_type=event_type,
        aggregate_id=str(request_row.id),
        payload={
            "user_id": str(request_row.user_id),
            "amount": request_row.amount,
            "request_id": str(request_row.id),
            "admin_notes": admin_notes,
        },
    )
    await logger.ainfo(
        "wallet_withdrawal_reviewed",
        request_id=str(request_id),
        approved=is_approved,
        admin_id=str(admin_id),
    )
    return WalletWithdrawalResponse.model_validate(request_row)


async def mark_withdrawal_paid(
    db: AsyncSession,
    *,
    request_id: uuid.UUID,
    admin_id: uuid.UUID,
    payout_reference: str,
) -> WalletWithdrawalResponse:
    """Record the manual bank payout for an APPROVED withdrawal request.

    No money moves here — the debit happened at hold time. This is purely the
    administrative record that the out-of-band transfer was made, with the
    bank reference for reconciliation.
    """
    stmt = (
        select(WalletWithdrawalRequest)
        .where(WalletWithdrawalRequest.id == request_id)
        .with_for_update()
    )
    request_row = (await db.execute(stmt)).scalar_one_or_none()
    if request_row is None:
        raise NotFoundError(resource="WalletWithdrawalRequest")

    if request_row.status != WithdrawalStatus.APPROVED:
        raise ConflictError(
            detail="فقط درخواست‌های تأییدشده را می‌توان به‌عنوان پرداخت‌شده ثبت کرد."
        )

    request_row.status = WithdrawalStatus.PAID
    request_row.payout_reference = payout_reference
    request_row.paid_at = datetime.now(UTC)
    await db.flush()

    await _publish_wallet_event(
        db,
        event_type="WalletWithdrawalPaid",
        aggregate_id=str(request_row.id),
        payload={
            "user_id": str(request_row.user_id),
            "amount": request_row.amount,
            "request_id": str(request_row.id),
            "payout_reference": payout_reference,
        },
    )
    await logger.ainfo(
        "wallet_withdrawal_paid",
        request_id=str(request_id),
        admin_id=str(admin_id),
        payout_reference=payout_reference,
    )
    return WalletWithdrawalResponse.model_validate(request_row)


async def list_withdrawals_admin(
    db: AsyncSession,
    *,
    status: WithdrawalStatus | None = None,
    page: int = 1,
    page_size: int = 20,
) -> WalletWithdrawalListResponse:
    """Admin list of withdrawal requests, optionally filtered by status."""
    if page < 1:
        page = 1
    if page_size < 1:
        page_size = 20
    if page_size > 100:
        page_size = 100

    filters = []
    if status is not None:
        filters.append(WalletWithdrawalRequest.status == status)

    total = int(
        await db.scalar(
            select(func.count()).select_from(WalletWithdrawalRequest).where(*filters)
        )
        or 0
    )
    rows = (
        (
            await db.execute(
                select(WalletWithdrawalRequest)
                .where(*filters)
                .order_by(WalletWithdrawalRequest.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .scalars()
        .all()
    )
    return WalletWithdrawalListResponse(
        items=[WalletWithdrawalResponse.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
        pages=max(1, math.ceil(total / page_size)),
    )


# ── Admin wallet surface ──────────────────────────────────────────────────


async def admin_adjust(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    amount: int,
    reason: str,
    admin_id: uuid.UUID,
) -> WalletTransactionResponse:
    """Admin credit/debit adjustment of a customer wallet.

    ``amount`` is signed: positive credits, negative debits. The adjustment is
    written as a single ``ADJUSTMENT`` ledger entry so it is indistinguishable
    in the ledger from any other movement (no balance is ever set directly).
    """
    await _require_switch(db, "wallet_admin_adjust_enabled")

    if amount == 0:
        raise ValidationError(
            detail="مبلغ اصلاح نمی‌تواند صفر باشد.",
            error_code="INVALID_AMOUNT",
        )

    if amount > 0:
        tx = await credit(
            db,
            user_id=user_id,
            amount=amount,
            tx_type=WalletTransactionType.ADJUSTMENT,
            reference_type="admin_adjustment",
            description=f"اصلاح موجودی توسط مدیر: {reason}",
        )
    else:
        tx = await debit(
            db,
            user_id=user_id,
            amount=-amount,
            tx_type=WalletTransactionType.ADJUSTMENT,
            reference_type="admin_adjustment",
            description=f"اصلاح موجودی توسط مدیر: {reason}",
        )

    await _publish_wallet_event(
        db,
        event_type="WalletAdminAdjusted",
        aggregate_id=str(user_id),
        payload={
            "user_id": str(user_id),
            "amount": amount,
            "reason": reason,
            "admin_id": str(admin_id),
        },
    )
    await logger.ainfo(
        "wallet_admin_adjusted",
        user_id=str(user_id),
        amount=amount,
        admin_id=str(admin_id),
    )
    return tx


async def admin_list_wallets(
    db: AsyncSession,
    *,
    search: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> WalletAdminListResponse:
    """Admin list of wallets, optionally filtered by the owner's phone."""
    from app.modules.users.domain.models import User

    if page < 1:
        page = 1
    if page_size < 1:
        page_size = 20
    if page_size > 100:
        page_size = 100

    stmt = select(Wallet)
    count_stmt = select(func.count()).select_from(Wallet)
    if search:
        pattern = f"%{search.strip()}%"
        stmt = stmt.join(User, User.id == Wallet.user_id).where(User.phone.ilike(pattern))
        count_stmt = count_stmt.join(User, User.id == Wallet.user_id).where(
            User.phone.ilike(pattern)
        )

    total = int(await db.scalar(count_stmt) or 0)
    rows = (
        (
            await db.execute(
                stmt.order_by(Wallet.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .scalars()
        .all()
    )
    from app.modules.wallet.schemas.wallet import WalletAdminListItem

    return WalletAdminListResponse(
        items=[WalletAdminListItem.model_validate(w) for w in rows],
        total=total,
        page=page,
        page_size=page_size,
        pages=max(1, math.ceil(total / page_size)),
    )


async def admin_list_transfers(
    db: AsyncSession,
    *,
    page: int = 1,
    page_size: int = 20,
) -> WalletTransferListResponse:
    """Admin list of peer-to-peer transfers, newest first."""
    if page < 1:
        page = 1
    if page_size < 1:
        page_size = 20
    if page_size > 100:
        page_size = 100

    total = int(await db.scalar(select(func.count()).select_from(WalletTransfer)) or 0)
    rows = (
        (
            await db.execute(
                select(WalletTransfer)
                .order_by(WalletTransfer.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .scalars()
        .all()
    )
    return WalletTransferListResponse(
        items=[WalletTransferResponse.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
        pages=max(1, math.ceil(total / page_size)),
    )


async def admin_get_ledger(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    page: int = 1,
    page_size: int = 20,
) -> WalletTransactionListResponse:
    """Admin view of any customer's wallet ledger (read-only)."""
    return await get_transactions(db, user_id=user_id, page=page, page_size=page_size)


async def get_switches(db: AsyncSession) -> dict[str, bool]:
    """Return the current wallet module switch states."""
    return {key: await _switch_enabled(db, key) for key in sorted(_WALLET_SWITCH_KEYS)}


async def set_switch(db: AsyncSession, *, key: str, enabled: bool) -> bool:
    """Set a wallet module switch. Raises if the key is not a wallet switch."""
    if key not in _WALLET_SWITCH_KEYS:
        raise ValidationError(
            detail="کلید تنظیمات کیف پول نامعتبر است.",
            error_code="UNKNOWN_WALLET_SWITCH",
        )
    from app.modules.settings.application.site_options_service import SiteOptionsService

    await SiteOptionsService.set(db, key, "1" if enabled else "0")
    await logger.ainfo("wallet_switch_changed", key=key, enabled=enabled)
    return enabled


async def _publish_wallet_event(
    db: AsyncSession,
    *,
    event_type: str,
    aggregate_id: str,
    payload: dict,
) -> None:
    """Publish a wallet event to the transactional outbox (never fatal).

    Event names are literal strings (never derived from an enum value) so the
    worker's dispatch table can match them exactly — deriving them is how the
    order notifications silently dropped ``OrderOn_hold``.
    """
    try:
        from app.shared.events.outbox_service import OutboxService

        await OutboxService.publish(
            db,
            event_type=event_type,
            aggregate_type="wallet",
            aggregate_id=aggregate_id,
            payload=payload,
        )
    except Exception as exc:
        await logger.awarning(
            "wallet_event_publish_skipped", event_type=event_type, error=str(exc)
        )


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
            detail="کیف پول غیرفعال است.",
            error_code="WALLET_INACTIVE",
        )
