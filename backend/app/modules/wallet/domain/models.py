"""Digital wallet domain models."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.base import BaseModel

# ---- Enums ----


class WalletTransactionType(str, enum.Enum):
    CREDIT = "credit"
    DEBIT = "debit"
    REFUND = "refund"
    CASHBACK = "cashback"
    BONUS = "bonus"
    WITHDRAWAL = "withdrawal"
    ADJUSTMENT = "adjustment"
    # Peer-to-peer transfer pair. Both legs share one ``journal_entry_id`` (the
    # ``reference_id`` of a journal entry) so a transfer is provably linked;
    # they are distinct members from DEBIT/CREDIT so a customer's history reads
    # "transfer out / transfer in" rather than a generic debit/credit.
    TRANSFER_OUT = "transfer_out"
    TRANSFER_IN = "transfer_in"
    # Withdrawal request lifecycle. Submitting a request debits the wallet
    # immediately (the funds are held); rejecting it credits the wallet back.
    # Approval + manual payout change only the request's status — the money
    # already moved at hold time, so the ledger stays the single source of truth.
    WITHDRAWAL_HOLD = "withdrawal_hold"
    WITHDRAWAL_REVERSAL = "withdrawal_reversal"


class WithdrawalStatus(str, enum.Enum):
    """Lifecycle of a customer withdrawal request.

    PENDING_REVIEW → APPROVED → PAID  (happy path)
    PENDING_REVIEW → REJECTED         (funds reversed to the wallet)
    """

    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    PAID = "paid"


# ---- Models ----


class Wallet(BaseModel):
    """User digital wallet for in-platform balance."""

    __tablename__ = "wallets"
    __table_args__ = (
        Index("ix_wallets_user_id", "user_id"),
        CheckConstraint("balance >= 0", name="ck_wallets_balance_non_negative"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    balance: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    transactions: Mapped[list["WalletTransaction"]] = relationship(
        "WalletTransaction", back_populates="wallet", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<Wallet(id={self.id}, user_id={self.user_id}, balance={self.balance})>"


class WalletTransaction(BaseModel):
    """Individual wallet balance movements."""

    __tablename__ = "wallet_transactions"
    __table_args__ = (
        Index("ix_wallet_transactions_wallet_id", "wallet_id"),
        Index("ix_wallet_transactions_type", "type"),
        Index("ix_wallet_transactions_created_at", "created_at"),
        Index(
            "ix_wallet_transactions_reference",
            "reference_type",
            "reference_id",
        ),
        # Business rule: the welcome signup gift may be credited at most
        # once per user. Created by migration a9b8c7d6e5f4 as a partial
        # unique index; declared here so autogenerate does not drop it.
        Index(
            "uq_wallet_signup_gift_once",
            "reference_id",
            unique=True,
            postgresql_where=text("reference_type = 'signup_gift' AND type = 'bonus'"),
        ),
    )

    wallet_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("wallets.id", ondelete="CASCADE"),
        nullable=False,
    )
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    type: Mapped[WalletTransactionType] = mapped_column(
        Enum(
            WalletTransactionType,
            name="wallet_transaction_type_enum",
            native_enum=False,
        ),
        nullable=False,
    )
    reference_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    reference_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    balance_after: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # Relationships
    wallet: Mapped["Wallet"] = relationship("Wallet", back_populates="transactions")

    def __repr__(self) -> str:
        return f"<WalletTransaction(id={self.id}, type={self.type}, amount={self.amount})>"


class WalletWithdrawalRequest(BaseModel):
    """A customer request to withdraw wallet funds to a bank account.

    The money movement happens at *submission* time: the service debits the
    wallet (a ``WITHDRAWAL_HOLD`` ledger entry, ``wallet_transaction_id``)
    so the funds are blocked the moment the request exists. Approval and
    manual payout only advance ``status`` — the ledger is never re-touched on
    approval, and a rejection credits the funds back with a
    ``WITHDRAWAL_REVERSAL`` entry. This keeps ``wallet_transactions`` the
    single source of truth and avoids a separate "held balance" column.
    """

    __tablename__ = "wallet_withdrawal_requests"
    __table_args__ = (
        Index("ix_wallet_withdrawal_requests_user_id", "user_id"),
        Index("ix_wallet_withdrawal_requests_status", "status"),
        Index("ix_wallet_withdrawal_requests_created_at", "created_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[WithdrawalStatus] = mapped_column(
        Enum(WithdrawalStatus, name="withdrawal_status_enum", native_enum=False),
        default=WithdrawalStatus.PENDING_REVIEW,
        nullable=False,
        server_default=text("'PENDING_REVIEW'::character varying"),
    )
    # Payout destination captured from the customer. IBAN (sheba) is the
    # canonical Iranian destination; a card number is accepted as a fallback.
    iban: Mapped[str | None] = mapped_column(String(34), nullable=True)
    card_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    account_holder_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # The ledger debit that held the funds at submission. Nullable so a row
    # written before the hold (should never happen) is still readable.
    wallet_transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    admin_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Set when an admin records the out-of-band bank transfer (manual payout).
    payout_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(
        String(255), unique=True, nullable=True
    )

    def __repr__(self) -> str:
        return (
            f"<WalletWithdrawalRequest(id={self.id}, user_id={self.user_id}, "
            f"amount={self.amount}, status={self.status})>"
        )


class WalletTransfer(BaseModel):
    """A peer-to-peer wallet transfer between two customers.

    The actual money movement is a balanced journal entry
    (``journal_entry_id``); this row is the customer-facing record carrying
    the participants, the amount and any fee. ``fee`` is reserved for a future
    platform fee and defaults to 0 (no fee today).
    """

    __tablename__ = "wallet_transfers"
    __table_args__ = (
        Index("ix_wallet_transfers_from_user_id", "from_user_id"),
        Index("ix_wallet_transfers_to_user_id", "to_user_id"),
        Index("ix_wallet_transfers_created_at", "created_at"),
    )

    from_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    to_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    fee: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    # The shared ``reference_id`` of the two ledger rows written by
    # ``record_journal_entry`` — links this record to the money movement.
    journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(
        String(255), unique=True, nullable=True
    )

    def __repr__(self) -> str:
        return (
            f"<WalletTransfer(id={self.id}, from={self.from_user_id}, "
            f"to={self.to_user_id}, amount={self.amount})>"
        )
