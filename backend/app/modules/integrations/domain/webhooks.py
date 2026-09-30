"""Outbound webhook endpoint and delivery domain models.

Endpoints subscribe to content events; deliveries are the per-endpoint
pending/success/failed queue rows drained by the Celery beat task.
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
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import BaseModel

MAX_ATTEMPTS = 8
RETRY_BACKOFF_BASE_SECONDS = 60
DELIVERY_TIMEOUT_SECONDS = 10


class WebhookDeliveryStatus(str, enum.Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"


class WebhookEndpoint(BaseModel):
    """A subscribed external URL plus its HMAC signing secret."""

    __tablename__ = "webhook_endpoints"

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    url: Mapped[str] = mapped_column(String(1000), nullable=False)
    events: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default=text("'[]'"))
    secret: Mapped[str | None] = mapped_column(String(200), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False, server_default=text("true")
    )

    def __repr__(self) -> str:
        return f"<WebhookEndpoint(name={self.name}, url={self.url})>"


class WebhookDelivery(BaseModel):
    """One event delivery attempt queue row for one endpoint."""

    __tablename__ = "webhook_deliveries"
    __table_args__ = (
        Index("ix_webhook_deliveries_endpoint_id", "endpoint_id"),
        Index("ix_webhook_deliveries_status_next", "status", "next_attempt_at"),
    )

    endpoint_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("webhook_endpoints.id", ondelete="CASCADE"),
        nullable=False,
    )
    event: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[WebhookDeliveryStatus] = mapped_column(
        Enum(WebhookDeliveryStatus, name="webhook_delivery_status_enum", native_enum=False),
        default=WebhookDeliveryStatus.PENDING,
        nullable=False,
        server_default=text("'PENDING'::character varying"),
    )
    attempts: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, server_default=text("0")
    )
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow,
        server_default=text("now()"),
    )
    response_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<WebhookDelivery(event={self.event}, status={self.status}, attempts={self.attempts})>"
# ── Generic inbound webhook receiver (ERP feature #4, P1) ──────────────────


class InboundWebhookStatus(str, enum.Enum):
    """Disposition of one received inbound webhook call."""

    RECEIVED = "received"
    VERIFIED = "verified"
    REJECTED_SIGNATURE = "rejected_signature"
    REJECTED_DUPLICATE = "rejected_duplicate"
    PROCESSED = "processed"
    FAILED = "failed"


class InboundWebhookEndpoint(BaseModel):
    """A generic inbound webhook receiver for external systems.

    The platform already had outbound webhooks (our system notifies partners)
    and payment-provider callbacks (special-cased per gateway). This is the
    missing generalisation: one row per external system that wants to POST
    events *to us* — an ERP/accounting connector, a DMS, a WhatsApp gateway —
    with HMAC verification, IP allowlisting and per-receiver idempotency.

    The signing secret is stored *encrypted* (AES-256-GCM, the
    ``crypto_service`` envelope), not hashed: verifying an inbound HMAC
    requires the raw key, so a one-way hash would make verification
    impossible. It is never returned after creation except via rotation.
    """

    __tablename__ = "inbound_webhook_endpoints"
    __table_args__ = (
        Index("ix_inbound_webhook_endpoints_name", "name"),
        Index("ix_inbound_webhook_endpoints_is_active", "is_active"),
    )

    #: Stable machine name, e.g. "accounting_software".
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: AES-256-GCM ciphertext of the signing secret (the platform's
    #: ``crypto_service`` envelope). Unlike a password this must stay
    #: *recoverable*: verifying an inbound HMAC needs the raw key, so a
    #: one-way hash would make signature checks impossible.
    secret_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    #: Optional IP allowlist (CIDR or literal). Empty list = no IP restriction.
    ip_whitelist: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False, server_default=text("true")
    )
    last_received_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    total_received: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class InboundWebhookDelivery(BaseModel):
    """One received call, with the verification verdict.

    Keeping every delivery — including the rejected ones — is what makes the
    receiver a *security surface with an audit trail* rather than a black
    box: an operator can see who knocked with a bad signature and when.
    """

    __tablename__ = "inbound_webhook_deliveries"
    __table_args__ = (
        Index("ix_inbound_webhook_deliveries_endpoint_id", "endpoint_id"),
        Index("ix_inbound_webhook_deliveries_status", "status"),
        Index("ix_inbound_webhook_deliveries_received_at", "received_at"),
        Index("ix_inbound_webhook_deliveries_idempotency", "idempotency_key"),
    )

    endpoint_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("inbound_webhook_endpoints.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[InboundWebhookStatus] = mapped_column(
        Enum(InboundWebhookStatus, name="inbound_webhook_status_enum", native_enum=False),
        default=InboundWebhookStatus.RECEIVED,
        nullable=False,
    )
    #: Raw payload (JSON-safe) — what the sender claims happened.
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    #: Sender-supplied idempotency key; drives duplicate rejection.
    idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    #: HTTP request metadata for the security review.
    source_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(300), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
