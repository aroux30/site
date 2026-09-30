"""Integration capability registry endpoints.

Two read-only endpoints over the same locally-derived registry:

- ``GET /capabilities`` — customer-safe view, no authentication. Only records
  flagged customer-visible are returned.
- ``GET /admin/capabilities`` — operator view, gated on the existing
  ``settings:read`` permission, which is the permission the settings surface
  already uses for "may inspect how this deployment is configured".

Both return the one contract-defined record shape; they differ only in which
records they include. Neither endpoint writes anything, mutates a capability,
contacts a provider, or influences payment selection — they only report
configuration state.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.settings import get_settings
from app.core.database.session import get_db
from app.core.security.dependencies import RequirePermissions
from app.core.security.rate_limiter import limiter
from app.modules.integrations.application.capability_registry import (
    build_capability_registry,
    customer_visible_capabilities,
    zarinpal_merchant_override_configured,
)
from app.modules.integrations.schemas.capability import CapabilityResponse

router = APIRouter()

# Outbound webhook management lives in a sibling router mounted on the same
# /integrations prefix (see app.main router includes).
from app.modules.integrations.api.webhook_routes import router as webhook_router

router.include_router(webhook_router)


@router.get(
    "/capabilities",
    response_model=list[CapabilityResponse],
    summary="List customer-visible integration capabilities",
)
@limiter.limit("60/minute")
async def list_public_capabilities(request: Request) -> list[CapabilityResponse]:
    """Return the integration capabilities a customer surface may render.

    Unauthenticated on purpose: the storefront needs this to decide which
    payment and delivery options to show, and none of the returned fields are
    sensitive. ``request`` is required by the rate limiter even though it is
    unused by the handler.
    """
    registry = build_capability_registry(get_settings(), now=datetime.now(UTC))
    return [
        CapabilityResponse.model_validate(record)
        for record in customer_visible_capabilities(registry)
    ]


@router.get(
    "/admin/capabilities",
    response_model=list[CapabilityResponse],
    summary="List all integration capabilities (admin)",
    dependencies=[Depends(RequirePermissions("settings:read"))],
)
async def list_admin_capabilities(
    db: AsyncSession = Depends(get_db),
) -> list[CapabilityResponse]:
    """Return every capability, including the ones hidden from customers.

    The only extra fact consulted here is whether a Zarinpal merchant id has
    been registered through the admin settings UI, which lives in the database
    rather than the environment. It is reduced to a boolean before it reaches
    the registry.
    """
    registry = build_capability_registry(
        get_settings(),
        zarinpal_merchant_id_configured=await zarinpal_merchant_override_configured(db),
        now=datetime.now(UTC),
    )
    return [CapabilityResponse.model_validate(record) for record in registry]
