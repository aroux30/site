"""IDPay payment gateway provider.

Documentation: https://idpay.ir/web-service/v1.1/
"""

from __future__ import annotations

import uuid
from typing import Any

import httpx
import structlog

from app.core.config.settings import get_settings
from app.modules.payments.infrastructure.providers.base import (
    PaymentProvider,
    PaymentResult,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# ── IDPay API URLs ────────────────────────────────────────────────────────

_SANDBOX_API = "https://api.idpay.ir/v1.1"
_PRODUCTION_API = "https://api.idpay.ir/v1.1"

_REQUEST_TIMEOUT = 30.0  # seconds


class IDPayProvider(PaymentProvider):
    """IDPay payment gateway adapter."""

    def __init__(
        self,
        api_key: str | None = None,
        sandbox: bool | None = None,
        callback_url: str | None = None,
    ) -> None:
        settings = get_settings()
        self._api_key = api_key or settings.PAYMENT_MERCHANT_ID
        self._sandbox = sandbox if sandbox is not None else settings.PAYMENT_SANDBOX
        self._default_callback = callback_url or settings.PAYMENT_CALLBACK_BASE_URL
        self._api_base = _SANDBOX_API if self._sandbox else _PRODUCTION_API

    @property
    def _headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "X-API-KEY": self._api_key,
        }
        if self._sandbox:
            headers["X-SANDBOX"] = "1"
        return headers

    # ── PaymentProvider interface ─────────────────────────────────────

    @property
    def provider_name(self) -> str:
        return "idpay"

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
        """Create a new transaction via IDPay."""

        # IDPay expects amounts in Rials
        payload: dict[str, Any] = {
            "order_id": str(order_id),
            "amount": amount,
            "callback": callback_url,
            "desc": description or f"Order {order_id}",
        }
        if mobile:
            payload["phone"] = mobile
        if email:
            payload["mail"] = email

        await logger.ainfo(
            "idpay_create_payment_request",
            order_id=str(order_id),
            amount=amount,
            sandbox=self._sandbox,
        )

        try:
            async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
                response = await client.post(
                    f"{self._api_base}/payment",
                    json=payload,
                    headers=self._headers,
                )
        except httpx.RequestError as exc:
            await logger.aerror(
                "idpay_create_payment_network_error",
                error=str(exc),
            )
            return PaymentResult(
                success=False,
                error_code="NETWORK_ERROR",
                error_message=f"Network error contacting IDPay: {exc}",
            )

        data = response.json() if response.status_code < 500 else {}

        if response.status_code in (200, 201) and data.get("link"):
            transaction_id = data.get("id", "")
            gateway_url = data["link"]
            await logger.ainfo(
                "idpay_create_payment_success",
                transaction_id=transaction_id,
                order_id=str(order_id),
            )
            return PaymentResult(
                success=True,
                authority=transaction_id,
                gateway_url=gateway_url,
                raw_response=data,
            )

        error_code = str(data.get("error_code", response.status_code))
        error_message = data.get("error_message", "Unknown IDPay error")
        await logger.awarning(
            "idpay_create_payment_failed",
            error_code=error_code,
            error_message=error_message,
        )
        return PaymentResult(
            success=False,
            error_code=error_code,
            error_message=error_message,
            raw_response=data,
        )

    async def verify_payment(
        self,
        *,
        authority: str,
        amount: int,
    ) -> PaymentResult:
        """Verify / settle an IDPay payment.

        ``authority`` here corresponds to the IDPay transaction ``id``.
        """

        payload = {
            "id": authority,
            "order_id": "",  # IDPay docs: either id or order_id required
            "amount": amount,  # server-enforced amount cross-check
        }

        await logger.ainfo(
            "idpay_verify_payment_request",
            transaction_id=authority,
            amount=amount,
        )

        try:
            async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
                response = await client.post(
                    f"{self._api_base}/payment/verify",
                    json=payload,
                    headers=self._headers,
                )
        except httpx.RequestError as exc:
            await logger.aerror(
                "idpay_verify_network_error",
                error=str(exc),
            )
            return PaymentResult(
                success=False,
                error_code="NETWORK_ERROR",
                error_message=f"Network error verifying with IDPay: {exc}",
            )

        data = response.json() if response.status_code < 500 else {}

        # IDPay returns status 200 with verify.status in the response
        verify_status = data.get("status")
        # status 100 = verified successfully, 101 = already verified
        if response.status_code == 200 and verify_status in (100, 101, "100", "101"):
            # Cross-check the settled amount reported by IDPay against the
            # expected payment amount; a mismatch must never settle.
            reported_amount = data.get("amount")
            if reported_amount is not None and int(reported_amount) != int(amount):
                await logger.aerror(
                    "idpay_verify_amount_mismatch",
                    transaction_id=authority,
                    expected=amount,
                    reported=int(reported_amount),
                )
                return PaymentResult(
                    success=False,
                    authority=authority,
                    error_code="AMOUNT_MISMATCH",
                    error_message=(
                        f"IDPay settled amount ({reported_amount}) does not "
                        f"match the payment amount ({amount})"
                    ),
                    raw_response=data,
                )
            track_id = str(data.get("track_id", ""))
            card_no = data.get("payment", {}).get("card_no")
            await logger.ainfo(
                "idpay_verify_success",
                track_id=track_id,
                transaction_id=authority,
            )
            return PaymentResult(
                success=True,
                authority=authority,
                ref_id=track_id,
                card_pan=card_no,
                raw_response=data,
            )

        error_code = str(data.get("error_code", verify_status or response.status_code))
        error_message = data.get("error_message", "IDPay verification failed")
        await logger.awarning(
            "idpay_verify_failed",
            error_code=error_code,
            error_message=error_message,
            transaction_id=authority,
        )
        return PaymentResult(
            success=False,
            authority=authority,
            error_code=error_code,
            error_message=error_message,
            raw_response=data,
        )

    async def refund(
        self,
        *,
        authority: str,
        amount: int,
    ) -> PaymentResult:
        """Request a refund from IDPay.

        IDPay does not expose a public refund API – refunds must be handled
        via the IDPay dashboard.
        """

        await logger.awarning(
            "idpay_refund_manual_required",
            transaction_id=authority,
            amount=amount,
        )
        return PaymentResult(
            success=False,
            authority=authority,
            error_code="MANUAL_REFUND",
            error_message=(
                "IDPay does not support automated refunds via API. "
                "Please process the refund through the IDPay dashboard."
            ),
        )
