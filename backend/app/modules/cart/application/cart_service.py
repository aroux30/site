"""Cart application service — shopping cart lifecycle management."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload

from app.core.exceptions.handlers import ConflictError, NotFoundError, ValidationError
from app.core.observability.tracer import get_tracer
from app.modules.cart.domain.models import Cart, CartItem, CartStatus
from app.modules.cart.schemas.cart import (
    CartItemResponse,
    CartResponse,
    CartValidationIssue,
    CartValidationResponse,
)
from app.modules.catalog.domain.models import Product, ProductImage, ProductVariant
from app.modules.inventory.domain.models import InventoryItem

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
logger: structlog.stdlib.BoundLogger = structlog.get_logger()

# Default cart TTL for guest carts (30 days)
_GUEST_CART_TTL_DAYS = 30
# Default cart TTL for authenticated user carts (90 days)
_USER_CART_TTL_DAYS = 90


# ── Helpers ────────────────────────────────────────────────────────────────


async def _enrich_cart_item(
    db: AsyncSession,
    cart_item: CartItem,
) -> CartItemResponse:
    """Build a ``CartItemResponse`` with live product / variant data."""
    stmt = (
        select(ProductVariant)
        .options(selectinload(ProductVariant.product))
        .where(ProductVariant.id == cart_item.variant_id)
    )
    result = await db.execute(stmt)
    variant = result.scalar_one_or_none()

    # Get primary image
    image_url: str | None = None
    if variant is not None:
        img_stmt = (
            select(ProductImage.url)
            .where(ProductImage.product_id == variant.product_id)
            .order_by(ProductImage.is_primary.desc(), ProductImage.position.asc())
            .limit(1)
        )
        img_result = await db.execute(img_stmt)
        image_url = img_result.scalar_one_or_none()

    # Check stock availability
    is_available = True
    if variant is not None:
        inv_stmt = select(InventoryItem).where(InventoryItem.variant_id == variant.id)
        inv_result = await db.execute(inv_stmt)
        inv_item = inv_result.scalar_one_or_none()
        if inv_item is not None and inv_item.track_inventory:
            is_available = inv_item.available >= cart_item.quantity

    return CartItemResponse(
        id=cart_item.id,
        variant_id=cart_item.variant_id,
        quantity=cart_item.quantity,
        price_snapshot=cart_item.price_snapshot,
        subtotal=cart_item.quantity * cart_item.price_snapshot,
        product_name=variant.product.name if variant and variant.product else None,
        variant_info=(str(variant.attributes) if variant and variant.attributes else None),
        sku=variant.sku if variant else None,
        current_price=variant.price if variant else None,
        image_url=image_url,
        is_available=is_available,
    )


async def _build_cart_response(
    db: AsyncSession,
    cart: Cart,
) -> CartResponse:
    """Enrich every item and compute aggregated totals."""
    enriched_items: list[CartItemResponse] = []
    for ci in cart.items:
        enriched_items.append(await _enrich_cart_item(db, ci))

    subtotal = sum(item.subtotal for item in enriched_items)
    item_count = sum(item.quantity for item in enriched_items)

    tracer = get_tracer()
    with tracer.start_as_current_span("cart.build_response") as span:
        span.set_attribute("cart.id", str(cart.id))
        span.set_attribute("cart.items_count", item_count)

    return CartResponse(
        id=cart.id,
        user_id=cart.user_id,
        session_id=cart.session_id,
        status=cart.status.value,
        items=enriched_items,
        subtotal=subtotal,
        item_count=item_count,
        expires_at=cart.expires_at,
        created_at=cart.created_at,
        updated_at=cart.updated_at,
    )


# ── Public API ─────────────────────────────────────────────────────────────


async def get_or_create_cart(
    db: AsyncSession,
    user_id: uuid.UUID | None = None,
    session_id: str | None = None,
) -> Cart:
    """Find the active cart for a user or session, or create one."""
    if user_id is None and session_id is None:
        raise ValidationError("Either user_id or session_id is required")

    # Try to find an existing active cart
    stmt = select(Cart).options(selectinload(Cart.items)).where(Cart.status == CartStatus.ACTIVE)
    if user_id is not None:
        stmt = stmt.where(Cart.user_id == user_id)
    else:
        stmt = stmt.where(Cart.session_id == session_id)

    result = await db.execute(stmt)
    cart = result.scalar_one_or_none()

    # Check TTL
    if cart is not None and cart.expires_at and cart.expires_at < datetime.now(UTC):
        cart.status = CartStatus.ABANDONED
        await db.flush()
        cart = None  # Will create a new one below

    if cart is None:
        ttl_days = _USER_CART_TTL_DAYS if user_id else _GUEST_CART_TTL_DAYS
        cart = Cart(
            user_id=user_id,
            session_id=session_id,
            status=CartStatus.ACTIVE,
            expires_at=datetime.now(UTC) + timedelta(days=ttl_days),
            last_activity_at=datetime.now(UTC),
        )
        db.add(cart)
        await db.flush()
        # Refresh to get the relationship
        await db.refresh(cart, attribute_names=["items"])
        await logger.ainfo(
            "cart_created",
            cart_id=str(cart.id),
            user_id=str(user_id) if user_id else None,
            session_id=session_id,
        )

    return cart


async def _resolve_line_price(
    db: AsyncSession,
    variant: ProductVariant,
    quantity: int,
    user_id: uuid.UUID | None = None,
) -> int:
    """Unit price for a cart line: tier price when brackets apply, else list price.

    Karta findPrice (Sprint 1.6): one server-side resolver for every channel,
    so a client can never dictate a unit price. When ``user_id`` is known the
    shopper's price-list segment (Odoo product.pricelist concept) is layered
    on top of the volume-tier price.
    """
    from app.modules.inventory.application import pricing_service

    user_segment = None
    if user_id is not None:
        from app.modules.pricing.application.segment_resolver import resolve_user_segment

        user_segment = await resolve_user_segment(db, user_id)

    return await pricing_service.resolve_unit_price(
        db,
        product_id=variant.product_id,
        base_unit_price=variant.price,
        quantity=quantity,
        user_segment=user_segment,
        variant_id=variant.id,
    )


async def _validate_order_quantity(
    db: AsyncSession,
    variant: ProductVariant,
    quantity: int,
) -> None:
    """Enforce product-level min/max per invoice (Karta Sprint 1.5).

    Backend is the source of truth; the storefront stepper only mirrors it.
    """
    product = await db.get(Product, variant.product_id)
    if product is None:
        return
    min_q = int(product.min_order_quantity or 1)
    max_q = product.max_order_quantity
    if quantity < min_q:
        raise ValidationError(
            detail=f"حداقل تعداد خرید این کالا {min_q} عدد است",
            error_code="MIN_ORDER_QUANTITY",
        )
    if max_q is not None and quantity > int(max_q):
        raise ValidationError(
            detail=f"حداکثر تعداد خرید این کالا {int(max_q)} عدد است",
            error_code="MAX_ORDER_QUANTITY",
        )


async def add_item(
    db: AsyncSession,
    cart_id: uuid.UUID,
    variant_id: uuid.UUID,
    quantity: int,
) -> CartResponse:
    """Add an item to the cart (or increment its quantity)."""
    if quantity <= 0:
        raise ValidationError("Quantity must be positive")

    # Get the variant and its price
    variant_stmt = select(ProductVariant).where(
        ProductVariant.id == variant_id,
        ProductVariant.is_active.is_(True),
    )
    variant_result = await db.execute(variant_stmt)
    variant = variant_result.scalar_one_or_none()
    if variant is None:
        raise NotFoundError(resource="ProductVariant", detail="Variant not found or inactive")

    # Check stock availability
    inv_stmt = select(InventoryItem).where(InventoryItem.variant_id == variant_id)
    inv_result = await db.execute(inv_stmt)
    inv_item = inv_result.scalar_one_or_none()
    if (
        inv_item is not None
        and inv_item.track_inventory
        and inv_item.available < quantity
    ):
        raise ConflictError(
            detail=f"Insufficient stock: requested {quantity}, available {inv_item.available}"
        )

    # Load cart with items
    cart_stmt = (
        select(Cart)
        .options(selectinload(Cart.items))
        .where(Cart.id == cart_id, Cart.status == CartStatus.ACTIVE)
    )
    cart_result = await db.execute(cart_stmt)
    cart = cart_result.scalar_one_or_none()
    if cart is None:
        raise NotFoundError(resource="Cart", detail="Active cart not found")

    # Check if this variant is already in the cart
    existing_item: CartItem | None = None
    for ci in cart.items:
        if ci.variant_id == variant_id:
            existing_item = ci
            break

    if existing_item is not None:
        new_qty = existing_item.quantity + quantity
        # Re-check stock for increased quantity
        if (
            inv_item is not None
            and inv_item.track_inventory
            and inv_item.available < new_qty
        ):
            raise ConflictError(
                detail=(
                    f"Insufficient stock for total quantity {new_qty}: "
                    f"available {inv_item.available}"
                )
            )
        await _validate_order_quantity(db, variant, new_qty)
        existing_item.quantity = new_qty
        # Tier-aware price snapshot (Sprint 1.6)
        existing_item.price_snapshot = await _resolve_line_price(db, variant, new_qty, user_id=cart.user_id)
    else:
        await _validate_order_quantity(db, variant, quantity)
        new_item = CartItem(
            cart_id=cart_id,
            variant_id=variant_id,
            quantity=quantity,
            price_snapshot=await _resolve_line_price(db, variant, quantity, user_id=cart.user_id),
        )
        db.add(new_item)
        cart.items.append(new_item)

    cart.last_activity_at = datetime.now(UTC)
    await db.flush()
    await logger.ainfo(
        "cart_item_added",
        cart_id=str(cart_id),
        variant_id=str(variant_id),
        quantity=quantity,
    )
    from app.shared.events.domain_events import CartItemAdded, record_domain_event

    await record_domain_event(
        CartItemAdded(
            cart_id=cart_id,
            variant_id=variant_id,
            quantity=quantity,
            user_id=cart.user_id,
        ),
        aggregate_type="cart",
        aggregate_id=cart_id,
    )
    return await _build_cart_response(db, cart)


async def update_item_quantity(
    db: AsyncSession,
    cart_id: uuid.UUID,
    item_id: uuid.UUID,
    quantity: int,
) -> CartResponse:
    """Update the quantity for an existing cart item (0 removes it)."""
    cart_stmt = (
        select(Cart)
        .options(selectinload(Cart.items))
        .where(Cart.id == cart_id, Cart.status == CartStatus.ACTIVE)
    )
    cart_result = await db.execute(cart_stmt)
    cart = cart_result.scalar_one_or_none()
    if cart is None:
        raise NotFoundError(resource="Cart", detail="Active cart not found")

    item: CartItem | None = None
    for ci in cart.items:
        if ci.id == item_id:
            item = ci
            break

    if item is None:
        raise NotFoundError(resource="CartItem")

    from app.shared.events.domain_events import (
        CartItemRemoved,
        CartItemUpdated,
        record_domain_event,
    )

    if quantity == 0:
        await db.delete(item)
        cart.items.remove(item)
        await logger.ainfo("cart_item_removed", cart_id=str(cart_id), item_id=str(item_id))
        await record_domain_event(
            CartItemRemoved(
                cart_id=cart_id,
                item_id=item_id,
                user_id=cart.user_id,
            ),
            aggregate_type="cart",
            aggregate_id=cart_id,
        )
    else:
        # Check stock availability for new quantity
        inv_stmt = select(InventoryItem).where(InventoryItem.variant_id == item.variant_id)
        inv_result = await db.execute(inv_stmt)
        inv_item = inv_result.scalar_one_or_none()
        if (
            inv_item
            and inv_item.track_inventory
            and inv_item.available < quantity
        ):
            raise ConflictError(
                detail=f"Insufficient stock: requested {quantity}, available {inv_item.available}"
            )

        # Refresh price snapshot with tier-aware unit price (Sprint 1.6)
        variant_stmt = select(ProductVariant).where(ProductVariant.id == item.variant_id)
        variant_result = await db.execute(variant_stmt)
        variant = variant_result.scalar_one_or_none()
        if variant is not None:
            await _validate_order_quantity(db, variant, quantity)
            item.price_snapshot = await _resolve_line_price(db, variant, quantity, user_id=cart.user_id)

        item.quantity = quantity
        await logger.ainfo(
            "cart_item_updated",
            cart_id=str(cart_id),
            item_id=str(item_id),
            quantity=quantity,
        )
        await record_domain_event(
            CartItemUpdated(
                cart_id=cart_id,
                item_id=item_id,
                quantity=quantity,
                user_id=cart.user_id,
            ),
            aggregate_type="cart",
            aggregate_id=cart_id,
        )

    cart.last_activity_at = datetime.now(UTC)
    await db.flush()
    return await _build_cart_response(db, cart)


async def remove_item(
    db: AsyncSession,
    cart_id: uuid.UUID,
    item_id: uuid.UUID,
) -> CartResponse:
    """Remove a specific item from the cart."""
    return await update_item_quantity(db, cart_id, item_id, quantity=0)


async def get_cart(
    db: AsyncSession,
    cart_id: uuid.UUID,
) -> CartResponse:
    """Get a fully enriched cart with product info, prices, and totals."""
    stmt = (
        select(Cart)
        .options(selectinload(Cart.items))
        .where(Cart.id == cart_id, Cart.status == CartStatus.ACTIVE)
    )
    result = await db.execute(stmt)
    cart = result.scalar_one_or_none()
    if cart is None:
        raise NotFoundError(resource="Cart", detail="Active cart not found")
    return await _build_cart_response(db, cart)


async def get_cart_by_owner(
    db: AsyncSession,
    user_id: uuid.UUID | None = None,
    session_id: str | None = None,
) -> CartResponse:
    """Get the active cart for a user or session, enriched with product info."""
    cart = await get_or_create_cart(db, user_id=user_id, session_id=session_id)
    return await _build_cart_response(db, cart)


async def merge_carts(
    db: AsyncSession,
    guest_session_id: str,
    user_id: uuid.UUID,
) -> CartResponse:
    """Merge a guest cart into the authenticated user's cart.

    Items from the guest cart are moved into the user's active cart.  If both
    carts contain the same variant, quantities are summed.  The guest cart is
    marked as ``MERGED`` afterwards.
    """
    # Load both carts
    guest_stmt = (
        select(Cart)
        .options(selectinload(Cart.items))
        .where(
            Cart.session_id == guest_session_id,
            Cart.status == CartStatus.ACTIVE,
        )
    )
    guest_result = await db.execute(guest_stmt)
    guest_cart = guest_result.scalar_one_or_none()

    if guest_cart is None:
        # No guest cart to merge — just return the user's cart
        return await get_cart_by_owner(db, user_id=user_id)

    # Get or create user cart
    user_cart = await get_or_create_cart(db, user_id=user_id)

    # Build a lookup of the user cart's items by variant_id
    user_items_map: dict[uuid.UUID, CartItem] = {ci.variant_id: ci for ci in user_cart.items}

    for guest_item in guest_cart.items:
        if guest_item.variant_id in user_items_map:
            # Merge quantities — keep the higher price snapshot (more recent)
            existing = user_items_map[guest_item.variant_id]
            existing.quantity += guest_item.quantity
            existing.price_snapshot = max(existing.price_snapshot, guest_item.price_snapshot)
        else:
            # Move the item to the user's cart
            new_item = CartItem(
                cart_id=user_cart.id,
                variant_id=guest_item.variant_id,
                quantity=guest_item.quantity,
                price_snapshot=guest_item.price_snapshot,
            )
            db.add(new_item)
            user_cart.items.append(new_item)

    # Mark guest cart as merged
    guest_cart.status = CartStatus.MERGED
    await db.flush()

    await logger.ainfo(
        "carts_merged",
        guest_session_id=guest_session_id,
        user_id=str(user_id),
        guest_cart_id=str(guest_cart.id),
        user_cart_id=str(user_cart.id),
        items_merged=len(guest_cart.items),
    )

    return await _build_cart_response(db, user_cart)


async def validate_cart(
    db: AsyncSession,
    cart_id: uuid.UUID,
) -> CartValidationResponse:
    """Check every item in the cart against current catalog and inventory.

    Returns a list of issues (price changes, out of stock, inactive variants)
    and auto-corrects price snapshots.
    """
    cart_stmt = (
        select(Cart)
        .options(selectinload(Cart.items))
        .where(Cart.id == cart_id, Cart.status == CartStatus.ACTIVE)
    )
    cart_result = await db.execute(cart_stmt)
    cart = cart_result.scalar_one_or_none()
    if cart is None:
        raise NotFoundError(resource="Cart", detail="Active cart not found")

    issues: list[CartValidationIssue] = []

    for ci in list(cart.items):
        variant_stmt = select(ProductVariant).where(ProductVariant.id == ci.variant_id)
        variant_result = await db.execute(variant_stmt)
        variant = variant_result.scalar_one_or_none()

        if variant is None or not variant.is_active:
            issues.append(
                CartValidationIssue(
                    variant_id=ci.variant_id,
                    issue="variant_unavailable",
                )
            )
            await db.delete(ci)
            cart.items.remove(ci)
            continue

        # Check price change (tier-aware: a bracket price is legitimate)
        expected_unit_price = await _resolve_line_price(db, variant, ci.quantity, user_id=cart.user_id)
        if expected_unit_price != ci.price_snapshot:
            issues.append(
                CartValidationIssue(
                    variant_id=ci.variant_id,
                    issue="price_changed",
                    old_value=ci.price_snapshot,
                    new_value=expected_unit_price,
                )
            )
            ci.price_snapshot = expected_unit_price

        # Check stock
        inv_stmt = select(InventoryItem).where(InventoryItem.variant_id == ci.variant_id)
        inv_result = await db.execute(inv_stmt)
        inv_item = inv_result.scalar_one_or_none()

        if inv_item is not None and inv_item.track_inventory:
            if inv_item.available <= 0:
                issues.append(
                    CartValidationIssue(
                        variant_id=ci.variant_id,
                        issue="out_of_stock",
                        old_value=ci.quantity,
                        new_value=0,
                    )
                )
                await db.delete(ci)
                cart.items.remove(ci)
            elif inv_item.available < ci.quantity:
                issues.append(
                    CartValidationIssue(
                        variant_id=ci.variant_id,
                        issue="quantity_reduced",
                        old_value=ci.quantity,
                        new_value=inv_item.available,
                    )
                )
                ci.quantity = inv_item.available

    await db.flush()

    cart_response = await _build_cart_response(db, cart)
    return CartValidationResponse(
        is_valid=len(issues) == 0,
        issues=issues,
        cart=cart_response,
    )


async def clear_cart(
    db: AsyncSession,
    cart_id: uuid.UUID,
) -> CartResponse:
    """Remove all items from the cart."""
    cart_stmt = (
        select(Cart)
        .options(selectinload(Cart.items))
        .where(Cart.id == cart_id, Cart.status == CartStatus.ACTIVE)
    )
    cart_result = await db.execute(cart_stmt)
    cart = cart_result.scalar_one_or_none()
    if cart is None:
        raise NotFoundError(resource="Cart", detail="Active cart not found")

    # Delete all items
    await db.execute(delete(CartItem).where(CartItem.cart_id == cart_id))
    cart.items.clear()
    await db.flush()

    await logger.ainfo("cart_cleared", cart_id=str(cart_id))
    from app.shared.events.domain_events import CartCleared, record_domain_event

    await record_domain_event(
        CartCleared(
            cart_id=cart_id,
            user_id=cart.user_id,
        ),
        aggregate_type="cart",
        aggregate_id=cart_id,
    )
    return await _build_cart_response(db, cart)
