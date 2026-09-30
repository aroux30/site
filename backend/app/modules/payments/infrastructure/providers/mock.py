"""Mock payment provider for development and testing.

Returns deterministic success/failure based on amount conventions:
- Amounts ending in ``99`` simulate a failure.
- All other amounts succeed immediately.

The mock also implements the payments-upgrade capabilities (tokenization and
installments) so the split-tender / saved-card / installment code paths are
exercisable end-to-end in development. It is the **only** provider that
implements them for real; the Iranian gateways wired here (Zarinpal, IDPay)
do not expose those operations in their public APIs — see the capability
docstrings in :mod:`app.modules.payments.infrastructure.providers.base`.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import structlog

from app.modules.payments.infrastructure.providers.base import (
    PaymentProvider,
    PaymentResult,
    TokenizationResult,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_MOCK_GATEWAY_URL = "http://localhost:3000/mock-gateway"

# Installment durations the mock advertises, matching the Iranian market's
# common 2 / 4 / 6 / 12 month offerings.
_MOCK_INSTALLMENT_MONTHS = (2, 4, 6, 12)


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

    # ── Capabilities: tokenization (mock) ─────────────────────────────
    #
    # The mock is the reference implementation of the tokenization contract:
    # it returns an opaque token plus display metadata and never a PAN. Real
    # gateways wired here do not implement these (see base.py for the
    # per-gateway status table).

    @property
    def supports_tokenization(self) -> bool:
        return True

    async def tokenize(
        self,
        *,
        user_id: uuid.UUID,
        callback_url: str,
        mobile: str | None = None,
    ) -> TokenizationResult:
        """Issue a deterministic mock token with masked display metadata.

        Deliberately returns only a masked PAN + last4: the real gateway
        contract forbids handing this application a full PAN, and the mock
        must not normalise a shape the real integrations cannot provide.
        """
        token = f"MOCKTOK-{uuid.uuid4().hex[:16]}"
        last4 = f"{uuid.uuid4().int % 10_000:04d}"
        await logger.ainfo(
            "mock_tokenize_success",
            user_id=str(user_id),
            token=token,
        )
        return TokenizationResult(
            success=True,
            token=token,
            masked_pan=f"6037-****-****-{last4}",
            last4=last4,
            expiry_jalali="1407/03",
            card_holder_name="دارنده کارت آزمایشی",
            bank_name="بانک آزمایشی",
            raw_response={"simulated": True, "callback_url": callback_url, "mobile": mobile},
        )

    async def charge_token(
        self,
        *,
        token: str,
        amount: int,
        order_id: uuid.UUID,
        description: str = "",
    ) -> PaymentResult:
        """Charge a mock token; amounts ending in 99 still simulate failure."""
        if amount % 100 == 99:
            await logger.ainfo(
                "mock_charge_token_simulated_failure",
                token=token,
                amount=amount,
            )
            return PaymentResult(
                success=False,
                authority=token,
                error_code="MOCK_CHARGE_FAILURE",
                error_message="Simulated tokenized charge failure (amount ends in 99)",
                raw_response={"simulated": True},
            )

        ref_id = f"MOCKTOKREF-{uuid.uuid4().hex[:12]}"
        await logger.ainfo(
            "mock_charge_token_success",
            token=token,
            amount=amount,
            order_id=str(order_id),
            ref_id=ref_id,
        )
        return PaymentResult(
            success=True,
            authority=token,
            ref_id=ref_id,
            card_pan="6037-****-****-1234",
            raw_response={
                "simulated": True,
                "token": token,
                "order_id": str(order_id),
                "amount": amount,
                "ref_id": ref_id,
                "charged_at": datetime.now(UTC).isoformat(),
            },
        )

    async def revoke_token(self, *, token: str) -> bool:
        await logger.ainfo("mock_revoke_token", token=token)
        return True

    # ── Capabilities: installments (mock) ─────────────────────────────

    @property
    def supports_installments(self) -> bool:
        return True

    @property
    def installment_options_months(self) -> tuple[int, ...]:
        return _MOCK_INSTALLMENT_MONTHS
