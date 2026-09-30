"""API routes for saved cards, installment plans, and split tender.

Mounted under ``/payments`` by :mod:`app.modules.payments.api.routes`. Every
customer route is user-scoped: ownership is part of the query (see the
services), so an id belonging to another account is indistinguishable from a
missing one.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.security.dependencies import RequirePermissions, get_current_user_id
from app.core.security.rate_limiter import limiter
from app.modules.payments.application import (
    installment_service,
    split_tender_service,
    tokenization_service,
)
from app.modules.payments.domain.installment_models import InstallmentPlanStatus
from app.modules.payments.schemas.allocation import (
    AllocationRefundRequest,
    OrderAllocationSummary,
    PaymentAllocationResponse,
    SplitPaymentResponse,
    SplitTenderRequest,
)
from app.modules.payments.schemas.installment import (
    CreateInstallmentPlanRequest,
    InstallmentOptionsResponse,
    InstallmentPlanListResponse,
    InstallmentPlanResponse,
)
from app.modules.payments.schemas.saved_method import (
    ChargeSavedMethodRequest,
    SavedPaymentMethodListResponse,
    SavedPaymentMethodResponse,
    TokenizeCardRequest,
    TokenizeCardResponse,
)

router = APIRouter()

_require_payment_manage = Depends(RequirePermissions("payments:manage"))


# ── Saved cards (tokenized) ───────────────────────────────────────────────


@router.get(
    "/saved-methods",
    response_model=SavedPaymentMethodListResponse,
    summary="List my saved cards",
)
async def list_saved_methods(
    include_inactive: bool = Query(False, description="Include revoked/expired cards"),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> SavedPaymentMethodListResponse:
    """Return the user's saved cards (default first). Tokens are never returned."""
    items = await tokenization_service.list_saved_methods(
        db, user_id=user_id, include_inactive=include_inactive
    )
    return SavedPaymentMethodListResponse(items=items, total=len(items))


