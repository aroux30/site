"""Shopping cart API routes."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.security.dependencies import get_current_user_id
from app.core.security.rate_limiter import limiter
from app.modules.cart.application import cart_service
from app.modules.cart.domain.models import CartStatus
from app.modules.cart.schemas.cart import (
    CartItemCreate,
    CartItemUpdate,
    CartMergeRequest,
    CartRecoveryResponse,
    CartResponse,
    CartValidationResponse,
)

router = APIRouter()


# ── Helpers ────────────────────────────────────────────────────────────────


async def _resolve_cart_owner(
    request: Request,
    user_id: uuid.UUID | None = None,
) -> tuple[uuid.UUID | None, str | None]:
    """Determine the cart owner from the token or session cookie.

    For authenticated users we use `user_id`.  For guests we fall back to a
    ``X-Session-ID`` header (set by the frontend).
    """
    session_id = request.headers.get("X-Session-ID")
    if user_id is not None:
        return user_id, None
    return None, session_id


async def _get_optional_user_id(request: Request) -> uuid.UUID | None:
    """Try to extract user_id from the token, return None if unauthenticated."""
    try:
        return await get_current_user_id(await _extract_payload(request))
    except Exception:
        return None


async def _extract_payload(request: Request) -> dict[str, Any]:
    from app.core.security.jwt import verify_token

    token: str | None = None
    auth = request.headers.get("Authorization")
    if auth and auth.startswith("Bearer "):
        token = auth.split(" ", 1)[1]
    elif "access_token" in request.cookies:
        token = request.cookies.get("access_token")

    if not token:
        raise ValueError("No token")
    return verify_token(token, expected_type="access")


async def _resolve_owner_from_request(
    request: Request,
) -> tuple[uuid.UUID | None, str | None]:
    """Best-effort extraction of owner identity."""
    user_id: uuid.UUID | None = None
    try:
        payload = await _extract_payload(request)
        user_id = uuid.UUID(payload["sub"])
    except Exception:  # noqa: S110  # optional auth probe; absence falls back to session id
        pass
    session_id = request.headers.get("X-Session-ID")
    if user_id:
        return user_id, None
    return None, session_id


# ── Endpoints ──────────────────────────────────────────────────────────────


@router.get(
    "",
    response_model=CartResponse,
    summary="Get current user's or guest's cart",
)
async def get_cart(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> CartResponse:
    user_id, session_id = await _resolve_owner_from_request(request)
    if user_id is None and not session_id:
        from app.core.exceptions.handlers import ValidationError

        raise ValidationError("Authentication or X-Session-ID header required")
    return await cart_service.get_cart_by_owner(db, user_id=user_id, session_id=session_id)


@router.post(
    "/items",
    response_model=CartResponse,
    summary="Add an item to the cart",
)
@limiter.limit("60/minute")
async def add_cart_item(
    body: CartItemCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> CartResponse:
    user_id, session_id = await _resolve_owner_from_request(request)
    if user_id is None and not session_id:
        from app.core.exceptions.handlers import ValidationError

        raise ValidationError("Authentication or X-Session-ID header required")

    cart = await cart_service.get_or_create_cart(db, user_id=user_id, session_id=session_id)
    return await cart_service.add_item(
        db,
        cart_id=cart.id,
        variant_id=body.variant_id,
        quantity=body.quantity,
    )


@router.patch(
    "/items/{item_id}",
    response_model=CartResponse,
    summary="Update cart item quantity",
)
@limiter.limit("60/minute")
async def update_cart_item(
    item_id: uuid.UUID,
    body: CartItemUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> CartResponse:
    user_id, session_id = await _resolve_owner_from_request(request)
    if user_id is None and not session_id:
        from app.core.exceptions.handlers import ValidationError

        raise ValidationError("Authentication or X-Session-ID header required")

    cart = await cart_service.get_or_create_cart(db, user_id=user_id, session_id=session_id)
    return await cart_service.update_item_quantity(
        db,
        cart_id=cart.id,
        item_id=item_id,
        quantity=body.quantity,
    )


@router.delete(
    "/items/{item_id}",
    response_model=CartResponse,
    summary="Remove an item from the cart",
)
@limiter.limit("60/minute")
async def delete_cart_item(
    item_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> CartResponse:
    user_id, session_id = await _resolve_owner_from_request(request)
    if user_id is None and not session_id:
        from app.core.exceptions.handlers import ValidationError

        raise ValidationError("Authentication or X-Session-ID header required")

    cart = await cart_service.get_or_create_cart(db, user_id=user_id, session_id=session_id)
    return await cart_service.remove_item(db, cart_id=cart.id, item_id=item_id)


@router.post(
    "/merge",
    response_model=CartResponse,
    summary="Merge guest cart into authenticated user's cart",
)
@limiter.limit("10/minute")
async def merge_carts(
    request: Request,
    body: CartMergeRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> CartResponse:
    return await cart_service.merge_carts(
        db,
        guest_session_id=body.guest_session_id,
        user_id=user_id,
    )


@router.post(
    "/recover",
    response_model=CartRecoveryResponse,
    summary="Restore an abandoned cart from a recovery link",
)
@limiter.limit("10/minute")
async def recover_cart(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> CartRecoveryResponse:
    """Exchange a recovery-link token for the cart it authorizes.

    The token is a single-purpose bearer JWT (``type=recovery``) that names
    both the cart and its owner; the cart is reactivated if it was abandoned,
    and its activity clock resets so the user is not reminded again while
    they are shopping.
    """
    token = request.query_params.get("token")
    if not token:
        from app.core.exceptions.handlers import ValidationError

        raise ValidationError("Recovery token is required")

    from app.core.security.jwt import verify_recovery_token

    cart_id, user_id = verify_recovery_token(token)

    from app.modules.cart.domain.models import Cart
    from app.core.exceptions.handlers import NotFoundError
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from datetime import UTC, datetime

    stmt = (
        select(Cart)
        .options(selectinload(Cart.items))
        .where(Cart.id == cart_id, Cart.user_id == user_id)
    )
    result = await db.execute(stmt)
    cart = result.scalar_one_or_none()
    if cart is None:
        raise NotFoundError(resource="Cart", detail="Cart not found")

    if cart.status == CartStatus.ABANDONED:
        cart.status = CartStatus.ACTIVE
    cart.last_activity_at = datetime.now(UTC)
    await db.flush()

    cart_response = await cart_service._build_cart_response(db, cart)
    return CartRecoveryResponse(cart=cart_response, recovered=True)


@router.post(
    "/validate",
    response_model=CartValidationResponse,
    summary="Validate cart items against current catalog and stock",
)
async def validate_cart(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> CartValidationResponse:
    user_id, session_id = await _resolve_owner_from_request(request)
    if user_id is None and not session_id:
        from app.core.exceptions.handlers import ValidationError

        raise ValidationError("Authentication or X-Session-ID header required")

    cart = await cart_service.get_or_create_cart(db, user_id=user_id, session_id=session_id)
    return await cart_service.validate_cart(db, cart_id=cart.id)
