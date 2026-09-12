"""B2B Reseller API routes (Karta Phase 4).

Implements:
- X-API-KEY header authentication with IP whitelisting
- Wholesale catalog inquiry with live digital stock levels
- Automated bulk card purchasing with instant PIN delivery
- Pre-paid credit balance inquiry
- Admin partner API key provisioning
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.security.dependencies import RequirePermissions
from app.modules.orders.application import reseller_service
from app.modules.orders.domain.reseller_models import ResellerApiKey
from app.modules.orders.schemas.reseller import (
    ResellerApiKeyCreateRequest,
    ResellerApiKeyCreateResponse,
    ResellerBalanceResponse,
    ResellerCatalogItem,
    ResellerPurchaseRequest,
    ResellerPurchaseResponse,
)

router = APIRouter(prefix="/reseller", tags=["orders-reseller"])


# ── Dependency: Reseller API Key Authentication ───────────────────────────


async def get_current_reseller(
    request: Request,
    x_api_key: str = Header(..., alias="X-API-KEY", description="Partner secret API key"),
    db: AsyncSession = Depends(get_db),
) -> ResellerApiKey:
    """Extract and authenticate partner API key with IP whitelisting."""
    forwarded = request.headers.get("x-forwarded-for")
    client_ip = (
        forwarded.split(",")[0].strip()
        if forwarded
        else (request.client.host if request.client else None)
    )
    return await reseller_service.verify_reseller_api_key(
        db, raw_api_key=x_api_key, client_ip=client_ip
    )


# ── B2B Partner Endpoints ─────────────────────────────────────────────────


@router.get(
    "/catalog",
    response_model=list[ResellerCatalogItem],
    summary="Wholesale catalog inquiry with live digital stock count",
)
async def get_catalog(
    reseller: ResellerApiKey = Depends(get_current_reseller),
    db: AsyncSession = Depends(get_db),
) -> list[ResellerCatalogItem]:
    items = await reseller_service.get_b2b_catalog_stock(db)
    return [ResellerCatalogItem.model_validate(i) for i in items]


@router.post(
    "/orders/purchase",
    response_model=ResellerPurchaseResponse,
    summary="Automated wholesale card purchase with instant PIN delivery",
)
async def purchase_cards(
    body: ResellerPurchaseRequest,
    reseller: ResellerApiKey = Depends(get_current_reseller),
    db: AsyncSession = Depends(get_db),
) -> ResellerPurchaseResponse:
    result = await reseller_service.b2b_purchase_cards(
        db,
        reseller_key=reseller,
        product_id=body.product_id,
        quantity=body.quantity,
        unit_price=body.unit_price,
    )
    return ResellerPurchaseResponse.model_validate(result)


@router.get(
    "/balance",
    response_model=ResellerBalanceResponse,
    summary="Inquire pre-paid credit balance",
)
async def get_balance(
    reseller: ResellerApiKey = Depends(get_current_reseller),
    db: AsyncSession = Depends(get_db),
) -> ResellerBalanceResponse:
    balance = await reseller_service.get_reseller_balance(db, reseller_key_id=reseller.id)
    return ResellerBalanceResponse(credit_balance=balance)


# ── Admin Provisioning Endpoints ──────────────────────────────────────────


@router.post(
    "/admin/keys",
    response_model=ResellerApiKeyCreateResponse,
    summary="Generate a new B2B partner API key (admin)",
    dependencies=[Depends(RequirePermissions("orders:write"))],
)
async def create_key(
    body: ResellerApiKeyCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> ResellerApiKeyCreateResponse:
    record, raw_key = await reseller_service.create_reseller_api_key(
        db,
        user_id=body.user_id,
        name=body.name,
        ip_whitelist=body.ip_whitelist,
        initial_credit=body.initial_credit,
        expires_at=body.expires_at,
        rate_limit_per_minute=body.rate_limit_per_minute,
    )
    resp = ResellerApiKeyCreateResponse.model_validate(record)
    resp.plaintext_api_key = raw_key
    return resp
