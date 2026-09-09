"""Wishlist module API routes.

All wishlist endpoints require authentication. The user's default wishlist
is created lazily on first interaction.
"""

from __future__ import annotations

import uuid
from typing import Any

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.security.dependencies import get_current_user_id
from app.modules.wishlist.application.wishlist_service import WishlistService
from app.modules.wishlist.schemas.wishlist import (
    WishlistAddRequest,
    WishlistCheckResponse,
    WishlistItemResponse,
    WishlistResponse,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger()

router = APIRouter()

_wishlist_service = WishlistService()


@router.get("", response_model=WishlistResponse)
async def get_wishlist(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> WishlistResponse:
    """Get the authenticated user's wishlist with product details."""
    return await _wishlist_service.get_wishlist(db=db, user_id=user_id)


@router.post("/items", response_model=WishlistItemResponse, status_code=201)
async def add_to_wishlist(
    data: WishlistAddRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> WishlistItemResponse:
    """Add a product to the user's wishlist."""
    product_id = uuid.UUID(data.product_id)
    return await _wishlist_service.add_item(
        db=db,
        user_id=user_id,
        product_id=product_id,
    )


@router.delete("/items/{product_id}", status_code=204)
async def remove_from_wishlist(
    product_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Remove a product from the user's wishlist."""
    await _wishlist_service.remove_item(
        db=db,
        user_id=user_id,
        product_id=product_id,
    )


@router.get("/check/{product_id}", response_model=WishlistCheckResponse)
async def check_wishlist(
    product_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> WishlistCheckResponse:
    """Check if a product is in the user's wishlist."""
    return await _wishlist_service.is_in_wishlist(
        db=db,
        user_id=user_id,
        product_id=product_id,
    )
