"""API routes for Fintech: Card2Card receipts, Direct Pay invoices, and Gateway config (Karta Phase 3/5)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.security.dependencies import RequirePermissions, get_current_user_id
from app.modules.payments.application import (
    card_transfer_service,
    direct_pay_service,
    gateway_error_dictionary,
)
from app.modules.payments.schemas.fintech import (
    CardTransferReceiptCreate,
    CardTransferReceiptResponse,
    CardTransferReceiptReviewRequest,
    DirectInvoiceCreateRequest,
    DirectInvoiceResponse,
    GatewayErrorResolveRequest,
    GatewayErrorResolveResponse,
    GatewaySettingResponse,
    GatewaySettingUpdateRequest,
)

router = APIRouter(prefix="/fintech", tags=["payments-fintech"])


# ── Card-to-Card Receipt Endpoints (Customer) ─────────────────────────────


@router.post(
    "/card2card/receipts",
    response_model=CardTransferReceiptResponse,
    summary="Submit a card-to-card transfer slip for manual review (Karta card2card)",
)
async def submit_receipt(
    body: CardTransferReceiptCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> CardTransferReceiptResponse:
    receipt = await card_transfer_service.submit_card_transfer_receipt(
        db,
        order_id=body.order_id,
        user_id=user_id,
        amount=body.amount,
        tracking_code=body.tracking_code,
        source_card_last4=body.source_card_last4,
        destination_card_number=body.destination_card_number,
        receipt_image_url=body.receipt_image_url,
    )
    return CardTransferReceiptResponse.model_validate(receipt)


@router.get(
    "/card2card/orders/{order_id}/receipts",
    response_model=list[CardTransferReceiptResponse],
    summary="List submitted transfer receipts for an order",
)
async def get_order_receipts(
    order_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> list[CardTransferReceiptResponse]:
    receipts = await card_transfer_service.list_receipts_by_order(db, order_id=order_id)
    return [CardTransferReceiptResponse.model_validate(r) for r in receipts]


# ── Card-to-Card Admin Review Endpoints ───────────────────────────────────


@router.post(
    "/admin/card2card/receipts/{receipt_id}/review",
    response_model=CardTransferReceiptResponse,
    summary="Admin review / approve / reject card transfer slip (admin)",
    dependencies=[Depends(RequirePermissions("payments:write"))],
)
async def review_receipt(
    receipt_id: uuid.UUID,
    body: CardTransferReceiptReviewRequest,
    admin_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> CardTransferReceiptResponse:
    receipt = await card_transfer_service.review_card_transfer_receipt(
        db,
        receipt_id=receipt_id,
        reviewed_by=admin_id,
        is_approved=body.is_approved,
        admin_notes=body.admin_notes,
    )
    return CardTransferReceiptResponse.model_validate(receipt)


# ── Direct Pay Quick Invoices (Karta Directpay) ───────────────────────────


@router.post(
    "/direct-invoices",
    response_model=DirectInvoiceResponse,
    summary="Generate a direct quick invoice and shareable payment link",
)
async def create_invoice(
    body: DirectInvoiceCreateRequest,
    user_id: uuid.UUID | None = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> DirectInvoiceResponse:
    invoice = await direct_pay_service.create_direct_invoice(
        db,
        amount=body.amount,
        title=body.title,
        description=body.description,
        user_id=user_id,
        payer_name=body.payer_name,
        payer_mobile=body.payer_mobile,
        ttl_hours=body.ttl_hours,
    )
    return DirectInvoiceResponse.model_validate(invoice)


@router.get(
    "/direct-invoices/{invoice_id}",
    response_model=DirectInvoiceResponse,
    summary="Get direct invoice details by ID (public / customer)",
)
async def get_invoice(
    invoice_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> DirectInvoiceResponse:
    invoice = await direct_pay_service.get_direct_invoice_by_id(db, invoice_id=invoice_id)
    return DirectInvoiceResponse.model_validate(invoice)


# ── Dynamic Gateway Registry & Errors ─────────────────────────────────────


@router.get(
    "/gateways",
    response_model=list[GatewaySettingResponse],
    summary="List active payment gateways ordered by priority",
)
async def list_gateways(
    db: AsyncSession = Depends(get_db),
) -> list[GatewaySettingResponse]:
    gateways = await direct_pay_service.list_active_gateways(db)
    return [GatewaySettingResponse.model_validate(g) for g in gateways]


@router.put(
    "/admin/gateways/{provider_key}",
    response_model=GatewaySettingResponse,
    summary="Configure or update gateway priority and active status (admin)",
    dependencies=[Depends(RequirePermissions("payments:write"))],
)
async def configure_gateway(
    provider_key: str,
    body: GatewaySettingUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> GatewaySettingResponse:
    gw = await direct_pay_service.configure_gateway_setting(
        db,
        provider_key=provider_key,
        title_fa=body.title_fa,
        is_active=body.is_active,
        is_default=body.is_default,
        priority=body.priority,
        min_amount=body.min_amount,
        max_amount=body.max_amount,
        credentials=body.credentials,
    )
    return GatewaySettingResponse.model_validate(gw)


@router.post(
    "/errors/translate",
    response_model=GatewayErrorResolveResponse,
    summary="Translate PSP error code to friendly Persian message (Karta get_error)",
)
async def translate_error(
    body: GatewayErrorResolveRequest,
) -> GatewayErrorResolveResponse:
    msg = gateway_error_dictionary.translate_gateway_error(
        provider=body.provider, error_code=body.error_code
    )
    return GatewayErrorResolveResponse(
        provider=body.provider,
        error_code=str(body.error_code),
        persian_message=msg,
    )
