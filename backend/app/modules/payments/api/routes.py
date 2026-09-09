"""Payment module API routes."""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.security.dependencies import (
    RequirePermissions,
    get_current_user_id,
)
from app.modules.payments.application import payment_service
from app.modules.payments.schemas.payment import (
    PaymentCallbackData,
    PaymentCreateRequest,
    PaymentMethodsResponse,
    PaymentResponse,
    PaymentVerifyRequest,
    RefundRequest,
    RefundResponse,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

router = APIRouter()


# ── Payment Methods ───────────────────────────────────────────────────────


@router.get(
    "/methods",
    response_model=PaymentMethodsResponse,
    summary="List available payment methods",
)
async def list_payment_methods() -> PaymentMethodsResponse:
    """Return the list of payment providers available to the buyer."""
    return payment_service.get_payment_methods()


# ── Create Payment ────────────────────────────────────────────────────────


@router.post(
    "",
    response_model=PaymentResponse,
    status_code=201,
    summary="Create a new payment",
)
async def create_payment(
    body: PaymentCreateRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> PaymentResponse:
    """Initiate a payment for an order.

    On success the response includes a ``gateway_url`` the client should
    redirect the user to.
    """
    return await payment_service.create_payment(
        db,
        user_id=user_id,
        order_id=body.order_id,
        provider=body.provider.value,
        amount=body.amount,
        idempotency_key=body.idempotency_key,
    )


# ── Get Payment ───────────────────────────────────────────────────────────


@router.get(
    "/{payment_id}",
    response_model=PaymentResponse,
    summary="Get payment details",
)
async def get_payment(
    payment_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> PaymentResponse:
    """Fetch a single payment record by ID."""
    return await payment_service.get_payment(db, payment_id=payment_id)


# ── Verify Payment ────────────────────────────────────────────────────────


@router.post(
    "/{payment_id}/verify",
    response_model=PaymentResponse,
    summary="Verify a payment after gateway redirect",
)
async def verify_payment(
    payment_id: uuid.UUID,
    body: PaymentVerifyRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> PaymentResponse:
    """Verify a payment after the user returns from the gateway.

    The client should call this endpoint with the ``authority`` and ``status``
    values received from the gateway redirect.
    """
    return await payment_service.verify_payment(
        db,
        payment_id=payment_id,
        authority=body.authority,
        status=body.status,
    )


# ── Refund Payment (Admin) ───────────────────────────────────────────────


@router.post(
    "/{payment_id}/refund",
    response_model=RefundResponse,
    summary="Refund a payment (admin)",
    dependencies=[Depends(RequirePermissions("payments:refund"))],
)
async def refund_payment(
    payment_id: uuid.UUID,
    body: RefundRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> RefundResponse:
    """Request a refund for a completed payment.

    Requires the ``payments:refund`` permission.
    """
    return await payment_service.refund_payment(
        db,
        payment_id=payment_id,
        amount=body.amount,
        reason=body.reason,
        actor_id=user_id,
    )


# ── Webhook Callback (Public) ────────────────────────────────────────────


@router.post(
    "/webhooks/{provider}",
    response_model=PaymentResponse,
    summary="Payment gateway webhook / callback",
    include_in_schema=False,
)
async def webhook_callback(
    provider: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> PaymentResponse:
    """Receive and process an asynchronous callback from a payment gateway.

    This endpoint is public (no auth required) because payment gateways
    call it directly.  Signature verification is handled internally per
    provider.
    """
    # Parse body – gateways may send form-encoded or JSON
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        raw = await request.json()
    else:
        form = await request.form()
        raw = dict(form)

    await logger.ainfo(
        "payment_webhook_received",
        provider=provider,
        payload_keys=list(raw.keys()) if isinstance(raw, dict) else None,
    )

    callback_data = PaymentCallbackData.model_validate(raw)

    return await payment_service.process_callback(
        db,
        provider=provider,
        callback_data=callback_data,
    )
