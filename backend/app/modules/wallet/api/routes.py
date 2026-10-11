"""Wallet module API routes.

Customer surface under ``/api/v1/wallet`` and the admin surface under
``/api/v1/admin/wallet`` (``admin_router``, auto-mounted by ``app.main``).
"""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.settings import get_settings
from app.core.database.session import get_db
from app.core.security.dependencies import RequirePermissions, get_current_user_id
from app.core.security.rate_limiter import limiter
from app.modules.payments.schemas.payment import PaymentResponse
from app.modules.wallet.application import wallet_service
from app.modules.wallet.domain.models import WalletTransactionType, WithdrawalStatus
from app.modules.wallet.schemas.wallet import (
    WalletAdminAdjustRequest,
    WalletAdminListResponse,
    WalletDepositRequest,
    WalletResponse,
    WalletSwitchResponse,
    WalletTopupRequest,
    WalletTransactionListResponse,
    WalletTransactionResponse,
    WalletTransferListResponse,
    WalletTransferRequest,
    WalletTransferResponse,
    WalletWithdrawalCreateRequest,
    WalletWithdrawalListResponse,
    WalletWithdrawalResponse,
    WithdrawalMarkPaidRequest,
    WithdrawalReviewRequest,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

router = APIRouter()

# Admin router mounted at /api/v1/admin/wallet via main.py _include_routers,
# which includes an admin_router at the bare API prefix — so the prefix must be
# declared here (same convention as payments' admin_router).
admin_router = APIRouter(prefix="/admin/wallet", tags=["admin-wallet"])


# ── Get Wallet ────────────────────────────────────────────────────────────


@router.get(
    "",
    response_model=WalletResponse,
    summary="Get current user's wallet",
)
async def get_wallet(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> WalletResponse:
    """Return the authenticated user's wallet, creating it if necessary."""
    return await wallet_service.get_or_create_wallet(db, user_id)


# ── List Transactions ─────────────────────────────────────────────────────


@router.get(
    "/transactions",
    response_model=WalletTransactionListResponse,
    summary="List wallet transactions",
)
async def list_transactions(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> WalletTransactionListResponse:
    """Return a paginated list of the user's wallet transactions.

    Results are sorted by date, newest first.
    """
    return await wallet_service.get_transactions(
        db,
        user_id=user_id,
        page=page,
        page_size=page_size,
    )


# ── Deposit ───────────────────────────────────────────────────────────────


@router.post(
    "/deposit",
    response_model=WalletTransactionResponse,
    status_code=201,
    summary="Deposit funds into wallet",
)
@limiter.limit("10/minute")
async def deposit(
    request: Request,
    body: WalletDepositRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> WalletTransactionResponse:
    """Credit the user's wallet with the specified amount.

    Fail-closed in production: wallet top-ups must go through a completed
    payment (gateway → verification → credit), never a direct credit call.
    The unauthenticated-credit path is kept for development and testing only.
    """
    if get_settings().ENVIRONMENT == "production":
        logger.error(
            "wallet_deposit_blocked_in_production",
            user_id=str(user_id),
            amount=body.amount,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "شارژ مستقیم کیف پول غیرفعال است. لطفاً از طریق درگاه پرداخت "
                "آنلاین کیف پول خود را شارژ کنید."
            ),
        )
    await wallet_service._require_switch(db, "wallet_deposit_enabled")
    await wallet_service._require_switch(db, "wallet_enabled")
    return await wallet_service.credit(
        db,
        user_id=user_id,
        amount=body.amount,
        tx_type=WalletTransactionType.CREDIT,
        reference_type="deposit",
        description="شارژ کیف پول",
    )


# ── Top-up via payment gateway (production path) ─────────────────────────


@router.post(
    "/topup",
    response_model=PaymentResponse,
    status_code=201,
    summary="Start a wallet top-up payment through an online gateway",
)
@limiter.limit("10/minute")
async def start_topup(
    request: Request,
    body: WalletTopupRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> PaymentResponse:
    """Create a gateway-backed wallet top-up payment.

    The returned ``gateway_url`` must be opened by the user; the wallet is
    credited only after the gateway verifies the payment.
    """
    from app.modules.payments.application import payment_service

    await wallet_service._require_switch(db, "wallet_deposit_enabled")
    await wallet_service._require_switch(db, "wallet_enabled")
    return await payment_service.create_wallet_topup(
        db,
        user_id=user_id,
        provider=body.provider,
        amount=body.amount,
        idempotency_key=body.idempotency_key,
    )


# ── Transfer (P2P) ────────────────────────────────────────────────────────


@router.post(
    "/transfer",
    response_model=WalletTransferResponse,
    status_code=201,
    summary="Transfer funds to another customer's wallet",
)
@limiter.limit("10/minute")
async def transfer(
    request: Request,
    body: WalletTransferRequest,
    idempotency_key: str | None = Header(
        None,
        alias="Idempotency-Key",
        max_length=255,
        description="Client-generated idempotency key to prevent duplicate transfers",
    ),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> WalletTransferResponse:
    """Transfer funds from the caller's wallet to another customer.

    The recipient is identified by phone number. The transfer is a single
    balanced journal entry (atomic, zero-sum); a repeated request with the same
    ``Idempotency-Key`` returns the original transfer without moving money again.
    """
    return await wallet_service.transfer(
        db,
        from_user_id=user_id,
        recipient_phone=body.recipient_phone,
        amount=body.amount,
        note=body.note,
        idempotency_key=idempotency_key or body.idempotency_key,
    )


# ── Withdraw (request → hold → admin review → manual payout) ──────────────


@router.post(
    "/withdrawals",
    response_model=WalletWithdrawalResponse,
    status_code=201,
    summary="Submit a withdrawal request (funds are held immediately)",
)
@limiter.limit("10/minute")
async def create_withdrawal(
    request: Request,
    body: WalletWithdrawalCreateRequest,
    idempotency_key: str | None = Header(
        None,
        alias="Idempotency-Key",
        max_length=255,
        description="Client-generated idempotency key to prevent duplicate requests",
    ),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> WalletWithdrawalResponse:
    """Submit a withdrawal request.

    The requested amount is deducted from the wallet immediately (held) so it
    cannot be spent twice while an admin reviews the request. On rejection the
    amount is returned to the wallet; on approval the admin records the manual
    bank payout.
    """
    return await wallet_service.request_withdrawal(
        db,
        user_id=user_id,
        amount=body.amount,
        iban=body.iban,
        card_number=body.card_number,
        account_holder_name=body.account_holder_name,
        idempotency_key=idempotency_key or body.idempotency_key,
    )


@router.get(
    "/withdrawals",
    response_model=WalletWithdrawalListResponse,
    summary="List the caller's withdrawal requests",
)
async def list_withdrawals(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> WalletWithdrawalListResponse:
    """Return the caller's own withdrawal requests, newest first."""
    return await wallet_service.get_withdrawals(
        db, user_id=user_id, page=page, page_size=page_size
    )


@router.post(
    "/withdraw",
    response_model=WalletWithdrawalResponse,
    status_code=201,
    summary="Withdraw funds from wallet (alias of /withdrawals)",
    include_in_schema=False,
)
@limiter.limit("10/minute")
async def withdraw(
    request: Request,
    body: WalletWithdrawalCreateRequest,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key", max_length=255),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> WalletWithdrawalResponse:
    """Backward-compatible alias: routes to the reviewable withdrawal flow.

    Previously this endpoint debited the wallet and returned a ledger entry
    with no review. It now creates a withdrawal request (funds held), so an
    older caller keeps working while gaining the review + manual-payout flow.
    """
    return await wallet_service.request_withdrawal(
        db,
        user_id=user_id,
        amount=body.amount,
        iban=body.iban,
        card_number=body.card_number,
        account_holder_name=body.account_holder_name,
        idempotency_key=idempotency_key or body.idempotency_key,
    )


# ── Admin surface ─────────────────────────────────────────────────────────
#
# Mounted at /api/v1/admin/wallet by app.main (admin_router). Every route is
# guarded by a wallet permission; the actor is re-bound as source="admin" for
# the audit trail by RequirePermissions.

_require_wallet_read = Depends(RequirePermissions("wallet:read"))
_require_wallet_manage = Depends(RequirePermissions("wallet:manage"))


@admin_router.get(
    "/settings",
    summary="Read the wallet module switches (admin)",
    dependencies=[_require_wallet_read],
)
async def get_wallet_settings(
    db: AsyncSession = Depends(get_db),
) -> dict[str, bool]:
    """Return the current wallet module switch states.

    Returned as a plain ``{key: bool}`` map (no response_model — a Pydantic
    model would be inferred from the annotation and a bare ``dict[str, bool]``
    is exactly what the admin page reads).
    """
    return await wallet_service.get_switches(db)


@admin_router.put(
    "/settings/{key}",
    response_model=WalletSwitchResponse,
    summary="Set a wallet module switch (admin)",
    dependencies=[_require_wallet_manage],
)
async def set_wallet_setting(
    key: str,
    enabled: bool = Query(..., description="Whether the wallet switch is enabled"),
    db: AsyncSession = Depends(get_db),
) -> WalletSwitchResponse:
    """Enable/disable a wallet capability (deposit, withdraw, transfer, …)."""
    value = await wallet_service.set_switch(db, key=key, enabled=enabled)
    return WalletSwitchResponse(key=key, enabled=value)


@admin_router.get(
    "/withdrawals",
    response_model=WalletWithdrawalListResponse,
    summary="List withdrawal requests (admin)",
    dependencies=[_require_wallet_read],
)
async def admin_list_withdrawals(
    status_filter: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> WalletWithdrawalListResponse:
    """List withdrawal requests, optionally filtered by status."""
    status_enum = None
    if status_filter:
        try:
            status_enum = WithdrawalStatus(status_filter)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="وضعیت درخواست برداشت نامعتبر است.",
            ) from None
    return await wallet_service.list_withdrawals_admin(
        db, status=status_enum, page=page, page_size=page_size
    )


@admin_router.post(
    "/withdrawals/{request_id}/review",
    response_model=WalletWithdrawalResponse,
    summary="Approve/reject a withdrawal request (admin)",
    dependencies=[_require_wallet_manage],
)
async def admin_review_withdrawal(
    request_id: uuid.UUID,
    body: WithdrawalReviewRequest,
    admin_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> WalletWithdrawalResponse:
    """Approve or reject a pending withdrawal request.

    Approving marks it APPROVED (money already held); rejecting returns the
    held funds to the customer's wallet.
    """
    return await wallet_service.review_withdrawal(
        db,
        request_id=request_id,
        admin_id=admin_id,
        is_approved=body.is_approved,
        admin_notes=body.admin_notes,
    )


@admin_router.post(
    "/withdrawals/{request_id}/mark-paid",
    response_model=WalletWithdrawalResponse,
    summary="Record the manual bank payout for an approved withdrawal (admin)",
    dependencies=[_require_wallet_manage],
)
async def admin_mark_withdrawal_paid(
    request_id: uuid.UUID,
    body: WithdrawalMarkPaidRequest,
    admin_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> WalletWithdrawalResponse:
    """Record that the out-of-band bank transfer was made, with its reference."""
    return await wallet_service.mark_withdrawal_paid(
        db,
        request_id=request_id,
        admin_id=admin_id,
        payout_reference=body.payout_reference,
    )


@admin_router.get(
    "/wallets",
    response_model=WalletAdminListResponse,
    summary="List customer wallets (admin)",
    dependencies=[_require_wallet_read],
)
async def admin_list_wallets(
    search: str | None = Query(None, description="Filter by owner phone"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> WalletAdminListResponse:
    """List wallets, optionally filtered by the owner's phone number."""
    return await wallet_service.admin_list_wallets(
        db, search=search, page=page, page_size=page_size
    )


@admin_router.get(
    "/wallets/{user_id}/ledger",
    response_model=WalletTransactionListResponse,
    summary="Read a customer's wallet ledger (admin)",
    dependencies=[_require_wallet_read],
)
async def admin_get_ledger(
    user_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> WalletTransactionListResponse:
    """Read any customer's wallet ledger (read-only)."""
    return await wallet_service.admin_get_ledger(
        db, user_id=user_id, page=page, page_size=page_size
    )


@admin_router.post(
    "/wallets/{user_id}/adjust",
    response_model=WalletTransactionResponse,
    status_code=201,
    summary="Adjust a customer's wallet balance (admin)",
    dependencies=[_require_wallet_manage],
)
async def admin_adjust_wallet(
    user_id: uuid.UUID,
    body: WalletAdminAdjustRequest,
    admin_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> WalletTransactionResponse:
    """Credit (positive amount) or debit (negative amount) a customer wallet."""
    return await wallet_service.admin_adjust(
        db,
        user_id=user_id,
        amount=body.amount,
        reason=body.reason,
        admin_id=admin_id,
    )


@admin_router.get(
    "/transfers",
    response_model=WalletTransferListResponse,
    summary="List peer-to-peer transfers (admin)",
    dependencies=[_require_wallet_read],
)
async def admin_list_transfers(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> WalletTransferListResponse:
    """List peer-to-peer transfers, newest first."""
    return await wallet_service.admin_list_transfers(db, page=page, page_size=page_size)
