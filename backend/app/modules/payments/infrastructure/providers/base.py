"""Abstract base for payment gateway providers."""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


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
