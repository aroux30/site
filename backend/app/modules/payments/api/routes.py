"""Payment module API routes."""

from __future__ import annotations

import uuid
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.security.dependencies import (
    RequirePermissions,
    get_current_user_id,
)
from app.modules.payments.application import payment_service
from app.modules.payments.infrastructure.provider_factory import get_payment_provider
from app.modules.payments.schemas.payment import (
    CardReceiptSubmitRequest,
    PaymentCallbackData,
    PaymentCreateRequest,
    PaymentMethodsResponse,
    PaymentRejectRequest,
    PaymentResponse,
    PaymentVerifyRequest,
    RefundRequest,
    RefundResponse,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

router = APIRouter()

# Admin router mounted at /api/v1/admin/payments via main.py _include_routers
admin_router = APIRouter(
    prefix="/admin/payments",
    tags=["admin-payments"],
)

_require_payment_manage = Depends(RequirePermissions("payments:manage"))


# ── Payment Methods ───────────────────────────────────────────────────────


@router.get(
    "/methods",
    response_model=PaymentMethodsResponse,
    summary="List available payment methods",
)
async def list_payment_methods() -> PaymentMethodsResponse:
    """Return the list of payment providers available to the buyer.

    Includes online gateways (Zarinpal, IDPay), Cryptocurrency (NowPayments / USDT),
    direct Card-to-Card transfer, and internal wallet.
    """
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


# ── Card-to-Card Receipt Submission ───────────────────────────────────────


@router.post(
    "/{payment_id}/card-receipt",
    response_model=PaymentResponse,
    summary="Submit card-to-card transfer receipt / reference",
)
async def submit_card_receipt(
    payment_id: uuid.UUID,
    body: CardReceiptSubmitRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> PaymentResponse:
    """Submit bank tracking code / receipt for a card-to-card payment.

    Keeps the payment status in ``PENDING`` awaiting administrator approval.
    """
    return await payment_service.submit_card_receipt(
        db,
        payment_id=payment_id,
        user_id=user_id,
        tracking_code=body.tracking_code,
        card_pan=body.card_pan,
        receipt_image_url=body.receipt_image_url,
        notes=body.notes,
    )


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


# ── Admin Approve / Reject (on router and admin_router) ───────────────────


@router.post(
    "/{payment_id}/approve",
    response_model=PaymentResponse,
    summary="Approve payment (admin)",
    dependencies=[_require_payment_manage],
)
@router.post(
    "/admin/{payment_id}/approve",
    response_model=PaymentResponse,
    summary="Approve payment alias (admin)",
    dependencies=[_require_payment_manage],
    include_in_schema=False,
)
@admin_router.post(
    "/{payment_id}/approve",
    response_model=PaymentResponse,
    summary="Approve payment via admin router",
    dependencies=[_require_payment_manage],
)
async def approve_payment(
    payment_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> PaymentResponse:
    """Admin approves a pending payment (e.g. card-to-card receipt verified)."""
    return await payment_service.approve_payment(
        db,
        payment_id=payment_id,
        admin_user_id=user_id,
    )


@router.post(
    "/{payment_id}/reject",
    response_model=PaymentResponse,
    summary="Reject payment (admin)",
    dependencies=[_require_payment_manage],
)
@router.post(
    "/admin/{payment_id}/reject",
    response_model=PaymentResponse,
    summary="Reject payment alias (admin)",
    dependencies=[_require_payment_manage],
    include_in_schema=False,
)
@admin_router.post(
    "/{payment_id}/reject",
    response_model=PaymentResponse,
    summary="Reject payment via admin router",
    dependencies=[_require_payment_manage],
)
async def reject_payment(
    payment_id: uuid.UUID,
    body: Optional[PaymentRejectRequest] = None,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> PaymentResponse:
    """Admin rejects a pending payment (e.g. invalid receipt)."""
    reason = body.reason if body else None
    return await payment_service.reject_payment(
        db,
        payment_id=payment_id,
        admin_user_id=user_id,
        reason=reason,
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
    call it directly. Signature verification is handled internally per provider.
    """
    raw_body = await request.body()

    # Parse body – gateways may send form-encoded or JSON
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        import json

        raw = json.loads(raw_body.decode("utf-8")) if raw_body else {}
    else:
        form = await request.form()
        raw = dict(form)

    # Optional IPN signature verification for NowPayments
    prov_lower = provider.lower()
    if prov_lower in ("crypto", "nowpayments"):
        sig_header = request.headers.get("x-nowpayments-sig")
        if sig_header:
            try:
                crypto_provider = get_payment_provider("crypto")
                if hasattr(crypto_provider, "verify_ipn_signature"):
                    is_valid = crypto_provider.verify_ipn_signature(raw_body, sig_header)
                    if not is_valid:
                        await logger.awarning(
                            "nowpayments_ipn_signature_mismatch",
                            provider=provider,
                        )
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Invalid IPN signature",
                        )
            except HTTPException:
                raise
            except Exception as exc:
                await logger.awarning("nowpayments_sig_check_error", error=str(exc))

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
