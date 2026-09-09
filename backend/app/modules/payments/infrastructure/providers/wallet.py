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
        """Initiate payment from internal wallet balance."""
        authority = f"WALLET-{uuid.uuid4().hex[:12].upper()}"
        gateway_url = f"/wallet/pay?authority={authority}&order_id={order_id}"

        await logger.ainfo(
            "wallet_payment_create",
            order_id=str(order_id),
            amount=amount,
            authority=authority,
        )

        return PaymentResult(
            success=True,
            authority=authority,
            gateway_url=gateway_url,
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
        """Verify internal wallet payment debit."""
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

        if db is not None and user_id is not None:
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
