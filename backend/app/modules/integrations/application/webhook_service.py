"""Outbound webhooks (Strapi/WordPress-style): notify external systems of content events.

A webhook endpoint subscribes to a set of event names (e.g. ``page.published``).
``enqueue_event`` stores a pending delivery; a Celery beat task drains the queue
and POSTs an HMAC-SHA256-signed JSON payload to each subscribed URL. Deliveries
retry with exponential backoff and give up after ``MAX_ATTEMPTS``.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit

import structlog
from sqlalchemy import select

from app.core.exceptions.handlers import NotFoundError, ValidationError
from app.modules.integrations.application.url_safety import (
    resolve_pinned_ip,
    validate_public_url,
)
from app.modules.integrations.domain.webhooks import (
    DELIVERY_TIMEOUT_SECONDS,
    MAX_ATTEMPTS,
    RETRY_BACKOFF_BASE_SECONDS,
    WebhookDelivery,
    WebhookDeliveryStatus,
    WebhookEndpoint,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# Keep this in sync with the event names services actually emit.
EVENTS: frozenset[str] = frozenset(
    {
        "page.created",
        "page.updated",
        "page.published",
        "page.unpublished",
        "page.deleted",
        "post.created",
        "post.updated",
        "post.published",
        "post.deleted",
        "media.created",
        "media.deleted",
    }
)

_URL_RE = re.compile(r"^https?://[^\s/$.?#].[^\s]*$", re.IGNORECASE)


def _validate_events(events: list[str]) -> list[str]:
    unknown = sorted(set(events) - EVENTS)
    if unknown:
        raise ValidationError(f"رویدادهای ناشناخته: {', '.join(unknown)}")
    if not events:
        raise ValidationError("حداقل یک رویداد باید انتخاب شود")
    return sorted(set(events))


def _validate_url(url: str) -> str:
    url = url.strip()
    if not _URL_RE.match(url):
        raise ValidationError("نشانی وب‌هوک معتبر نیست (باید با http/https شروع شود)")
    # Shape is not enough: the delivery worker fetches this URL from inside
    # the cluster, so a syntactically valid http://169.254.169.254/ is an
    # SSRF payload. Reject internal targets here, where the operator can see
    # the error, and again at delivery time (see deliver_one).
    return validate_public_url(url)


async def create_endpoint(
    db: AsyncSession, *, name: str, url: str, events: list[str], secret: str | None = None
) -> WebhookEndpoint:
    endpoint = WebhookEndpoint(
        name=name.strip(),
        url=_validate_url(url),
        events=_validate_events(events),
        secret=secret,
    )
    db.add(endpoint)
    await db.flush()
    logger.info("webhook_endpoint_created", endpoint_id=str(endpoint.id), url=endpoint.url)
    return endpoint


async def update_endpoint(
    db: AsyncSession,
    endpoint_id: uuid.UUID,
    *,
    name: str | None = None,
    url: str | None = None,
    events: list[str] | None = None,
    is_active: bool | None = None,
    secret: str | None = None,
) -> WebhookEndpoint:
    endpoint = await db.get(WebhookEndpoint, endpoint_id)
    if not endpoint:
        raise NotFoundError("WebhookEndpoint", f"Webhook endpoint {endpoint_id} not found")
    if name is not None:
        endpoint.name = name.strip()
    if url is not None:
        endpoint.url = _validate_url(url)
    if events is not None:
        endpoint.events = _validate_events(events)
    if is_active is not None:
        endpoint.is_active = is_active
    if secret is not None:
        endpoint.secret = secret or None
    await db.flush()
    logger.info("webhook_endpoint_updated", endpoint_id=str(endpoint.id))
    return endpoint


async def list_endpoints(db: AsyncSession) -> list[WebhookEndpoint]:
    stmt = select(WebhookEndpoint).order_by(WebhookEndpoint.created_at.desc())
    return list((await db.execute(stmt)).scalars().all())


async def delete_endpoint(db: AsyncSession, endpoint_id: uuid.UUID) -> None:
    endpoint = await db.get(WebhookEndpoint, endpoint_id)
    if not endpoint:
        raise NotFoundError("WebhookEndpoint", f"Webhook endpoint {endpoint_id} not found")
    await db.delete(endpoint)
    await db.flush()
    logger.info("webhook_endpoint_deleted", endpoint_id=str(endpoint_id))


async def enqueue_event(
    db: AsyncSession, event: str, payload: dict[str, Any]
) -> int:
    """Create a pending delivery per active endpoint subscribed to ``event``.

    Returns the number of deliveries enqueued. Unknown events enqueue nothing
    (callers must not crash if an event name is retired).
    """
    if event not in EVENTS:
        logger.warning("webhook_unknown_event", event_name=event)
        return 0
    stmt = select(WebhookEndpoint).where(WebhookEndpoint.is_active.is_(True))
    endpoints = (await db.execute(stmt)).scalars().all()
    count = 0
    body = {"event": event, "timestamp": datetime.now(UTC).isoformat(), "data": payload}
    for endpoint in endpoints:
        if event not in (endpoint.events or []):
            continue
        db.add(
            WebhookDelivery(
                endpoint_id=endpoint.id,
                event=event,
                payload=body,
                status=WebhookDeliveryStatus.PENDING,
            )
        )
        count += 1
    await db.flush()
    if count:
        logger.info("webhook_event_enqueued", event_name=event, deliveries=count)
    return count


def sign_payload(secret: str | None, body: bytes) -> str:
    """HMAC-SHA256 signature header value (``sha256=<hex>``), empty without a secret."""
    if not secret:
        return ""
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


async def deliver_one(db: AsyncSession, delivery: WebhookDelivery) -> WebhookDelivery:
    """Attempt a single HTTP delivery, recording the outcome on the row.

    The row's status machine: pending → success, or pending → pending (retry
    scheduled) until ``attempts`` reaches ``MAX_ATTEMPTS`` → failed.
    """
    import httpx

    endpoint = await db.get(WebhookEndpoint, delivery.endpoint_id)
    if not endpoint:
        delivery.status = WebhookDeliveryStatus.FAILED
        delivery.last_error = "endpoint deleted"
        await db.flush()
        return delivery

    body = json.dumps(delivery.payload, ensure_ascii=False).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "site-webhooks/1.0",
        "X-Webhook-Event": delivery.event,
        "X-Webhook-Delivery": str(delivery.id),
    }
    signature = sign_payload(endpoint.secret, body)
    if signature:
        headers["X-Webhook-Signature"] = signature

    # Re-vet at delivery time: the URL passed validation when it was saved,
    # but DNS may since have been re-pointed at an internal address (rebinding).
    # A blocked host fails the delivery rather than being silently skipped, so
    # a rebinding attempt is visible in the delivery log.
    try:
        resolve_pinned_ip(urlsplit(endpoint.url).hostname or "")
    except ValidationError as exc:
        delivery.status = WebhookDeliveryStatus.FAILED
        delivery.last_error = f"blocked target: {exc}"[:500]
        await db.flush()
        logger.warning(
            "webhook_target_blocked",
            delivery_id=str(delivery.id),
            endpoint_id=str(endpoint.id),
        )
        return delivery

    delivery.attempts = (delivery.attempts or 0) + 1
    try:
        async with httpx.AsyncClient(timeout=DELIVERY_TIMEOUT_SECONDS) as client:
            response = await client.post(endpoint.url, content=body, headers=headers)
        delivery.response_status = response.status_code
        if 200 <= response.status_code < 300:
            delivery.status = WebhookDeliveryStatus.SUCCESS
            delivery.delivered_at = datetime.now(UTC)
            delivery.last_error = None
            logger.info(
                "webhook_delivered",
                delivery_id=str(delivery.id),
                status=response.status_code,
            )
            await db.flush()
            return delivery
        delivery.last_error = f"HTTP {response.status_code}"
    except Exception as exc:  # network errors, DNS, TLS, timeout
        delivery.last_error = str(exc)[:500]

    if delivery.attempts >= MAX_ATTEMPTS:
        delivery.status = WebhookDeliveryStatus.FAILED
        logger.warning(
            "webhook_delivery_failed",
            delivery_id=str(delivery.id),
            attempts=delivery.attempts,
            error=delivery.last_error,
        )
    else:
        # Exponential backoff: 60s, 120s, 240s, 480s, …
        delay = RETRY_BACKOFF_BASE_SECONDS * (2 ** (delivery.attempts - 1))
        delivery.next_attempt_at = datetime.now(UTC) + timedelta(seconds=delay)
        delivery.status = WebhookDeliveryStatus.PENDING
    await db.flush()
    return delivery


async def process_pending_deliveries(db: AsyncSession, *, limit: int = 50) -> dict[str, int]:
    """Deliver due pending webhooks (Celery beat entry point body)."""
    now = datetime.now(UTC)
    stmt = (
        select(WebhookDelivery)
        .where(
            WebhookDelivery.status == WebhookDeliveryStatus.PENDING,
            WebhookDelivery.next_attempt_at <= now,
        )
        .order_by(WebhookDelivery.next_attempt_at)
        .limit(limit)
    )
    deliveries = (await db.execute(stmt)).scalars().all()
    results = {"success": 0, "failed": 0, "retrying": 0}
    for delivery in deliveries:
        await deliver_one(db, delivery)
        if delivery.status == WebhookDeliveryStatus.SUCCESS:
            results["success"] += 1
        elif delivery.status == WebhookDeliveryStatus.FAILED:
            results["failed"] += 1
        else:
            results["retrying"] += 1
    await db.flush()
    return results


async def list_deliveries(
    db: AsyncSession,
    *,
    endpoint_id: uuid.UUID | None = None,
    status: WebhookDeliveryStatus | None = None,
    limit: int = 50,
) -> list[WebhookDelivery]:
    stmt = select(WebhookDelivery).order_by(WebhookDelivery.created_at.desc()).limit(limit)
    if endpoint_id is not None:
        stmt = stmt.where(WebhookDelivery.endpoint_id == endpoint_id)
    if status is not None:
        stmt = stmt.where(WebhookDelivery.status == status)
    return list((await db.execute(stmt)).scalars().all())


async def send_test_delivery(
    db: AsyncSession, endpoint_id: uuid.UUID
) -> WebhookDelivery:
    """Deliver a synthetic ``ping`` immediately and persist the attempt row.

    Shares sign_payload/deliver_one with real deliveries, so success here
    means the endpoint URL, HMAC secret and network path all work.
    """
    endpoint = await db.get(WebhookEndpoint, endpoint_id)
    if not endpoint:
        raise NotFoundError("WebhookEndpoint", f"Webhook endpoint {endpoint_id} not found")
    delivery = WebhookDelivery(
        endpoint_id=endpoint.id,
        event="ping",
        payload={
            "event": "ping",
            "timestamp": datetime.now(UTC).isoformat(),
            "data": {"message": "تست وب‌هوک از پنل مدیریت"},
        },
        status=WebhookDeliveryStatus.PENDING,
    )
    db.add(delivery)
    await db.flush()
    await deliver_one(db, delivery)
    logger.info(
        "webhook_test_delivery",
        endpoint_id=str(endpoint_id),
        status=delivery.status.value,
    )
    return delivery


async def rotate_secret(db: AsyncSession, endpoint_id: uuid.UUID) -> str:
    """Generate and store a fresh signing secret; returned once to the caller."""
    import secrets as secrets_mod

    endpoint = await db.get(WebhookEndpoint, endpoint_id)
    if not endpoint:
        raise NotFoundError("WebhookEndpoint", f"Webhook endpoint {endpoint_id} not found")
    secret = secrets_mod.token_urlsafe(32)
    endpoint.secret = secret
    await db.flush()
    logger.info("webhook_secret_rotated", endpoint_id=str(endpoint_id))
    return secret
