"""Pydantic v2 schemas for the wallet module."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.wallet.domain.models import WalletTransactionType, WithdrawalStatus

# ── Request Schemas ───────────────────────────────────────────────────────


class WalletDepositRequest(BaseModel):
    """Deposit funds into the user's wallet."""

    model_config = ConfigDict(str_strip_whitespace=True)

    amount: int = Field(..., gt=0, description="Amount to deposit in IRR (Rials)")


class WalletWithdrawRequest(BaseModel):
    """Withdraw funds from the user's wallet."""

    model_config = ConfigDict(str_strip_whitespace=True)

    amount: int = Field(..., gt=0, description="Amount to withdraw in IRR (Rials)")


# ── Response Schemas ──────────────────────────────────────────────────────


class WalletFeatures(BaseModel):
    """Which wallet capabilities are currently enabled (module switches).

    Surfaced on ``GET /wallet`` so the storefront can HIDE the corresponding
    entry points instead of rendering buttons that only answer with an error.
    ``enabled`` is the master switch: when it is off the whole wallet surface
    (menu entry, balance chip, wallet tab, checkout wallet payment) must
    disappear, not merely the action buttons. A missing/absent field reads as
    enabled (backwards compatible with an older backend or a database that
    predates the switch seeds).
    """

    enabled: bool = True
    deposit: bool = True
    withdraw: bool = True
    transfer: bool = True


class WalletResponse(BaseModel):
    """Current wallet state."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    balance: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    features: WalletFeatures = Field(default_factory=WalletFeatures)


class WalletTransactionResponse(BaseModel):
    """A single wallet transaction."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    wallet_id: uuid.UUID
    amount: int
    type: WalletTransactionType
    reference_type: str | None = None
    reference_id: uuid.UUID | None = None
    description: str | None = None
    balance_after: int
    created_at: datetime


class WalletTransactionListResponse(BaseModel):
    """Paginated list of wallet transactions."""

    items: list[WalletTransactionResponse]
    total: int
    page: int
    page_size: int
    pages: int


class WalletTopupRequest(BaseModel):
    """Start a gateway-backed wallet top-up payment."""

    model_config = ConfigDict(str_strip_whitespace=True)

    provider: str = Field(
        ..., description="Online gateway to pay with (zarinpal)"
    )
    amount: int = Field(..., gt=0, description="Top-up amount in IRR (Rials)")
    idempotency_key: str | None = Field(
        None, max_length=255, description="Client-generated idempotency key"
    )


# ── Transfer Schemas ──────────────────────────────────────────────────────


class WalletTransferRequest(BaseModel):
    """Transfer funds from the caller's wallet to another customer."""

    model_config = ConfigDict(str_strip_whitespace=True)

    # The store is phone-first (the ``users.email`` column was removed on
    # 2026-10-07 with the email feature), so the recipient is identified by
    # phone number. The service normalizes it, resolves it to a user and
    # rejects unknown/self recipients.
    recipient_phone: str = Field(
        ..., min_length=4, max_length=15, description="Recipient phone number"
    )
    amount: int = Field(..., gt=0, description="Transfer amount in IRR (Rials)")
    note: str | None = Field(None, max_length=500, description="Optional note to the recipient")
    idempotency_key: str | None = Field(
        None, max_length=255, description="Client-generated idempotency key"
    )

    @field_validator("recipient_phone")
    @classmethod
    def _normalize_recipient(cls, v: str) -> str:
        # Reuse the auth module's canonical Iranian-mobile normalizer so a
        # recipient typed as "+98912…", "98912…" or with Persian digits
        # resolves to the same stored form ("0912…") as login does.
        from app.modules.auth.schemas.auth import _validate_iran_phone

        return _validate_iran_phone(v)


class WalletTransferResponse(BaseModel):
    """A completed peer-to-peer transfer."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    from_user_id: uuid.UUID
    to_user_id: uuid.UUID
    amount: int
    fee: int
    journal_entry_id: uuid.UUID | None = None
    note: str | None = None
    created_at: datetime


# ── Withdrawal Schemas ────────────────────────────────────────────────────


class WalletWithdrawalCreateRequest(BaseModel):
    """Submit a withdrawal request; funds are held immediately on success."""

    model_config = ConfigDict(str_strip_whitespace=True)

    amount: int = Field(..., gt=0, description="Withdrawal amount in IRR (Rials)")
    # Iranian IBAN (sheba) is the canonical payout destination; a card number
    # is accepted as a fallback. At least one of the two must be provided.
    iban: str | None = Field(None, max_length=34, description="Iranian IBAN (sheba)")
    card_number: str | None = Field(None, max_length=20, description="Destination card number")
    account_holder_name: str | None = Field(
        None, max_length=200, description="Account holder name"
    )
    idempotency_key: str | None = Field(
        None, max_length=255, description="Client-generated idempotency key"
    )


class WalletWithdrawalResponse(BaseModel):
    """A withdrawal request and its current status."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    amount: int
    status: WithdrawalStatus
    iban: str | None = None
    card_number: str | None = None
    account_holder_name: str | None = None
    wallet_transaction_id: uuid.UUID | None = None
    reviewed_by: uuid.UUID | None = None
    reviewed_at: datetime | None = None
    admin_notes: str | None = None
    payout_reference: str | None = None
    paid_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class WalletWithdrawalListResponse(BaseModel):
    """Paginated list of the caller's withdrawal requests."""

    items: list[WalletWithdrawalResponse]
    total: int
    page: int
    page_size: int
    pages: int


class WithdrawalReviewRequest(BaseModel):
    """Admin decision on a pending withdrawal request."""

    is_approved: bool
    admin_notes: str | None = Field(None, max_length=1000)


class WithdrawalMarkPaidRequest(BaseModel):
    """Admin records the out-of-band bank payout for an approved withdrawal."""

    payout_reference: str = Field(
        ..., min_length=1, max_length=255, description="Bank transfer reference / tracking code"
    )


# ── Admin Schemas ─────────────────────────────────────────────────────────


class WalletAdminAdjustRequest(BaseModel):
    """Admin credit/debit adjustment of a customer wallet."""

    model_config = ConfigDict(str_strip_whitespace=True)

    # Signed amount in Rials: positive credits, negative debits. Never zero.
    amount: int = Field(..., description="Signed amount in IRR: +credit, -debit")
    reason: str = Field(..., min_length=3, max_length=500, description="Reason for the adjustment")

    @field_validator("amount")
    @classmethod
    def _non_zero(cls, v: int) -> int:
        if v == 0:
            raise ValueError("Amount must not be zero")
        return v


class WalletAdminListItem(BaseModel):
    """One wallet row in the admin wallet list."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    balance: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class WalletAdminListResponse(BaseModel):
    """Paginated admin list of wallets."""

    items: list[WalletAdminListItem]
    total: int
    page: int
    page_size: int
    pages: int


class WalletTransferListResponse(BaseModel):
    """Paginated admin list of peer-to-peer transfers."""

    items: list[WalletTransferResponse]
    total: int
    page: int
    page_size: int
    pages: int


class WalletSwitchResponse(BaseModel):
    """A single wallet module switch after a change."""

    key: str
    enabled: bool
