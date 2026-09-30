"""Admin endpoints for outbound webhook endpoints and their delivery log."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.security.dependencies import RequirePermissions
from app.modules.integrations.application import webhook_service
from app.modules.integrations.domain.webhooks import WebhookDeliveryStatus

router = APIRouter()

_require_integrations_write = Depends(RequirePermissions("settings:write"))


class WebhookEndpointCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    url: str = Field(..., min_length=1, max_length=1000)
    events: list[str] = Field(..., min_length=1)
    secret: str | None = Field(None, max_length=200)


class WebhookEndpointUpdateRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=150)
    url: str | None = Field(None, min_length=1, max_length=1000)
    events: list[str] | None = Field(None, min_length=1)
    is_active: bool | None = None
    secret: str | None = Field(None, max_length=200)


class WebhookEndpointResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    url: str
    events: list[str]
    is_active: bool


class WebhookDeliveryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    endpoint_id: uuid.UUID
    event: str
    status: WebhookDeliveryStatus
    attempts: int
    response_status: int | None = None
    last_error: str | None = None
    # Operationally useful timing + payload: without these the log could not
    # answer "when did it fire / when does it retry / what was sent".
    payload: dict[str, Any] | None = None
    created_at: datetime | None = None
    next_attempt_at: datetime | None = None
    delivered_at: datetime | None = None


@router.get(
    "/admin/webhooks/events",
    response_model=list[str],
    summary="List emittable webhook event names (admin)",
    dependencies=[_require_integrations_write],
)
async def list_webhook_events() -> list[str]:
    return sorted(webhook_service.EVENTS)


@router.get(
    "/admin/webhooks",
    response_model=list[WebhookEndpointResponse],
    summary="List webhook endpoints (admin)",
    dependencies=[_require_integrations_write],
)
async def list_endpoints(
    db: AsyncSession = Depends(get_db),
) -> list[WebhookEndpointResponse]:
    endpoints = await webhook_service.list_endpoints(db)
    return [WebhookEndpointResponse.model_validate(e) for e in endpoints]


@router.post(
    "/admin/webhooks",
    response_model=WebhookEndpointResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a webhook endpoint (admin)",
    dependencies=[_require_integrations_write],
)
async def create_endpoint(
    body: WebhookEndpointCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> WebhookEndpointResponse:
    endpoint = await webhook_service.create_endpoint(
        db, name=body.name, url=body.url, events=body.events, secret=body.secret
    )
    return WebhookEndpointResponse.model_validate(endpoint)


@router.patch(
    "/admin/webhooks/{endpoint_id}",
    response_model=WebhookEndpointResponse,
    summary="Update a webhook endpoint (admin)",
    dependencies=[_require_integrations_write],
)
async def update_endpoint(
    endpoint_id: uuid.UUID,
    body: WebhookEndpointUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> WebhookEndpointResponse:
    endpoint = await webhook_service.update_endpoint(
        db,
        endpoint_id,
        name=body.name,
        url=body.url,
        events=body.events,
        is_active=body.is_active,
        secret=body.secret,
    )
    return WebhookEndpointResponse.model_validate(endpoint)


@router.delete(
    "/admin/webhooks/{endpoint_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a webhook endpoint (admin)",
    dependencies=[_require_integrations_write],
)
async def delete_endpoint(
    endpoint_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    await webhook_service.delete_endpoint(db, endpoint_id)


@router.get(
    "/admin/webhooks/deliveries",
    response_model=list[WebhookDeliveryResponse],
    summary="Recent webhook delivery log (admin)",
    dependencies=[_require_integrations_write],
)
async def list_deliveries(
    endpoint_id: uuid.UUID | None = Query(None),
    status_filter: WebhookDeliveryStatus | None = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> list[WebhookDeliveryResponse]:
    deliveries = await webhook_service.list_deliveries(
        db, endpoint_id=endpoint_id, status=status_filter, limit=limit
    )
    return [WebhookDeliveryResponse.model_validate(d) for d in deliveries]


@router.post(
    "/admin/webhooks/{endpoint_id}/test",
    response_model=WebhookDeliveryResponse,
    summary="Send a test delivery to one endpoint (admin)",
    dependencies=[_require_integrations_write],
)
async def test_endpoint(
    endpoint_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> WebhookDeliveryResponse:
    """Deliver a synthetic ``ping`` payload immediately and return the result.

    Uses the same signing/transport path as real events, so a green result
    proves URL, reachability and secret configuration end-to-end.
    """
    delivery = await webhook_service.send_test_delivery(db, endpoint_id)
    return WebhookDeliveryResponse.model_validate(delivery)


@router.post(
    "/admin/webhooks/{endpoint_id}/secret/rotate",
    response_model=dict[str, str],
    summary="Rotate the signing secret and return the new value once (admin)",
    dependencies=[_require_integrations_write],
)
async def rotate_secret(
    endpoint_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    secret = await webhook_service.rotate_secret(db, endpoint_id)
    return {"secret": secret}
