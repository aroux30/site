"""Mock payment provider for development and testing.

Returns deterministic success/failure based on amount conventions:
- Amounts ending in ``99`` simulate a failure.
- All other amounts succeed immediately.
"""

from __future__ import annotations

import uuid
from typing import Any

import structlog

from app.modules.payments.infrastructure.providers.base import (
    PaymentProvider,
    PaymentResult,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_MOCK_GATEWAY_URL = "http://localhost:3000/mock-gateway"


class MockProvider(PaymentProvider):
    """In-memory mock payment provider for local development and tests."""

    @property
    def provider_name(self) -> str:
        return "mock"

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
        mock_authority = f"MOCK-{uuid.uuid4().hex[:16]}"

        # Simulate failure for amounts ending in 99
        if amount % 100 == 99:
            await logger.ainfo(
                "mock_create_payment_simulated_failure",
                order_id=str(order_id),
                amount=amount,
            )
            return PaymentResult(
                success=False,
                error_code="MOCK_FAILURE",
                error_message="Simulated payment failure (amount ends in 99)",
                raw_response={"simulated": True},
            )

        gateway_url = (
            f"{_MOCK_GATEWAY_URL}"
            f"?authority={mock_authority}"
            f"&callback={callback_url}"
            f"&amount={amount}"
        )

        await logger.ainfo(
            "mock_create_payment_success",
            order_id=str(order_id),
            amount=amount,
            authority=mock_authority,
        )

        return PaymentResult(
            success=True,
            authority=mock_authority,
            gateway_url=gateway_url,
            raw_response={
                "simulated": True,
                "order_id": str(order_id),
                "amount": amount,
            },
        )

    async def verify_payment(
        self,
        *,
        authority: str,
        amount: int,
    ) -> PaymentResult:
        # Simulate failure for amounts ending in 99
        if amount % 100 == 99:
            await logger.ainfo(
                "mock_verify_simulated_failure",
                authority=authority,
                amount=amount,
            )
            return PaymentResult(
                success=False,
                authority=authority,
                error_code="MOCK_VERIFY_FAILURE",
                error_message="Simulated verification failure (amount ends in 99)",
                raw_response={"simulated": True},
            )

        mock_ref_id = f"MOCKREF-{uuid.uuid4().hex[:12]}"

        await logger.ainfo(
            "mock_verify_success",
            authority=authority,
            ref_id=mock_ref_id,
            amount=amount,
        )

        return PaymentResult(
            success=True,
            authority=authority,
            ref_id=mock_ref_id,
            card_pan="6037-****-****-1234",
            raw_response={
                "simulated": True,
                "ref_id": mock_ref_id,
                "amount": amount,
            },
        )

    async def refund(
        self,
        *,
        authority: str,
        amount: int,
    ) -> PaymentResult:
        await logger.ainfo(
            "mock_refund_success",
            authority=authority,
            amount=amount,
        )
        return PaymentResult(
            success=True,
            authority=authority,
            ref_id=f"MOCKREFUND-{uuid.uuid4().hex[:8]}",
            raw_response={
                "simulated": True,
                "authority": authority,
                "amount": amount,
            },
        )