@router.post(
    "/saved-methods",
    response_model=TokenizeCardResponse,
    status_code=201,
    summary="Register a card with a gateway (tokenize)",
)
@limiter.limit("10/minute")
async def tokenize_card(
    request: Request,
    body: TokenizeCardRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> TokenizeCardResponse:
    """Start a card-registration flow.

    The PAN is entered on the gateway's own page and never reaches this
    application. Providers that register synchronously return a saved card
    here; gateways that need the customer to visit a card-entry page return
    ``requires_redirect`` + ``redirect_url`` and the token arrives later via
    the provider callback.
    """
    result = await tokenization_service.initiate_tokenization(
        db,
        user_id=user_id,
        provider_name=body.provider,
        mobile=body.mobile,
    )

    if not result.success:
        return TokenizeCardResponse(
            success=False,
            provider=body.provider,
            error_code=result.error_code,
            error_message=result.error_message,
        )

    saved = await tokenization_service.save_tokenized_method(
        db,
        user_id=user_id,
        provider_name=body.provider,
        result=result,
    )
    return TokenizeCardResponse(
        success=True,
        provider=body.provider,
        saved_method=saved,
    )


@router.delete(
    "/saved-methods/{method_id}",
    response_model=SavedPaymentMethodResponse,
    summary="Delete (revoke) a saved card",
)
async def delete_saved_method(
    method_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> SavedPaymentMethodResponse:
    """Revoke a saved card locally and ask the gateway to invalidate its token."""
    return await tokenization_service.revoke_saved_method(
        db, user_id=user_id, method_id=method_id, reason="customer_deleted"
    )


@router.post(
    "/saved-methods/{method_id}/default",
    response_model=SavedPaymentMethodResponse,
    summary="Set a saved card as default",
)
async def set_default_saved_method(
    method_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> SavedPaymentMethodResponse:
    """Make one saved card the user's default payment method."""
    return await tokenization_service.set_default_method(
        db, user_id=user_id, method_id=method_id
    )


@router.post(
    "/saved-methods/{method_id}/charge",
    summary="Charge a saved card for an order",
)
async def charge_saved_method(
    method_id: uuid.UUID,
    body: ChargeSavedMethodRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    """Charge a saved card for an order (no customer redirect).

    v1 exposes this for the customer's own checkout; a future recurring-charge
    service calls :func:`tokenization_service.charge_saved_method` directly.
    """
    payment, result = await tokenization_service.charge_saved_method(
        db,
        user_id=user_id,
        method_id=method_id,
        amount=body.amount,
        order_id=body.order_id,
        description=body.description,
    )
    return {
        "payment_id": str(payment.id),
        "order_id": str(payment.order_id) if payment.order_id else None,
        "status": payment.status.value,
        "amount_rial": payment.amount,
        "authority": payment.authority,
        "gateway_ref": result.ref_id,
    }


# ── Admin visibility over saved cards ─────────────────────────────────────


@router.get(
    "/admin/saved-methods",
    response_model=SavedPaymentMethodListResponse,
    summary="List saved cards (admin)",
    dependencies=[_require_payment_manage],
    include_in_schema=False,
)
async def admin_list_saved_methods(
    user_id: uuid.UUID | None = Query(None),
    provider: str | None = Query(None),
    include_inactive: bool = Query(True),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
) -> SavedPaymentMethodListResponse:
    """Admin view of saved cards. Still masked — no gateway token is exposed."""
    items = await tokenization_service.list_saved_methods_admin(
        db,
        user_id=user_id,
        provider=provider,
        include_inactive=include_inactive,
        limit=limit,
    )
    return SavedPaymentMethodListResponse(items=items, total=len(items))


# ── Installment plans ─────────────────────────────────────────────────────


@router.get(
    "/installments/options",
    response_model=InstallmentOptionsResponse,
    summary="Installment options for an order",
)
async def installment_options(
    order_id: uuid.UUID = Query(...),
    provider: str = Query("mock"),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> InstallmentOptionsResponse:
    """Duration breakdown for an order at a given gateway.

    Computed server-side with the exact integer-Rial split rule so the
    checkout UI never reimplements the rounding; every option's schedule sums
    exactly to the order total.
    """
    return await installment_service.build_options_for_order(
        db, user_id=user_id, order_id=order_id, provider_name=provider
    )


@router.post(
    "/installments",
    response_model=InstallmentPlanResponse,
    status_code=201,
    summary="Create an installment plan for an order",
)
async def create_installment_plan(
    body: CreateInstallmentPlanRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> InstallmentPlanResponse:
    """Create the plan the customer chose at checkout."""
    return await installment_service.create_plan(
        db,
        user_id=user_id,
        order_id=body.order_id,
        provider_name=body.provider,
        num_installments=body.num_installments,
        first_installment_rial=body.first_installment_rial,
    )


@router.post(
    "/installments/{plan_id}/first-payment",
    summary="Start the first-installment payment for a plan",
    status_code=201,
)
async def create_installment_prepayment(
    plan_id: uuid.UUID,
    idempotency_key: str | None = Query(None, max_length=255),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    """Create the gateway payment for a plan's prepayment.

    The remaining installments are collected by the gateway under its credit
    contract; this application's payment path only ever moves the first one.
    """
    payment, gateway_url = await installment_service.create_installment_payment(
        db,
        user_id=user_id,
        plan_id=plan_id,
        idempotency_key=idempotency_key,
    )
    return {
        "payment_id": str(payment.id),
        "order_id": str(payment.order_id) if payment.order_id else None,
        "amount_rial": payment.amount,
        "status": payment.status.value,
        "gateway_url": gateway_url,
        "authority": payment.authority,
    }


@router.get(
    "/installments",
    response_model=InstallmentPlanListResponse,
    summary="List my installment plans",
)
async def list_installment_plans(
    status: InstallmentPlanStatus | None = Query(None),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> InstallmentPlanListResponse:
    """The user's plans, newest first."""
    items = await installment_service.list_plans(db, user_id=user_id, status=status)
    return InstallmentPlanListResponse(items=items, total=len(items))


@router.get(
    "/installments/orders/{order_id}",
    response_model=InstallmentPlanResponse | None,
    summary="Get the installment plan of an order",
)
async def get_order_installment_plan(
    order_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> InstallmentPlanResponse | None:
    """The order's plan, or null when the order is not on installments."""
    return await installment_service.get_plan_for_order(
        db, order_id=order_id, user_id=user_id
    )


@router.get(
    "/installments/{plan_id}",
    response_model=InstallmentPlanResponse,
    summary="Get an installment plan",
)
async def get_installment_plan(
    plan_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> InstallmentPlanResponse:
    """Fetch one of the user's plans with its full schedule."""
    return await installment_service.get_plan(db, plan_id=plan_id, user_id=user_id)


@router.post(
    "/installments/{plan_id}/installments/{index}/pay",
    response_model=InstallmentPlanResponse,
    summary="Mark a scheduled installment paid",
    dependencies=[_require_payment_manage],
    include_in_schema=False,
)
async def mark_installment_paid(
    plan_id: uuid.UUID,
    index: int,
    db: AsyncSession = Depends(get_db),
) -> InstallmentPlanResponse:
    """Admin/system hook: settle one scheduled installment.

    Customer-facing installment collection runs through the gateway's own
    debit of the saved token; this endpoint is the manual/settlement path.
    """
    return await installment_service.mark_installment_paid(
        db, plan_id=plan_id, installment_index=index
    )


# ── Split tender ──────────────────────────────────────────────────────────


@router.post(
    "/split",
    response_model=SplitPaymentResponse,
    status_code=201,
    summary="Pay an order with several payments (split tender)",
)
@limiter.limit("10/minute")
async def create_split_payment(
    request: Request,
    body: SplitTenderRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> SplitPaymentResponse:
    """Create a wallet + gateway (or gateway + gateway) split for one order.

    The slices must sum exactly to the order total. Wallet slices settle
    immediately inside this call; gateway slices return their payment ids and
    a ``redirect_url`` for the first unsettled slice.
    """
    return await split_tender_service.create_split_payments(
        db,
        user_id=user_id,
        order_id=body.order_id,
        slices=body.slices,
    )


@router.get(
    "/orders/{order_id}/allocations",
    response_model=OrderAllocationSummary,
    summary="Get an order's split-tender allocations",
)
async def get_order_allocations(
    order_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> OrderAllocationSummary:
    """Paid / pending / remaining view of the order's slices."""
    return await split_tender_service.order_allocation_summary(
        db, order_id=order_id, user_id=user_id
    )


@router.post(
    "/allocations/{allocation_id}/refund",
    response_model=dict,
    summary="Refund one split-tender slice (admin)",
    dependencies=[Depends(RequirePermissions("payments:refund"))],
)
async def refund_allocation(
    allocation_id: uuid.UUID,
    body: AllocationRefundRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    """Refund the payment behind one allocation (v1: full slice only)."""
    return await split_tender_service.refund_allocation(
        db,
        allocation_id=allocation_id,
        amount=body.amount,
        actor_id=user_id,
        reason=body.reason,
    )


@router.get(
    "/allocations/{allocation_id}",
    response_model=PaymentAllocationResponse,
    summary="Get one allocation",
    include_in_schema=False,
)
async def get_allocation(
    allocation_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> PaymentAllocationResponse:
    """Fetch one allocation, ownership-checked through its order's buyer."""
    return await split_tender_service.get_allocation_for_user(
        db, allocation_id=allocation_id, user_id=user_id
    )

