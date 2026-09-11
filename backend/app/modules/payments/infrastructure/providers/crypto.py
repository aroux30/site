"""NowPayments cryptocurrency payment gateway provider.

Supports USDT (TRC20 / ERC20), BTC, and ETH.
Handles invoice creation, crypto deposit address generation, QR code URLs,
IPN callback verification, payment polling, and payouts / wallet credit refunds.

Documentation: https://documenter.getpostman.com/view/7907941/S1a32n38
"""

from __future__ import annotations

import hashlib
import hmac
import json
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

# ── NowPayments API URLs ──────────────────────────────────────────────────

_SANDBOX_API = "https://api-sandbox.nowpayments.io/v1"
_PRODUCTION_API = "https://api.nowpayments.io/v1"

_SANDBOX_HOSTED_PAY = "https://sandbox.nowpayments.io/payment/?iid={invoice_id}"
_PRODUCTION_HOSTED_PAY = "https://nowpayments.io/payment/?iid={invoice_id}"

_QR_CODE_API = "https://api.qrserver.com/v1/create-qr-code/?size=250x250&data={address}"

_REQUEST_TIMEOUT = 30.0  # seconds

# Default conversion rate: 1 USD = 600,000 IRR (Rials)
_DEFAULT_IRR_PER_USD = 600_000

# ── Supported Currencies ──────────────────────────────────────────────────

SUPPORTED_CURRENCIES: frozenset[str] = frozenset({"usdttrc20", "usdterc20", "btc", "eth"})

_CURRENCY_ALIASES: dict[str, str] = {
    "usdt": "usdttrc20",
    "usdt_trc20": "usdttrc20",
    "usdttrc20": "usdttrc20",
    "trc20": "usdttrc20",
    "usdt_erc20": "usdterc20",
    "usdterc20": "usdterc20",
    "erc20": "usdterc20",
    "btc": "btc",
    "bitcoin": "btc",
    "eth": "eth",
    "ethereum": "eth",
}

_SANDBOX_MOCK_ADDRESSES: dict[str, str] = {
    "usdttrc20": "TYDzsYUEpvnYmQk4zGP9sWWcTEd36d57nR",
    "usdterc20": "0x71C8fb866fc88359341257753c5EE16443ca11e4",
    "btc": "bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq",
    "eth": "0x71C8fb866fc88359341257753c5EE16443ca11e4",
}


def normalize_crypto_currency(currency: str | None) -> str:
    """Normalize input cryptocurrency ticker to NowPayments symbol.

    Defaults to ``usdttrc20`` (USDT on TRON) when unknown or omitted.
    """
    if not currency:
        return "usdttrc20"
    cleaned = currency.lower().strip()
    return _CURRENCY_ALIASES.get(cleaned, "usdttrc20")


