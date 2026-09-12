"""Zarinpal payment gateway provider.

Supports both sandbox and production modes.  All amounts are in IRR (Rials);
the provider converts to Toman internally for Zarinpal's API when required.

Documentation: https://docs.zarinpal.com/paymentGateway/
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

# ── Zarinpal API URLs ─────────────────────────────────────────────────────

_SANDBOX_API = "https://sandbox.zarinpal.com/pg/v4/payment"
_PRODUCTION_API = "https://api.zarinpal.com/pg/v4/payment"

_SANDBOX_GATEWAY = "https://sandbox.zarinpal.com/pg/StartPay/{authority}"
_PRODUCTION_GATEWAY = "https://www.zarinpal.com/pg/StartPay/{authority}"

_REQUEST_TIMEOUT = 30.0  # seconds


class ZarinpalProvider(PaymentProvider):
    """Zarinpal payment gateway adapter."""

    def __init__(
        self,
        merchant_id: str | None = None,
        sandbox: bool | None = None,
        callback_url: str | None = None,
    ) -> None:
        settings = get_settings()
        self._merchant_id = merchant_id or settings.PAYMENT_MERCHANT_ID
        self._sandbox = sandbox if sandbox is not None else settings.PAYMENT_SANDBOX
        self._default_callback = callback_url or settings.PAYMENT_CALLBACK_BASE_URL
        self._api_base = _SANDBOX_API if self._sandbox else _PRODUCTION_API
        self._gateway_template = _SANDBOX_GATEWAY if self._sandbox else _PRODUCTION_GATEWAY

    # ── PaymentProvider interface ─────────────────────────────────────

    @property
    def provider_name(self) -> str:
        return "zarinpal"

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
        """Request a new payment authority from Zarinpal."""

        # Zarinpal v4 accepts Rials directly
        payload: dict[str, Any] = {
            "merchant_id": self._merchant_id,
            "amount": amount,
            "callback_url": callback_url,
            "description": description or f"Order {order_id}",
            "metadata": {
                "order_id": str(order_id),
            },
        }
        if mobile:
            payload["metadata"]["mobile"] = mobile
        if email:
            payload["metadata"]["email"] = email

        await logger.ainfo(
            "zarinpal_create_payment_request",
            order_id=str(order_id),
            amount=amount,
            sandbox=self._sandbox,
        )

        try:
            async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
                response = await client.post(
                    f"{self._api_base}/request.json",
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as exc:
            await logger.aerror(
                "zarinpal_create_payment_http_error",
                status_code=exc.response.status_code,
                body=exc.response.text,
            )
            return PaymentResult(
                success=False,
                error_code=str(exc.response.status_code),
                error_message=f"Zarinpal HTTP error: {exc.response.status_code}",
                raw_response={"error": exc.response.text},
            )
        except httpx.RequestError as exc:
            await logger.aerror(
                "zarinpal_create_payment_network_error",
                error=str(exc),
            )
            return PaymentResult(
                success=False,
                error_code="NETWORK_ERROR",
                error_message=f"Network error contacting Zarinpal: {exc}",
            )

        data_section = data.get("data", {})
        errors_section = data.get("errors", {})

        if data_section and data_section.get("code") == 100:
            authority = data_section["authority"]
            gateway_url = self._gateway_template.format(authority=authority)
            await logger.ainfo(
                "zarinpal_create_payment_success",
                authority=authority,
                order_id=str(order_id),
            )
            return PaymentResult(
                success=True,
                authority=authority,
                gateway_url=gateway_url,
                raw_response=data,
            )

        error_code = str(errors_section.get("code", data_section.get("code", "UNKNOWN")))
        error_message = (
            errors_section.get("message")
            or data_section.get("message")
            or "Unknown Zarinpal error"
        )
        await logger.awarning(
            "zarinpal_create_payment_failed",
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
        """Verify a payment with Zarinpal after the user returns."""

        payload = {
            "merchant_id": self._merchant_id,
            "authority": authority,
            "amount": amount,
        }

        await logger.ainfo(
            "zarinpal_verify_payment_request",
            authority=authority,
            amount=amount,
        )

        try:
            async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
                response = await client.post(
                    f"{self._api_base}/verify.json",
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as exc:
            await logger.aerror(
                "zarinpal_verify_http_error",
                status_code=exc.response.status_code,
            )
            return PaymentResult(
                success=False,
                error_code=str(exc.response.status_code),
                error_message=f"Zarinpal verify HTTP error: {exc.response.status_code}",
                raw_response={"error": exc.response.text},
            )
        except httpx.RequestError as exc:
            await logger.aerror(
                "zarinpal_verify_network_error",
                error=str(exc),
            )
            return PaymentResult(
                success=False,
                error_code="NETWORK_ERROR",
                error_message=f"Network error verifying with Zarinpal: {exc}",
            )

        data_section = data.get("data", {})
        errors_section = data.get("errors", {})

        # code 100 = first successful verification, 101 = already verified
        if data_section and data_section.get("code") in (100, 101):
            # Cross-check the settled amount reported by Zarinpal against the
            # expected payment amount; a mismatch must never settle.
            reported_amount = data_section.get("amount")
            if reported_amount is not None and int(reported_amount) != int(amount):
                await logger.aerror(
                    "zarinpal_verify_amount_mismatch",
                    authority=authority,
                    expected=amount,
                    reported=int(reported_amount),
                )
                return PaymentResult(
                    success=False,
                    authority=authority,
                    error_code="AMOUNT_MISMATCH",
                    error_message=(
                        f"Zarinpal settled amount ({reported_amount}) does not "
                        f"match the payment amount ({amount})"
                    ),
                    raw_response=data,
                )
            ref_id = str(data_section.get("ref_id", ""))
            card_pan = data_section.get("card_pan")
            await logger.ainfo(
                "zarinpal_verify_success",
                ref_id=ref_id,
                authority=authority,
            )
            return PaymentResult(
                success=True,
                authority=authority,
                ref_id=ref_id,
                card_pan=card_pan,
                raw_response=data,
            )

        error_code = str(errors_section.get("code", data_section.get("code", "UNKNOWN")))
        error_message = (
            errors_section.get("message")
            or data_section.get("message")
            or "Zarinpal verification failed"
        )
        await logger.awarning(
            "zarinpal_verify_failed",
            error_code=error_code,
            error_message=error_message,
            authority=authority,
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
        """Request a refund through Zarinpal.

        Zarinpal v4 does not have a public refund API endpoint – refunds are
        typically handled through the merchant dashboard.  This implementation
        logs the request and returns a "manual refund required" result.
        """

        await logger.awarning(
            "zarinpal_refund_manual_required",
            authority=authority,
            amount=amount,
        )
        return PaymentResult(
            success=False,
            authority=authority,
            error_code="MANUAL_REFUND",
            error_message=(
                "Zarinpal does not support automated refunds via API. "
                "Please process the refund through the Zarinpal merchant dashboard."
            ),
        )
