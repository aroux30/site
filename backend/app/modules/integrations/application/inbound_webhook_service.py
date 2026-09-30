"""Generic inbound webhook receiver.

One route per external system POSTs events *to us*, with HMAC verification,
optional IP allowlisting, and idempotent duplicate rejection. Payment-provider
callbacks are the special case that already existed; this is the general one
an ERP/accounting connector or a messaging gateway lands on.

Security posture
----------------
* **Verify before parse-you-act-on.** The signature is checked against the
  raw request body before any handler sees the payload; a failure records a
  ``rejected_signature`` delivery row and returns 401.
* **Secrets are encrypted at rest.** The signing key is stored as an
  AES-256-GCM envelope, not a hash: verifying an inbound HMAC needs the raw
  key back, so a one-way hash would make verification impossible.
* **Constant-time compare.** ``hmac.compare_digest`` — a byte-by-byte compare
  leaks the secret to anyone who can time the endpoint.
* **Every knock is logged**, including refusals: a receiver without a record
  of rejected calls cannot be audited.
* **Fail closed on config errors.** An endpoint whose secret is unreadable is
  not "open to everyone"; the call is refused and recorded.

Idempotency
-----------
The sender supplies an idempotency key (header or payload field). A repeat of
a key already seen for that endpoint returns the recorded verdict and stores
nothing new — an external system retrying a POST it mistakenly thinks failed
cannot double-apply an effect.
"""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import secrets
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import select

from app.core.exceptions.handlers import ConflictError, NotFoundError, ValidationError
from app.modules.integrations.domain.webhooks import (
    InboundWebhookDelivery,
    InboundWebhookEndpoint,
    InboundWebhookStatus,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

#: Prefix on generated secrets, mirroring the reseller key convention so an
#: operator can tell at a glance what kind of credential they are looking at.
SECRET_PREFIX = "iwh_"

#: Payload event-type keys, in the order they are tried. External systems
#: disagree on the field name; accepting the common three beats making every
#: integrator add a mapping just to be received.
_EVENT_TYPE_KEYS = ("event_type", "event", "type")

#: Payload idempotency keys, same reasoning.
_IDEMPOTENCY_KEYS = ("idempotency_key", "idempotencyKey", "event_id", "id")


def generate_secret() -> str:
    """A fresh inbound-webhook secret. Returned once; only its ciphertext
    is persisted."""
    return SECRET_PREFIX + secrets.token_urlsafe(32)


def encrypt_secret(secret: str) -> str:
    """Encrypt the raw secret for at-rest storage (AES-256-GCM envelope).

    Deliberately not a hash: signature verification needs the raw key back.
    """
    from app.modules.inventory.application.crypto_service import encrypt_pin

    return encrypt_pin(secret)


def sign_payload(secret: str, body: bytes) -> str:
    """HMAC-SHA256 signature in the same format the outbound side emits.

    Sharing the format means a partner integrating with us writes one signer
    and uses it in both directions.
    """
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def verify_signature(secret: str, body: bytes, provided: str | None) -> bool:
    """Constant-time verification of an incoming signature.

    Accepts the value with or without the ``sha256=`` prefix: some HTTP
    clients (and every hand-rolled curl) drop it, and rejecting those teaches
    integrators nothing except to hate the API.
    """
    if not provided:
        return False
    expected = sign_payload(secret, body)
    candidate = provided.strip()
    if not candidate.startswith("sha256="):
        candidate = "sha256=" + candidate
    return hmac.compare_digest(expected, candidate)


def is_ip_allowed(source_ip: str | None, whitelist: list[str] | None) -> bool:
    """True when the caller's IP is permitted by the endpoint.

    An empty/absent whitelist means "no IP restriction" — the signature is
    then the only gate, which is the documented default. A malformed entry in
    the whitelist is ignored rather than widening access; an unparseable
    source IP against a non-empty whitelist is refused.
    """
    if not whitelist:
        return True
    if not source_ip:
        return False
    try:
        address = ipaddress.ip_address(source_ip)
    except ValueError:
        return False
    for entry in whitelist:
        try:
            network = ipaddress.ip_network(entry, strict=False)
        except ValueError:
            continue
        if address in network:
            return True
    return False


def _extract(payload: dict[str, Any] | None, keys: tuple[str, ...]) -> str | None:
    """First present, non-empty string among ``keys``. Pure."""
    if not payload:
        return None
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, int):
            return str(value)
    return None


