"""Inbound webhook receiver: the public receive endpoint + admin management.

Two routers on purpose:

* ``receiver_router`` — the public POST endpoint external systems call. It is
  authenticated *by signature*, not by a session or API key, so it must not
  sit behind the admin permission guard; the HMAC check is its auth.
* ``admin_router`` — endpoint CRUD, secret rotation, and the delivery log,
  guarded by ``settings:write`` like the rest of the integrations admin.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.exceptions.handlers import ValidationError
from app.core.security.dependencies import RequirePermissions, get_current_user_id
from app.modules.integrations.application import inbound_webhook_service as svc
from app.modules.integrations.domain.webhooks import InboundWebhookStatus

# The receiver is folded into the module's main ``router`` by
# ``api/__init__`` (main.py only mounts ``router``/``admin_router``), which is
# why the public paths below carry the full ``/inbound/...`` prefix themselves.
receiver_router = APIRouter()
admin_router = APIRouter()

_ADMIN = "/admin/inbound-webhooks"
_require_write = Depends(RequirePermissions("settings:write"))


# ── Schemas ─────────────────────────────────────────────────────────────────


class InboundEndpointCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(None, max_length=2000)
    ip_whitelist: list[str] | None = Field(
        None, description="CIDR/literal IPs allowed to call; empty = no IP gate"
    )


class InboundEndpointResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None = None
    ip_whitelist: list[str] | None = None
    is_active: bool
    last_received_at: datetime | None = None
    total_received: int
    created_at: datetime


class InboundSecretResponse(BaseModel):
    """The one and only time the raw secret leaves the server."""

    endpoint: InboundEndpointResponse
    secret: str = Field(..., description="نمایش یک‌باره — ذخیره کنید")


class InboundDeliveryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    endpoint_id: uuid.UUID
    event_type: str | None = None
    status: str
    payload: dict[str, Any] | None = None
    idempotency_key: str | None = None
    source_ip: str | None = None
    user_agent: str | None = None
    error: str | None = None
    received_at: datetime
    processed_at: datetime | None = None


class ReceiveAck(BaseModel):
    """What the sender gets back — deliberately minimal."""

    delivery_id: uuid.UUID
    status: str
    duplicate: bool


# ── Public receiver ─────────────────────────────────────────────────────────


@receiver_router.post(
    "/inbound/{endpoint_name}",
    response_model=ReceiveAck,
    summary="Receive an inbound webhook (signature-authenticated)",
)
async def receive_inbound_webhook(
    endpoint_name: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_webhook_signature: str | None = Header(None, alias="X-Webhook-Signature"),
    x_idempotency_key: str | None = Header(None, alias="X-Idempotency-Key"),
) -> ReceiveAck:
    """Receive one signed webhook call.

    The signature (HMAC-SHA256 of the raw body, ``sha256=<hex>``) is the
    authentication — there is no session here by design. A duplicate
    idempotency key answers 200 with ``duplicate=true`` and applies nothing,
    so a sender's retry loop cannot double-apply an effect.
    """
    raw_body = await request.body()

    # Parse leniently: the signature is checked against the raw bytes, so a
    # payload that is not JSON is still a *signed* call we must reject with
    # the right reason (bad signature vs. unparseable body) rather than a 500.
    payload: dict[str, Any] | None = None
    if raw_body:
        try:
            parsed = json.loads(raw_body)
            payload = parsed if isinstance(parsed, dict) else {"data": parsed}
        except (json.JSONDecodeError, UnicodeDecodeError):
            payload = None

    source_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    delivery, accepted = await svc.receive(
        db,
        endpoint_name=endpoint_name,
        raw_body=raw_body,
        signature=x_webhook_signature,
        payload=payload,
        source_ip=source_ip,
        user_agent=user_agent,
        idempotency_key=x_idempotency_key,
    )
    await db.commit()
    return ReceiveAck(
        delivery_id=delivery.id,
        status=delivery.status.value,
        duplicate=not accepted,
    )


# ── Admin management ────────────────────────────────────────────────────────


@admin_router.get(
    _ADMIN,
    response_model=list[InboundEndpointResponse],
    dependencies=[_require_write],
    summary="List inbound webhook receivers (admin)",
)
async def list_inbound_endpoints(
    db: AsyncSession = Depends(get_db),
) -> list[InboundEndpointResponse]:
    """All receivers, newest first. Requires ``settings:write``."""
    return await svc.list_endpoints(db)


@admin_router.post(
    _ADMIN,
    response_model=InboundSecretResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[_require_write],
    summary="Create an inbound webhook receiver (admin)",
)
async def create_inbound_endpoint(
    body: InboundEndpointCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> InboundSecretResponse:
    """Create a receiver and return its signing secret **once**.

    The secret is stored encrypted (verification needs it back) and is never
    returned again except by rotation. Requires ``settings:write``.
    """
    endpoint, secret = await svc.create_endpoint(
        db,
        name=body.name,
        description=body.description,
        ip_whitelist=body.ip_whitelist,
    )
    await db.commit()
    return InboundSecretResponse(
        endpoint=InboundEndpointResponse.model_validate(endpoint),
        secret=secret,
    )


@admin_router.post(
    f"{_ADMIN}/{{endpoint_id}}/rotate-secret",
    response_model=InboundSecretResponse,
    dependencies=[_require_write],
    summary="Rotate an inbound webhook secret (admin)",
)
async def rotate_inbound_secret(
    endpoint_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> InboundSecretResponse:
    """Issue a fresh secret; the previous one stops working immediately."""
    endpoint, secret = await svc.rotate_secret(db, endpoint_id=endpoint_id)
    await db.commit()
    return InboundSecretResponse(
        endpoint=InboundEndpointResponse.model_validate(endpoint),
        secret=secret,
    )


@admin_router.get(
    f"{_ADMIN}/deliveries",
    response_model=list[InboundDeliveryResponse],
    dependencies=[_require_write],
    summary="Recent inbound webhook deliveries (admin)",
)
async def list_inbound_deliveries(
    db: AsyncSession = Depends(get_db),
    endpoint_name: str | None = Query(None, description="Filter by receiver name"),
    delivery_status: str | None = Query(
        None, alias="status", description="Filter by verdict"
    ),
    limit: int = Query(100, ge=1, le=500),
) -> list[InboundDeliveryResponse]:
    """Received calls — including refusals, which are the audit signal."""
    parsed_status: InboundWebhookStatus | None = None
    if delivery_status:
        try:
            parsed_status = InboundWebhookStatus(delivery_status)
        except ValueError as exc:
            raise ValidationError(
                f"وضعیت نامعتبر است: {delivery_status}",
                error_code="INVALID_STATUS",
            ) from exc
    rows = await svc.list_deliveries(
        db, endpoint_name=endpoint_name, status=parsed_status, limit=limit
    )
    return [InboundDeliveryResponse.model_validate(r) for r in rows]
