"""Wallet module API routes."""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.security.dependencies import get_current_user_id
from app.modules.wallet.application import wallet_service
from app.modules.wallet.domain.models import WalletTransactionType
from app.modules.wallet.schemas.wallet import (
    WalletDepositRequest,
    WalletResponse,
    WalletTransactionListResponse,
    WalletTransactionResponse,
    WalletWithdrawRequest,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

router = APIRouter()


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
async def deposit(
    body: WalletDepositRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> WalletTransactionResponse:
    """Credit the user's wallet with the specified amount.

    In a production flow, this endpoint would first create a payment through
    the payment module and credit the wallet only after verification.  For
    direct wallet top-ups (e.g., admin adjustments) this records the credit
    immediately.
    """
    return await wallet_service.credit(
        db,
        user_id=user_id,
        amount=body.amount,
        tx_type=WalletTransactionType.CREDIT,
        reference_type="deposit",
        description="Wallet deposit",
    )


# ── Withdraw ──────────────────────────────────────────────────────────────


@router.post(
    "/withdraw",
    response_model=WalletTransactionResponse,
    status_code=201,
    summary="Withdraw funds from wallet",
)
async def withdraw(
    body: WalletWithdrawRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> WalletTransactionResponse:
    """Deduct funds from the user's wallet.

    The balance is checked atomically under a row-level lock; if the
    available balance is insufficient an error is returned.
    """
    return await wallet_service.debit(
        db,
        user_id=user_id,
        amount=body.amount,
        tx_type=WalletTransactionType.WITHDRAWAL,
        reference_type="withdrawal",
        description="Wallet withdrawal",
    )