async def create_endpoint(
    db: AsyncSession,
    *,
    name: str,
    description: str | None = None,
    ip_whitelist: list[str] | None = None,
) -> tuple[InboundWebhookEndpoint, str]:
    """Create a receiver. Returns ``(endpoint, raw_secret)``.

    The raw secret is returned exactly once, here; only its AES-GCM
    ciphertext is persisted.
    """
    clean_name = (name or "").strip()
    if not clean_name:
        raise ValidationError(
            "نام گیرنده الزامی است", error_code="INBOUND_NAME_REQUIRED"
        )
    existing = (
        await db.execute(
            select(InboundWebhookEndpoint.id).where(
                InboundWebhookEndpoint.name == clean_name
            )
        )
    ).first()
    if existing is not None:
        raise ConflictError(
            f"گیرنده‌ای با نام «{clean_name}» از قبل وجود دارد",
            error_code="INBOUND_NAME_TAKEN",
        )

    secret = generate_secret()
    endpoint = InboundWebhookEndpoint(
        name=clean_name,
        description=description,
        secret_encrypted=encrypt_secret(secret),
        ip_whitelist=ip_whitelist,
        is_active=True,
    )
    db.add(endpoint)
    await db.flush()
    await logger.ainfo(
        "inbound_endpoint_created", endpoint_id=str(endpoint.id), name=clean_name
    )
    return endpoint, secret


async def rotate_secret(
    db: AsyncSession, *, endpoint_id: uuid.UUID
) -> tuple[InboundWebhookEndpoint, str]:
    """Issue a new secret. The old one stops working immediately."""
    endpoint = await db.get(InboundWebhookEndpoint, endpoint_id)
    if endpoint is None:
        raise NotFoundError("InboundWebhookEndpoint")
    secret = generate_secret()
    endpoint.secret_encrypted = encrypt_secret(secret)
    await db.flush()
    await logger.ainfo("inbound_endpoint_secret_rotated", endpoint_id=str(endpoint_id))
    return endpoint, secret


async def receive(
    db: AsyncSession,
    *,
    endpoint_name: str,
    raw_body: bytes,
    signature: str | None,
    payload: dict[str, Any] | None,
    source_ip: str | None = None,
    user_agent: str | None = None,
    idempotency_key: str | None = None,
) -> tuple[InboundWebhookDelivery, bool]:
    """Receive one call. Returns ``(delivery, accepted)``.

    ``accepted`` is False for a duplicate — the caller should still answer
    200 (the sender must not retry forever), but no new effect is applied.
    A bad signature or disallowed IP raises before that point.
    """
    endpoint = (
        await db.execute(
            select(InboundWebhookEndpoint).where(
                InboundWebhookEndpoint.name == endpoint_name
            )
        )
    ).scalar_one_or_none()
    if endpoint is None or not endpoint.is_active:
        # Unknown endpoint: 404 without recording — there is no receiver row
        # to hang the delivery on, and an unauthenticated caller must not be
        # able to write arbitrary rows into the audit table.
        raise NotFoundError("InboundWebhookEndpoint")

    # Signature first: nothing about the payload is trusted before this.
    # Fail closed if the stored secret cannot be decrypted (a rotated-away
    # encryption key, a corrupted row): an unverifiable receiver is not an
    # open one.
    from app.modules.inventory.application.crypto_service import decrypt_pin

    try:
        raw_secret = decrypt_pin(endpoint.secret_encrypted)
    except Exception:
        await _record(
            db,
            endpoint,
            status=InboundWebhookStatus.FAILED,
            payload=payload,
            idempotency_key=idempotency_key,
            source_ip=source_ip,
            user_agent=user_agent,
            error="secret undecryptable — receiver misconfigured",
        )
        raise ConflictError(
            "گیرنده پیکربندی نشده است", error_code="INBOUND_SECRET_UNAVAILABLE"
        ) from None
    if not raw_secret:
        await _record(
            db,
            endpoint,
            status=InboundWebhookStatus.FAILED,
            payload=payload,
            idempotency_key=idempotency_key,
            source_ip=source_ip,
            user_agent=user_agent,
            error="secret unavailable — receiver misconfigured",
        )
        raise ConflictError(
            "گیرنده پیکربندی نشده است", error_code="INBOUND_SECRET_UNAVAILABLE"
        )

    if not verify_signature(raw_secret, raw_body, signature):
        await _record(
            db,
            endpoint,
            status=InboundWebhookStatus.REJECTED_SIGNATURE,
            payload=payload,
            idempotency_key=idempotency_key,
            source_ip=source_ip,
            user_agent=user_agent,
            error="signature mismatch",
        )
        raise ValidationError(
            "امضای درخواست نامعتبر است", error_code="INBOUND_BAD_SIGNATURE"
        )

    if not is_ip_allowed(source_ip, endpoint.ip_whitelist):
        await _record(
            db,
            endpoint,
            status=InboundWebhookStatus.REJECTED_SIGNATURE,
            payload=payload,
            idempotency_key=idempotency_key,
            source_ip=source_ip,
            user_agent=user_agent,
            error=f"ip not allowed: {source_ip}",
        )
        raise ValidationError(
            "آدرس IP مجاز نیست", error_code="INBOUND_IP_NOT_ALLOWED"
        )

    event_type = _extract(payload, _EVENT_TYPE_KEYS)
    key = idempotency_key or _extract(payload, _IDEMPOTENCY_KEYS)

    if key:
        previous = (
            await db.execute(
                select(InboundWebhookDelivery).where(
                    InboundWebhookDelivery.endpoint_id == endpoint.id,
                    InboundWebhookDelivery.idempotency_key == key,
                    InboundWebhookDelivery.status != InboundWebhookStatus.FAILED,
                )
            )
        ).scalar_one_or_none()
        if previous is not None:
            # A retry of a call we already accepted: answer with the recorded
            # verdict, write nothing. This is what stops an external system's
            # retry loop from double-applying an effect.
            await logger.ainfo(
                "inbound_duplicate_ignored",
                endpoint=endpoint.name,
                idempotency_key=key,
            )
            return previous, False

    delivery = await _record(
        db,
        endpoint,
        status=InboundWebhookStatus.VERIFIED,
        payload=payload,
        idempotency_key=key,
        source_ip=source_ip,
        user_agent=user_agent,
        event_type=event_type,
    )
    endpoint.last_received_at = datetime.now(UTC)
    endpoint.total_received = (endpoint.total_received or 0) + 1
    await db.flush()
    await logger.ainfo(
        "inbound_webhook_verified",
        endpoint=endpoint.name,
        event_type=event_type,
        delivery_id=str(delivery.id),
    )
    return delivery, True


