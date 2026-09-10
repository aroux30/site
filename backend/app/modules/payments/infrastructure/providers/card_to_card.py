"""Card-to-Card (کارت به کارت) bank transfer payment provider.

Allows buyers to pay by directly transferring funds to the merchant's bank
account / card number (e.g. بانک سامان / ۶۲۱۹-۸۶۱۰-...).
Customers submit their bank reference / tracking code or upload a receipt photo.
The payment remains in PENDING status until an administrator reviews and
approves or rejects it.
"""

from __future__ import annotations

import uuid
from typing import Any, Optional

import structlog

from app.core.config.settings import get_settings
from app.modules.payments.infrastructure.providers.base import (
    PaymentProvider,
    PaymentResult,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# Default merchant bank transfer credentials (Iranian banking standard)
_DEFAULT_CARD_NUMBER = "6219-8610-1234-5678"
_DEFAULT_CARD_HOLDER = "فروشگاه آنلاین"
_DEFAULT_BANK_NAME = "بانک سامان"
_DEFAULT_INSTRUCTIONS = (
    "لطفاً مبلغ را به شماره کارت زیر واریز نموده و سپس شماره پیگیری / شماره ارجاع "
    "را در بخش ثبت فیش ارسال فرمایید. پس از بررسی و تأیید مدیریت، سفارش شما "
    "تکمیل خواهد شد."
)


def format_card_pan(pan: str) -> str:
    """Format a 16-digit card number into 4-4-4-4 blocks."""
    clean = "".join(filter(str.isdigit, pan))
    if len(clean) == 16:
        return f"{clean[0:4]}-{clean[4:8]}-{clean[8:12]}-{clean[12:16]}"
    return pan


class CardToCardProvider(PaymentProvider):
    """Card-to-Card offline bank transfer payment adapter."""

    def __init__(
        self,
        card_number: str | None = None,
        card_holder: str | None = None,
        bank_name: str | None = None,
        instructions: str | None = None,
    ) -> None:
        settings = get_settings()
        self._card_number = format_card_pan(
            card_number
            if card_number is not None
            else getattr(settings, "CARD_TO_CARD_NUMBER", _DEFAULT_CARD_NUMBER)
        )
        self._card_holder = (
            card_holder
            if card_holder is not None
            else getattr(settings, "CARD_TO_CARD_HOLDER", _DEFAULT_CARD_HOLDER)
        )
        self._bank_name = (
            bank_name
            if bank_name is not None
            else getattr(settings, "CARD_TO_CARD_BANK", _DEFAULT_BANK_NAME)
        )
        self._instructions = (
            instructions
            if instructions is not None
            else getattr(settings, "CARD_TO_CARD_INSTRUCTIONS", _DEFAULT_INSTRUCTIONS)
        )

    # ── PaymentProvider interface ─────────────────────────────────────

    @property
    def provider_name(self) -> str:
        return "card_transfer"

    @property
    def card_number(self) -> str:
        return self._card_number

    @property
    def card_holder(self) -> str:
        return self._card_holder

    @property
    def bank_name(self) -> str:
        return self._bank_name

    @property
    def instructions(self) -> str:
        return self._instructions

    def get_merchant_details(self) -> dict[str, str]:
        """Return merchant bank details for customer-facing display."""
        return {
            "card_number": self._card_number,
            "card_holder": self._card_holder,
            "bank_name": self._bank_name,
            "instructions": self._instructions,
        }

    async def create_payment(
        self,
        *,
        amount: int,
        order_id: uuid.UUID,
        callback_url: str,
        description: str = "",
        mobile: str | None = None,
        email: str | None = None,
    ) -> PaymentResult:
        """Initiate a Card-to-Card payment and return merchant card details.

        Generates a unique tracking authority for the transaction. The payment
        status remains PENDING awaiting receipt submission and admin approval.
        """
        short_uuid = uuid.uuid4().hex[:10].upper()
        authority = f"C2C-{short_uuid}"
        receipt_submission_url = f"/checkout/card-transfer?authority={authority}&order_id={order_id}"

        await logger.ainfo(
            "card_to_card_create_payment",
            order_id=str(order_id),
            amount=amount,
            authority=authority,
            card_number=self._card_number,
        )

        merchant_data = {
            "authority": authority,
            "order_id": str(order_id),
            "amount": amount,
            "currency": "IRR",
            "card_number": self._card_number,
            "card_holder": self._card_holder,
            "bank_name": self._bank_name,
            "instructions": self._instructions,
            "receipt_submission_url": receipt_submission_url,
            "requires_admin_approval": True,
            "status": "pending_receipt",
        }

        return PaymentResult(
            success=True,
            authority=authority,
            gateway_url=receipt_submission_url,
            card_pan=self._card_number,
            raw_response=merchant_data,
        )

    async def verify_payment(
        self,
        *,
        authority: str,
        amount: int,
    ) -> PaymentResult:
        """Check verification status for a card-to-card transfer.

        Card-to-card transfers require manual verification by an administrator
        via `/admin/payments/{id}/approve`. Automated checks return a pending
        status message unless simulating immediate approval in test mode.
        """
        await logger.ainfo(
            "card_to_card_verify_attempt",
            authority=authority,
            amount=amount,
        )

        # In testing/simulation mode, allow explicit test authorities to auto-verify
        if authority.endswith("-APPROVED"):
            settings = get_settings()
            if settings.ENVIRONMENT == "production":
                raise ValueError(
                    "Security violation: Simulated payment auto-approval is strictly forbidden in production"
                )
            ref_id = f"REF-{authority}"
            return PaymentResult(
                success=True,
                authority=authority,
                ref_id=ref_id,
                card_pan=self._card_number,
                raw_response={
                    "simulated": True,
                    "approved": True,
                    "authority": authority,
                },
            )

        # Standard card transfers require admin verification
        return PaymentResult(
            success=False,
            authority=authority,
            error_code="WAITING_ADMIN_APPROVAL",
            error_message="پرداخت کارت به کارت پس از بررسی فیش توسط مدیریت تأیید می‌شود.",
            raw_response={
                "authority": authority,
                "status": "waiting_admin_approval",
                "card_number": self._card_number,
            },
        )

    async def refund(
        self,
        *,
        authority: str,
        amount: int,
        user_id: uuid.UUID | None = None,
        db: Any = None,
        **kwargs: Any,
    ) -> PaymentResult:
        """Process a refund for a card-to-card payment.

        Credits the internal wallet if a database session and user_id are
        supplied, otherwise creates a manual bank refund tracking record.
        """
        await logger.ainfo(
            "card_to_card_refund_start",
            authority=authority,
            amount=amount,
            user_id=str(user_id) if user_id else None,
        )

        # Credit internal customer wallet if possible
        if db is not None and user_id is not None:
            try:
                from app.modules.wallet.application import wallet_service
                from app.modules.wallet.domain.models import WalletTransactionType

                wallet_tx = await wallet_service.credit(
                    db,
                    user_id=user_id,
                    amount=amount,
                    tx_type=WalletTransactionType.REFUND,
                    description=f"استرداد وجه کارت به کارت ({authority})",
                )
                return PaymentResult(
                    success=True,
                    authority=authority,
                    ref_id=str(wallet_tx.id),
                    raw_response={
                        "method": "internal_wallet_credit",
                        "wallet_transaction_id": str(wallet_tx.id),
                        "amount": amount,
                    },
                )
            except Exception as exc:
                await logger.awarning(
                    "card_to_card_wallet_refund_failed",
                    error=str(exc),
                )

        ref_id = f"C2CREFUND-{uuid.uuid4().hex[:8].upper()}"
        return PaymentResult(
            success=True,
            authority=authority,
            ref_id=ref_id,
            raw_response={
                "method": "manual_card_refund",
                "authority": authority,
                "amount": amount,
                "note": "استرداد کارت به کارت به صورت انتقال وجه دستی بانکی انجام می‌شود.",
            },
        )
