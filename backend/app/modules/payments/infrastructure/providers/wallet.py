"""Internal wallet payment provider."""

from __future__ import annotations

import uuid
from typing import Any

import structlog

from app.modules.payments.infrastructure.providers.base import (
    PaymentProvider,
    PaymentResult,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class WalletPaymentProvider(PaymentProvider):
    """Internal user wallet payment adapter."""

    @property
    def provider_name(self) -> str:
        return "wallet"

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
        """Initiate payment from internal wallet balance.

        No external redirect is involved: the client completes the payment by
        calling the verify endpoint, and the service layer debits the wallet
        inside the same locked transaction that completes the payment.
        """
        authority = f"WALLET-{uuid.uuid4().hex[:12].upper()}"

        await logger.ainfo(
            "wallet_payment_create",
            order_id=str(order_id),
            amount=amount,
            authority=authority,
        )

        return PaymentResult(
            success=True,
            authority=authority,
            gateway_url=None,
            raw_response={
                "order_id": str(order_id),
                "amount": amount,
                "provider": "wallet",
            },
        )

    async def verify_payment(
        self,
        *,
        authority: str,
        amount: int,
    ) -> PaymentResult:
        """Confirm an internal wallet payment.

        The authoritative wallet debit is performed by the payment service in
        the same transaction that marks the payment completed; this method
        only reports success for the gateway-adapter contract.
        """
        ref_id = f"WTX-{uuid.uuid4().hex[:10].upper()}"
        await logger.ainfo(
            "wallet_payment_verify",
            authority=authority,
            amount=amount,
            ref_id=ref_id,
        )
        return PaymentResult(
            success=True,
            authority=authority,
            ref_id=ref_id,
            raw_response={
                "provider": "wallet",
                "authority": authority,
                "ref_id": ref_id,
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
        """Refund an internal wallet transaction by re-crediting the wallet."""
        ref_id = f"WREF-{uuid.uuid4().hex[:10].upper()}"

        if db is None or user_id is None:
            # Without a session and a resolved owner there is no wallet to
            # credit, so a "successful" refund would record PROCESSED money
            # that never moved. Fail closed and let refund_payment record a
            # retryable APPROVED refund instead.
            await logger.aerror(
                "wallet_provider_refund_missing_context",
                authority=authority,
                has_db=db is not None,
                has_user_id=user_id is not None,
            )
            return PaymentResult(
                success=False,
                authority=authority,
                ref_id=ref_id,
                raw_response={
                    "provider": "wallet",
                    "method": "wallet_refund_missing_context",
                    "error": "refund requires a db session and a resolved owner",
                    "amount": amount,
                },
            )

        try:
            from app.modules.wallet.application import wallet_service
            from app.modules.wallet.domain.models import WalletTransactionType

            tx = await wallet_service.credit(
                db,
                user_id=user_id,
                amount=amount,
                tx_type=WalletTransactionType.REFUND,
                description=f"استرداد به کیف پول ({authority})",
            )
            ref_id = str(tx.id)
        except Exception as exc:
            await logger.awarning("wallet_provider_refund_credit_failed", error=str(exc))
            # The wallet credit failed — the refund has NOT settled.
            # Returning success=True would record a PROCESSED Refund for
            # money that never landed (and flip the payment to REFUNDED).
            # success=False makes refund_payment record an
            # APPROVED/pending_manual refund instead, retryable later.
            return PaymentResult(
                success=False,
                authority=authority,
                ref_id=ref_id,
                raw_response={
                    "provider": "wallet",
                    "method": "wallet_credit_failed",
                    "error": str(exc),
                    "amount": amount,
                },
            )

        return PaymentResult(
            success=True,
            authority=authority,
            ref_id=ref_id,
            raw_response={
                "provider": "wallet",
                "authority": authority,
                "amount": amount,
            },
        )