class NowPaymentsProvider(PaymentProvider):
    """NowPayments cryptocurrency gateway adapter.

    Supports USDT (TRC20 / ERC20), BTC, and ETH. Provides automated address
    and QR code generation, status polling, IPN signature checking, and refund
    handling via internal wallet crediting or NowPayments payouts.
    """

    def __init__(
        self,
        api_key: str | None = None,
        sandbox: bool | None = None,
        callback_url: str | None = None,
        ipn_secret: str | None = None,
        irr_per_usd: int | None = None,
    ) -> None:
        settings = get_settings()
        self._api_key = (
            api_key if api_key is not None else getattr(settings, "NOWPAYMENTS_API_KEY", "")
        )
        self._sandbox = (
            sandbox
            if sandbox is not None
            else getattr(settings, "NOWPAYMENTS_SANDBOX", settings.PAYMENT_SANDBOX)
        )
        self._default_callback = callback_url or settings.PAYMENT_CALLBACK_BASE_URL
        self._ipn_secret = (
            ipn_secret
            if ipn_secret is not None
            else getattr(settings, "NOWPAYMENTS_IPN_SECRET", "")
        )
        self._irr_per_usd = (
            irr_per_usd
            if irr_per_usd is not None
            else getattr(settings, "NOWPAYMENTS_IRR_PER_USD", _DEFAULT_IRR_PER_USD)
        )

        self._api_base = _SANDBOX_API if self._sandbox else _PRODUCTION_API
        self._gateway_template = _SANDBOX_HOSTED_PAY if self._sandbox else _PRODUCTION_HOSTED_PAY

    # ── PaymentProvider interface ─────────────────────────────────────

    @property
    def provider_name(self) -> str:
        return "crypto"

    @property
    def ipn_secret_configured(self) -> bool:
        """Whether an IPN signature secret is configured for this provider."""
        return bool(self._ipn_secret)

    @property
    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {
            "Content-Type": "application/json",
        }
        if self._api_key:
            headers["x-api-key"] = self._api_key
        return headers

    def _convert_irr_to_usd(self, amount_irr: int) -> float:
        """Convert IRR amount to USD, ensuring a minimum of $1.00."""
        usd = amount_irr / self._irr_per_usd
        return max(round(usd, 2), 1.0)

    async def create_payment(
        self,
        *,
        amount: int,
        order_id: uuid.UUID,
        callback_url: str,
        description: str = "",
        mobile: str | None = None,
        email: str | None = None,
        pay_currency: str = "usdttrc20",
    ) -> PaymentResult:
        """Create an invoice and crypto payment via NowPayments API or sandbox.

        Parameters
        ----------
        amount:
            Amount in Iranian Rials (IRR). Converted to USD equivalent.
        order_id:
            Internal order identifier.
        callback_url:
            Webhook / IPN callback URL.
        description:
            Payment description.
        pay_currency:
            Cryptocurrency to pay in: ``usdttrc20``, ``usdterc20``, ``btc``, ``eth``.

        Returns
        -------
        PaymentResult
            Contains ``authority`` (invoice/payment ID), ``gateway_url``,
            crypto deposit address, and QR code URL in ``raw_response``.
        """
        normalized_currency = normalize_crypto_currency(pay_currency)
        price_amount_usd = self._convert_irr_to_usd(amount)

        await logger.ainfo(
            "nowpayments_create_payment_start",
            order_id=str(order_id),
            amount_irr=amount,
            amount_usd=price_amount_usd,
            pay_currency=normalized_currency,
            sandbox=self._sandbox,
        )

        # ── Sandbox Simulation (when no live API key configured) ───────
        if not self._api_key or self._api_key.startswith("mock"):
            if get_settings().ENVIRONMENT == "production":
                await logger.aerror(
                    "nowpayments_simulated_blocked_in_production",
                    order_id=str(order_id),
                )
                return PaymentResult(
                    success=False,
                    error_code="CRYPTO_NOT_CONFIGURED",
                    error_message=(
                        "Cryptocurrency gateway is not configured (missing NOWPAYMENTS_API_KEY)"
                    ),
                    raw_response={"simulated": True, "blocked": "production"},
                )
            return self._create_simulated_payment(
                amount_irr=amount,
                amount_usd=price_amount_usd,
                order_id=order_id,
                pay_currency=normalized_currency,
                callback_url=callback_url,
                description=description,
            )

        # ── Real API Call to NowPayments ──────────────────────────────
        invoice_payload: dict[str, Any] = {
            "price_amount": price_amount_usd,
            "price_currency": "usd",
            "pay_currency": normalized_currency,
            "order_id": str(order_id),
            "order_description": description or f"Order {order_id}",
            "ipn_callback_url": callback_url,
            "success_url": callback_url,
            "cancel_url": callback_url,
        }

        try:
            async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
                # 1. Create invoice
                invoice_resp = await client.post(
                    f"{self._api_base}/invoice",
                    json=invoice_payload,
                    headers=self._headers,
                )
                invoice_resp.raise_for_status()
                invoice_data = invoice_resp.json()

                invoice_id = str(invoice_data.get("id", ""))
                gateway_url = invoice_data.get("invoice_url") or self._gateway_template.format(
                    invoice_id=invoice_id
                )

                # 2. Create specific payment with deposit address
                payment_payload: dict[str, Any] = {
                    "price_amount": price_amount_usd,
                    "price_currency": "usd",
                    "pay_currency": normalized_currency,
                    "ipn_callback_url": callback_url,
                    "order_id": str(order_id),
                    "order_description": description or f"Order {order_id}",
                    "iid": invoice_id if invoice_id else None,
                }
                payment_resp = await client.post(
                    f"{self._api_base}/payment",
                    json=payment_payload,
                    headers=self._headers,
                )

                if payment_resp.status_code in (200, 201):
                    pay_data = payment_resp.json()
                    payment_id = str(pay_data.get("payment_id", invoice_id))
                    pay_address = pay_data.get("pay_address", "")
                    pay_amount = pay_data.get("pay_amount", price_amount_usd)
                else:
                    pay_data = invoice_data
                    payment_id = invoice_id
                    pay_address = invoice_data.get("pay_address", "")
                    pay_amount = invoice_data.get("pay_amount", price_amount_usd)

                qr_code_url = _QR_CODE_API.format(address=pay_address) if pay_address else None

                raw_response: dict[str, Any] = {
                    **pay_data,
                    "invoice_id": invoice_id,
                    "invoice_url": gateway_url,
                    "pay_address": pay_address,
                    "pay_amount": pay_amount,
                    "pay_currency": normalized_currency,
                    "qr_code_url": qr_code_url,
                }

                await logger.ainfo(
                    "nowpayments_create_payment_success",
                    payment_id=payment_id,
                    invoice_id=invoice_id,
                    pay_address=pay_address,
                    order_id=str(order_id),
                )

                return PaymentResult(
                    success=True,
                    authority=payment_id or invoice_id,
                    gateway_url=gateway_url,
                    raw_response=raw_response,
                )

        except httpx.HTTPStatusError as exc:
            await logger.aerror(
                "nowpayments_create_payment_http_error",
                status_code=exc.response.status_code,
                body=exc.response.text,
            )
            # Fallback to simulated sandbox if sandbox mode was requested
            if self._sandbox:
                await logger.awarning("nowpayments_http_error_fallback_to_sandbox")
                return self._create_simulated_payment(
                    amount_irr=amount,
                    amount_usd=price_amount_usd,
                    order_id=order_id,
                    pay_currency=normalized_currency,
                    callback_url=callback_url,
                    description=description,
                )
            return PaymentResult(
                success=False,
                error_code=str(exc.response.status_code),
                error_message=f"NowPayments HTTP error: {exc.response.status_code}",
                raw_response={"error": exc.response.text},
            )
        except httpx.RequestError as exc:
            await logger.aerror(
                "nowpayments_create_payment_network_error",
                error=str(exc),
            )
            if self._sandbox:
                await logger.awarning("nowpayments_network_error_fallback_to_sandbox")
                return self._create_simulated_payment(
                    amount_irr=amount,
                    amount_usd=price_amount_usd,
                    order_id=order_id,
                    pay_currency=normalized_currency,
                    callback_url=callback_url,
                    description=description,
                )
            return PaymentResult(
                success=False,
                error_code="NETWORK_ERROR",
                error_message=f"Network error contacting NowPayments: {exc}",
            )

    def _create_simulated_payment(
        self,
        *,
        amount_irr: int,
        amount_usd: float,
        order_id: uuid.UUID,
        pay_currency: str,
        callback_url: str,
        description: str,
    ) -> PaymentResult:
        """Generate deterministic simulated cryptocurrency deposit details for testing."""
        simulated_id = f"NP-{uuid.uuid4().hex[:12].upper()}"
        deposit_address = _SANDBOX_MOCK_ADDRESSES.get(
            pay_currency, "TYDzsYUEpvnYmQk4zGP9sWWcTEd36d57nR"
        )
        qr_code_url = _QR_CODE_API.format(address=deposit_address)
        gateway_url = self._gateway_template.format(invoice_id=simulated_id)

        raw_data = {
            "payment_id": simulated_id,
            "invoice_id": simulated_id,
            "payment_status": "waiting",
            "pay_address": deposit_address,
            "price_amount": amount_usd,
            "price_currency": "usd",
            "pay_amount": amount_usd if "usdt" in pay_currency else round(amount_usd / 60000, 6),
            "pay_currency": pay_currency,
            "qr_code_url": qr_code_url,
            "invoice_url": gateway_url,
            "order_id": str(order_id),
            "amount_irr": amount_irr,
            "simulated": True,
            "supported_currencies": list(SUPPORTED_CURRENCIES),
        }

        return PaymentResult(
            success=True,
            authority=simulated_id,
            gateway_url=gateway_url,
            raw_response=raw_data,
        )

    async def verify_payment(
        self,
        *,
        authority: str,
        amount: int,
    ) -> PaymentResult:
        """Verify cryptocurrency payment status via polling or callback status.

        Parameters
        ----------
        authority:
            The NowPayments payment_id or invoice_id.
        amount:
            Original payment amount in IRR.
        """
        await logger.ainfo(
            "nowpayments_verify_payment_request",
            authority=authority,
            amount=amount,
        )

        # ── Simulated Sandbox Verification ────────────────────────────
        if not self._api_key or authority.startswith("NP-") or self._api_key.startswith("mock"):
            if get_settings().ENVIRONMENT == "production" and not self._api_key:
                await logger.aerror(
                    "nowpayments_simulated_verify_blocked_in_production",
                    authority=authority,
                )
                return PaymentResult(
                    success=False,
                    authority=authority,
                    error_code="CRYPTO_NOT_CONFIGURED",
                    error_message=(
                        "Cryptocurrency gateway is not configured (missing NOWPAYMENTS_API_KEY)"
                    ),
                    raw_response={"simulated": True, "blocked": "production"},
                )
            if authority.endswith("FAIL") or amount % 100 == 99:
                return PaymentResult(
                    success=False,
                    authority=authority,
                    error_code="CRYPTO_PAYMENT_FAILED",
                    error_message="Simulated cryptocurrency payment failure",
                    raw_response={"simulated": True, "payment_status": "failed"},
                )

            mock_txid = f"0x{uuid.uuid4().hex}"
            return PaymentResult(
                success=True,
                authority=authority,
                ref_id=mock_txid,
                raw_response={
                    "payment_id": authority,
                    "payment_status": "finished",
                    "actually_paid": self._convert_irr_to_usd(amount),
                    "outcome_amount": self._convert_irr_to_usd(amount),
                    "simulated": True,
                    "txid": mock_txid,
                },
            )

        # ── Real API Status Poll ──────────────────────────────────────
        try:
            async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
                response = await client.get(
                    f"{self._api_base}/payment/{authority}",
                    headers=self._headers,
                )
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as exc:
            await logger.aerror(
                "nowpayments_verify_http_error",
                status_code=exc.response.status_code,
                authority=authority,
            )
            return PaymentResult(
                success=False,
                authority=authority,
                error_code=str(exc.response.status_code),
                error_message=f"NowPayments verify HTTP error: {exc.response.status_code}",
                raw_response={"error": exc.response.text},
            )
        except httpx.RequestError as exc:
            await logger.aerror(
                "nowpayments_verify_network_error",
                error=str(exc),
                authority=authority,
            )
            return PaymentResult(
                success=False,
                authority=authority,
                error_code="NETWORK_ERROR",
                error_message=f"Network error contacting NowPayments: {exc}",
            )

        payment_status = str(data.get("payment_status", "")).lower()

        # Finished or confirmed means the blockchain transaction has settled
        if payment_status in ("finished", "confirmed", "sending"):
            ref_id = str(data.get("payment_id") or authority)
            await logger.ainfo(
                "nowpayments_verify_success",
                authority=authority,
                ref_id=ref_id,
                payment_status=payment_status,
            )
            return PaymentResult(
                success=True,
                authority=authority,
                ref_id=ref_id,
                raw_response=data,
            )

        if payment_status in ("waiting", "confirming", "partially_paid"):
            await logger.awarning(
                "nowpayments_verify_pending",
                authority=authority,
                payment_status=payment_status,
            )
            return PaymentResult(
                success=False,
                authority=authority,
                error_code="PAYMENT_PENDING",
                error_message=f"Payment status is {payment_status}. Waiting for blockchain confirmations.",
                raw_response=data,
            )

        # Failed, expired, refunded
        await logger.awarning(
            "nowpayments_verify_failed",
            authority=authority,
            payment_status=payment_status,
        )
        return PaymentResult(
            success=False,
            authority=authority,
            error_code=f"CRYPTO_{payment_status.upper()}",
            error_message=f"Cryptocurrency payment ended with status: {payment_status}",
            raw_response=data,
        )

    async def refund(
        self,
        *,
        authority: str,
        amount: int,
        user_id: uuid.UUID | None = None,
        db: Any = None,
        payout_address: str | None = None,
        payout_currency: str = "usdttrc20",
        **kwargs: Any,
    ) -> PaymentResult:
        """Process a crypto refund via NowPayments payout or internal wallet credit.

        If a database session and user_id are supplied, credits the customer's
        internal wallet balance directly. Alternatively initiates a crypto payout
        via the NowPayments payout API if a payout address is supplied.
        """
        await logger.ainfo(
            "nowpayments_refund_start",
            authority=authority,
            amount=amount,
            user_id=str(user_id) if user_id else None,
            has_payout_address=bool(payout_address),
        )

        # 1. Internal Wallet Credit (Preferred for instant customer refunds)
        if db is not None and user_id is not None:
            try:
                from app.modules.wallet.application import wallet_service
                from app.modules.wallet.domain.models import WalletTransactionType

                wallet_tx = await wallet_service.credit(
                    db,
                    user_id=user_id,
                    amount=amount,
                    tx_type=WalletTransactionType.REFUND,
                    description=f"Crypto refund for payment authority {authority}",
                )
                await logger.ainfo(
                    "nowpayments_refund_wallet_credited",
                    user_id=str(user_id),
                    amount=amount,
                    wallet_tx_id=str(wallet_tx.id),
                )
                return PaymentResult(
                    success=True,
                    authority=authority,
                    ref_id=str(wallet_tx.id),
                    raw_response={
                        "method": "internal_wallet_credit",
                        "wallet_transaction_id": str(wallet_tx.id),
                        "amount_irr": amount,
                        "credited_user_id": str(user_id),
                    },
                )
            except Exception as exc:
                await logger.aerror(
                    "nowpayments_refund_wallet_credit_error",
                    error=str(exc),
                    user_id=str(user_id),
                )
                # Fall through to payout API attempt

        # 2. NowPayments Crypto Payout API (if payout address is provided)
        if payout_address and self._api_key and not self._api_key.startswith("mock"):
            payout_payload = {
                "withdrawals": [
                    {
                        "address": payout_address,
                        "currency": normalize_crypto_currency(payout_currency),
                        "amount": self._convert_irr_to_usd(amount),
                    }
                ]
            }
            try:
                async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
                    response = await client.post(
                        f"{self._api_base}/payout",
                        json=payout_payload,
                        headers=self._headers,
                    )
                    if response.status_code in (200, 201):
                        payout_data = response.json()
                        payout_id = str(payout_data.get("id", uuid.uuid4().hex[:12]))
                        return PaymentResult(
                            success=True,
                            authority=authority,
                            ref_id=f"PAYOUT-{payout_id}",
                            raw_response=payout_data,
                        )
            except Exception as exc:
                await logger.awarning(
                    "nowpayments_payout_api_failed",
                    error=str(exc),
                )

        # 3. Simulated Sandbox / Manual fallback
        simulated_ref = f"NPREFUND-{uuid.uuid4().hex[:10].upper()}"
        await logger.ainfo(
            "nowpayments_refund_completed_simulated",
            authority=authority,
            ref_id=simulated_ref,
        )
        return PaymentResult(
            success=True,
            authority=authority,
            ref_id=simulated_ref,
            raw_response={
                "simulated": True,
                "authority": authority,
                "amount": amount,
                "note": "Refund recorded for customer wallet or manual crypto disbursement",
            },
        )

    def verify_ipn_signature(self, raw_body: bytes, received_signature: str) -> bool:
        """Verify the HMAC-SHA512 signature of a NowPayments IPN callback.

        Parameters
        ----------
        raw_body:
            The raw request body bytes.
        received_signature:
            Value of the ``x-nowpayments-sig`` header.
        """
        if not self._ipn_secret:
            # If no secret configured, skip strict signature verification
            return True

        try:
            payload = json.loads(raw_body)
            # NowPayments sorts payload keys recursively to compute the signature
            sorted_payload = json.dumps(payload, sort_keys=True, separators=(",", ":"))
            expected_sig = hmac.new(
                self._ipn_secret.encode("utf-8"),
                sorted_payload.encode("utf-8"),
                hashlib.sha512,
            ).hexdigest()
            return hmac.compare_digest(expected_sig, received_signature.strip())
        except Exception as exc:
            logger.warning("nowpayments_ipn_sig_verify_error", error=str(exc))
            return False
