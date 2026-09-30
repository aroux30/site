"""Abstract base for payment gateway providers."""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class TokenizationResult:
    """Result of a gateway tokenization (card-on-file) operation.

    ``token`` is the gateway's own opaque handle. It is **never** a PAN: no
    implementation may return a card number here, and the persistence layer
    (``SavedPaymentMethod``) stores this value plus display-only metadata.

    Attributes
    ----------
    success:
        Whether the gateway issued a usable token.
    token:
        The gateway token (opaque, gateway-scoped, meaningless without the
        merchant credentials).
    masked_pan:
        Display metadata echoed by the gateway (e.g. ``6037-****-****-1234``).
    last4:
        Last four digits, for the account page.
    expiry_jalali:
        Jalali expiry *label* (``"1407/03"``) as a display string only.
    card_holder_name / bank_name:
        Optional display metadata.
    error_code / error_message:
        Failure detail.
    raw_response:
        Full gateway response for audit (must be PAN-free by provider contract).
    """

    success: bool
    token: str | None = None
    masked_pan: str | None = None
    last4: str | None = None
    expiry_jalali: str | None = None
    card_holder_name: str | None = None
    bank_name: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    raw_response: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PaymentResult:
    """Standardised result returned by every payment provider operation.

    Attributes
    ----------
    success:
        Whether the operation succeeded at the gateway level.
    authority:
        Gateway-specific token / reference used to redirect the user.
    gateway_url:
        Full URL the client should be redirected to for payment.
    ref_id:
        Provider reference / transaction ID after successful verification.
    card_pan:
        Masked card number returned by the gateway (if available).
    error_code:
        Provider-specific error code on failure.
    error_message:
        Human-readable error description on failure.
    raw_response:
        The full raw response from the gateway for audit / debugging.
    """

    success: bool
    authority: str | None = None
    gateway_url: str | None = None
    ref_id: str | None = None
    card_pan: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    raw_response: dict[str, Any] = field(default_factory=dict)


class PaymentProvider(ABC):
    """Contract that every payment gateway adapter must implement."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return a slug identifying this provider (e.g. ``zarinpal``)."""

    @abstractmethod
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
        """Initiate a payment at the gateway.

        Parameters
        ----------
        amount:
            Payment amount in **IRR** (Rials).
        order_id:
            Internal order identifier (forwarded as metadata).
        callback_url:
            URL the gateway should redirect to after user payment.
        description:
            Human-readable purchase description shown at gateway page.
        mobile:
            Buyer mobile (optional, some gateways pre-fill it).
        email:
            Buyer email (optional).

        Returns
        -------
        PaymentResult
            Contains ``authority`` and ``gateway_url`` on success.
        """

    @abstractmethod
    async def verify_payment(
        self,
        *,
        authority: str,
        amount: int,
    ) -> PaymentResult:
        """Verify / settle a payment after the user returns from the gateway.

        Parameters
        ----------
        authority:
            The authority / token the gateway returned during ``create_payment``.
        amount:
            The original amount (in IRR) – the gateway verifies it matches.

        Returns
        -------
        PaymentResult
            Contains ``ref_id`` on success.
        """

    @abstractmethod
    async def refund(
        self,
        *,
        authority: str,
        amount: int,
    ) -> PaymentResult:
        """Request a refund through the payment gateway.

        Parameters
        ----------
        authority:
            The authority / transaction reference to refund.
        amount:
            Refund amount in IRR.

        Returns
        -------
        PaymentResult
        """

    def verify_ipn_signature(self, raw_body: bytes, received_signature: str) -> bool:
        """Verify the signature of an asynchronous IPN/webhook callback.

        Only providers that support signed callbacks (e.g. NowPayments)
        implement real verification.  The default refuses to trust any
        callback so a provider without verification support can never be
        silently treated as verified.
        """
        raise NotImplementedError(
            f"{type(self).__name__} does not support IPN signature verification"
        )

    # ── Capabilities (payments upgrade v1) ─────────────────────────────
    #
    # Capabilities are declared as properties so a caller can branch without
    # catching NotImplementedError, and so the UI can hide an option the
    # gateway cannot serve. Every capability defaults to False / empty: a
    # provider that does not implement the corresponding method is therefore
    # never advertised to a customer. This is deliberate — a capability that
    # silently claimed support would offer a checkout option that always
    # fails at the gateway.

    @property
    def supports_tokenization(self) -> bool:
        """Whether this gateway can store a card and charge it later.

        Public Zarinpal v4 and IDPay v1.1 APIs have no card-on-file endpoint;
        their installment/credit products are merchant-contract features
        issued out of band. Both therefore return False and raise from
        :meth:`tokenize` / :meth:`charge_token`.
        """
        return False

    @property
    def supports_installments(self) -> bool:
        """Whether this gateway offers installment / credit purchases."""
        return False

    @property
    def installment_options_months(self) -> tuple[int, ...]:
        """Installment durations the gateway advertises (empty when unsupported)."""
        return ()

    async def tokenize(
        self,
        *,
        user_id: uuid.UUID,
        callback_url: str,
        mobile: str | None = None,
    ) -> TokenizationResult:
        """Register a card with the gateway and return an opaque token.

        Parameters
        ----------
        user_id:
            Internal user id, forwarded as metadata for correlation.
        callback_url:
            Where the gateway should return the customer after the card
            registration flow (the gateway hosts the card-entry page; this
            application must never see the PAN).
        mobile:
            Optional buyer mobile, some gateways pre-fill it.

        Raises
        ------
        NotImplementedError
            When :attr:`supports_tokenization` is False for this gateway.
        """
        raise NotImplementedError(
            f"{type(self).__name__} does not support card tokenization"
        )

    async def charge_token(
        self,
        *,
        token: str,
        amount: int,
        order_id: uuid.UUID,
        description: str = "",
    ) -> PaymentResult:
        """Charge a previously tokenized card without customer interaction.

        This is the entry point a future recurring/subscription service calls;
        it must remain side-effect-idempotent at the gateway level (pass a
        gateway-visible reference such as ``order_id`` or a generated
        authority so a retried charge is not billed twice).

        Parameters
        ----------
        token:
            A token previously returned by :meth:`tokenize`.
        amount:
            Amount in IRR.
        order_id:
            Internal reference, forwarded as metadata.

        Raises
        ------
        NotImplementedError
            When :attr:`supports_tokenization` is False for this gateway.
        """
        raise NotImplementedError(
            f"{type(self).__name__} does not support tokenized charges"
        )

    async def revoke_token(self, *, token: str) -> bool:
        """Ask the gateway to invalidate a stored token.

        Best-effort: returning False means the local row must still be marked
        revoked (the customer asked for the card to be removed), but the
        gateway may still hold a usable token and an operator should follow up.
        """
        return False
