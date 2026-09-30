"""Saved payment methods (tokenized cards) for the payments upgrade v1.

ERP benchmark gap analysis (feature #6 Payments, P1 — tokenized charges).

Design notes for a future recurring-charge service
--------------------------------------------------
This module deliberately keeps the *token* opaque and gateway-scoped so a
recurring/subscription engine (gap feature P1-4, hard-blocked on tokenization)
can later call :func:`app.modules.payments.application.tokenization_service.charge_token`
repeatedly without re-presenting the customer.

Security contract (non-negotiable):

* No PAN, no CVV, no expiry *number* is ever persisted. A saved method stores
  only the provider's own token plus display metadata (last 4 digits and the
  Jalali expiry *label* the gateway echoed back, both of which are safe to
  show a customer but useless for a charge).
* The token is meaningless without the merchant credentials, which stay in
  gateway configuration — a database dump alone cannot charge a card.
* Tokens are per ``(user_id, provider)``; deleting the row revokes the local
  reference, and providers that support remote revocation get a best-effort
  ``revoke_token`` call (see the tokenization service).

Gateway support status (see :mod:`app.modules.payments.infrastructure.providers.base`
for the capability contract):

===================  ==========================================================
Provider             Tokenization status
===================  ==========================================================
``mock``              Fully implemented (test/dev only; disabled in production)
``zarinpal``          NOT supported by the public v4 API — ``tokenize`` raises
                      ``NotImplementedError``. Zarinpal's "ZarinPal Plus" /
                      installment products are merchant-contract features that
                      issue their own tokens out of band; a real integration
                      must come from Zarinpal's merchant agreement, not this
                      code path.
``idpay``             NOT supported by the public v1.1 API — same reasoning.
``wallet``            Not applicable (internal balance, no card to tokenize).
``card_transfer``     Not applicable (offline bank transfer, no token).
``crypto``            Not applicable (on-chain, no card to tokenize).
===================  ==========================================================

The capability abstraction exists so the calling code is already written
against the interface that a gateway with a real tokenization product will
implement; until then the admin/customer UI simply hides the option for
providers that report ``supports_tokenization = False``.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import BaseModel


class TokenizationStatus(str, enum.Enum):
    """Lifecycle of a saved-method token, independent of the gateway's wording."""

    ACTIVE = "active"
    REVOKED = "revoked"
    EXPIRED = "expired"
    FAILED = "failed"


class SavedPaymentMethod(BaseModel):
    """A customer's tokenized card reference at one gateway.

    Only the provider token and non-sensitive display metadata are stored.
    ``token`` is the gateway's own opaque identifier (e.g. a mock provider
    token, or a real gateway token issued under a merchant tokenization
    contract); it is never a PAN.
    """

    __tablename__ = "saved_payment_methods"
    __table_args__ = (
        Index("ix_saved_payment_methods_user_id", "user_id"),
        Index("ix_saved_payment_methods_provider", "provider"),
        # The same gateway token must never be attached to two rows — a
        # re-tokenized card that returns the same token updates the existing
        # row instead of creating a duplicate the customer cannot delete.
        Index(
            "uq_saved_payment_methods_provider_token",
            "provider",
            "token",
            unique=True,
        ),
        # At most one default per user is enforced in the service inside the
        # same locked transaction; this partial index is the database-side
        # backstop against a racing double-default.
        Index(
            "uq_saved_payment_methods_one_default",
            "user_id",
            unique=True,
            postgresql_where=text("is_default = true AND is_active = true"),
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    # The gateway's opaque token. Never a PAN; never sent to the client.
    token: Mapped[str] = mapped_column(String(255), nullable=False)
    # Display metadata only. ``masked_pan`` is produced by the gateway (or by
    # ``mask_card_pan`` for gateways that echo a PAN once at tokenization) and
    # is what the customer sees in their account page.
    masked_pan: Mapped[str | None] = mapped_column(String(30), nullable=True)
    last4: Mapped[str | None] = mapped_column(String(4), nullable=True)
    # Jalali expiry as a display label ("1407/03"). The numeric month/year is
    # deliberately not stored separately: it adds no capability (charges are
    # authorized by the token) and a numeric expiry is PII-adjacent.
    expiry_jalali: Mapped[str | None] = mapped_column(String(10), nullable=True)
    card_holder_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    bank_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[TokenizationStatus] = mapped_column(
        Enum(
            TokenizationStatus,
            name="tokenization_status_enum",
            native_enum=False,
        ),
        default=TokenizationStatus.ACTIVE,
        nullable=False,
        # Enum member NAME: the column stores names (no values_callable), so a
        # lowercase server default would write a value the ORM cannot map back
        # to TokenizationStatus.ACTIVE on read.
        server_default=text("'ACTIVE'::character varying"),
    )
    is_default: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, server_default=text("false")
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False, server_default=text("true")
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Gateway echoes (fingerprint, brand, redirect hints) that are safe to
    # keep and useful for support. Never PAN/CVV.
    extra_data: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONB, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<SavedPaymentMethod(id={self.id}, user_id={self.user_id}, "
            f"provider={self.provider}, last4={self.last4}, active={self.is_active})>"
        )