async def _record(
    db: AsyncSession,
    endpoint: InboundWebhookEndpoint,
    *,
    status: InboundWebhookStatus,
    payload: dict[str, Any] | None,
    idempotency_key: str | None,
    source_ip: str | None,
    user_agent: str | None,
    error: str | None = None,
    event_type: str | None = None,
) -> InboundWebhookDelivery:
    """Write one delivery row and flush. Shared by every verdict path."""
    delivery = InboundWebhookDelivery(
        endpoint_id=endpoint.id,
        event_type=event_type,
        status=status,
        payload=payload,
        idempotency_key=idempotency_key,
        source_ip=source_ip,
        user_agent=user_agent,
        error=error,
        received_at=datetime.now(UTC),
    )
    db.add(delivery)
    await db.flush()
    return delivery


async def mark_processed(
    db: AsyncSession,
    *,
    delivery_id: uuid.UUID,
    error: str | None = None,
) -> InboundWebhookDelivery:
    """Record the outcome of handling a verified delivery.

    The receive path deliberately does *not* apply effects: an integrator's
    handler decides what an event means, and marking the receipt processed is
    its way of saying so. An error here is recorded, never raised — the event
    was already accepted and must not be lost to a handler bug.
    """
    delivery = await db.get(InboundWebhookDelivery, delivery_id)
    if delivery is None:
        raise NotFoundError("InboundWebhookDelivery")
    delivery.status = (
        InboundWebhookStatus.PROCESSED if not error else InboundWebhookStatus.FAILED
    )
    delivery.error = error
    delivery.processed_at = datetime.now(UTC)
    await db.flush()
    return delivery


async def list_deliveries(
    db: AsyncSession,
    *,
    endpoint_name: str | None = None,
    status: InboundWebhookStatus | None = None,
    limit: int = 100,
) -> list[InboundWebhookDelivery]:
    """Recent deliveries, newest first, for the admin receiver log."""
    stmt = select(InboundWebhookDelivery).order_by(
        InboundWebhookDelivery.received_at.desc()
    ).limit(limit)
    if endpoint_name:
        endpoint = (
            await db.execute(
                select(InboundWebhookEndpoint.id).where(
                    InboundWebhookEndpoint.name == endpoint_name
                )
            )
        ).scalar_one_or_none()
        if endpoint is None:
            return []
        stmt = stmt.where(InboundWebhookDelivery.endpoint_id == endpoint)
    if status is not None:
        stmt = stmt.where(InboundWebhookDelivery.status == status)
    return list((await db.execute(stmt)).scalars().all())


async def list_endpoints(
    db: AsyncSession,
) -> list[InboundWebhookEndpoint]:
    """All receivers, newest first."""
    rows = (
        await db.execute(
            select(InboundWebhookEndpoint).order_by(
                InboundWebhookEndpoint.created_at.desc()
            )
        )
    ).scalars().all()
    return list(rows)
