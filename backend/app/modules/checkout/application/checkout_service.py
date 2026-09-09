"""Checkout application service — order creation with full transactional integrity."""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions.handlers import ConflictError, NotFoundError, ValidationError
from app.modules.cart.domain.models import Cart, CartItem, CartStatus
from app.modules.catalog.domain.models import Product, ProductVariant
from app.modules.checkout.schemas.checkout import (
    CheckoutLineItem,
    CheckoutQuoteRequest,
    CheckoutQuoteResponse,
    CheckoutValidationIssue,
    CheckoutValidationResponse,
    CreateOrderRequest,
    CreateOrderResponse,
)
from app.modules.discounts.domain.models import Coupon, Discount, DiscountType
from app.modules.inventory.application import inventory_service
from app.modules.inventory.domain.models import InventoryItem
from app.modules.orders.domain.models import Order, OrderItem, OrderStatus, OrderStatusHistory
from app.modules.shipping.domain.models import ShippingMethod, ShippingRate
from app.modules.users.domain.models import Address

logger: structlog.stdlib.BoundLogger = structlog.get_logger()


# ── Helpers ────────────────────────────────────────────────────────────────


def _generate_order_number() -> str:
    """Generate a unique, human-readable order number.

    Format: ``EC-<timestamp_hex>-<random>``  (approx 18 chars).
    """
    ts_part = hex(int(datetime.now(timezone.utc).timestamp()))[2:].upper()
    rand_part = secrets.token_hex(3).upper()
    return f"EC-{ts_part}-{rand_part}"


async def _load_active_cart(
    db: AsyncSession,
    cart_id: uuid.UUID,
) -> Cart:
    stmt = (
        select(Cart)
        .options(selectinload(Cart.items))
        .where(Cart.id == cart_id, Cart.status == CartStatus.ACTIVE)
    )
    result = await db.execute(stmt)
    cart = result.scalar_one_or_none()
    if cart is None:
        raise NotFoundError(resource="Cart", detail="Active cart not found")
    if not cart.items:
        raise ValidationError("Cart is empty")
    return cart


async def _load_address(
    db: AsyncSession,
    address_id: uuid.UUID,
    user_id: uuid.UUID,
) -> Address:
    stmt = select(Address).where(Address.id == address_id, Address.user_id == user_id)
    result = await db.execute(stmt)
    addr = result.scalar_one_or_none()
    if addr is None:
        raise NotFoundError(resource="Address", detail="Address not found or not owned by user")
    return addr


async def _load_shipping_method(
    db: AsyncSession,
    method_id: uuid.UUID,
) -> ShippingMethod:
    stmt = (
        select(ShippingMethod)
        .options(selectinload(ShippingMethod.rates))
        .where(ShippingMethod.id == method_id, ShippingMethod.is_active == True)
    )
    result = await db.execute(stmt)
    method = result.scalar_one_or_none()
    if method is None:
        raise NotFoundError(resource="ShippingMethod", detail="Shipping method not found or inactive")
    return method


async def _calculate_shipping(
    db: AsyncSession,
    method: ShippingMethod,
    province: str,
    subtotal: int,
) -> int:
    """Find the best matching shipping rate for the given province and subtotal."""
    # Try province-specific rate first, then fallback to generic
    stmt = (
        select(ShippingRate)
        .where(ShippingRate.method_id == method.id)
        .order_by(
            # Prefer province-specific rates
            (ShippingRate.province == province).desc(),
            ShippingRate.min_order_amount.desc().nulls_last(),
        )
    )
    result = await db.execute(stmt)
    rates = list(result.scalars().all())

    for rate in rates:
        # Check province match
        if rate.province is not None and rate.province != province:
            continue
        # Check minimum order amount
        if rate.min_order_amount is not None and subtotal < rate.min_order_amount:
            continue
        return rate.price

    # If no rate found, return 0 (free shipping) — could also raise an error
    if rates:
        # Fallback to the first generic rate
        for rate in rates:
            if rate.province is None:
                return rate.price

    return 0


async def _apply_coupon(
    db: AsyncSession,
    coupon_code: str,
    subtotal: int,
    user_id: uuid.UUID,
) -> tuple[int, str]:
    """Validate and apply a coupon code. Returns (discount_amount, coupon_code)."""
    stmt = (
        select(Coupon)
        .options(selectinload(Coupon.discount))
        .where(Coupon.code == coupon_code.upper(), Coupon.is_active == True)
    )
    result = await db.execute(stmt)
    coupon = result.scalar_one_or_none()

    if coupon is None:
        raise ValidationError(f"Coupon code '{coupon_code}' is not valid")

    now = datetime.now(timezone.utc)
    if now < coupon.starts_at or now > coupon.ends_at:
        raise ValidationError("Coupon has expired or is not yet active")

    if coupon.usage_limit is not None and coupon.usage_count >= coupon.usage_limit:
        raise ValidationError("Coupon usage limit reached")

    discount = coupon.discount
    if discount is None or not discount.is_active:
        raise ValidationError("Discount rule is inactive")

    if now < discount.starts_at or now > discount.ends_at:
        raise ValidationError("Discount has expired")

    if discount.min_cart_amount is not None and subtotal < discount.min_cart_amount:
        raise ValidationError(
            f"Minimum cart amount for this coupon is {discount.min_cart_amount // 10:,} Toman"
        )

    # Calculate discount
    if discount.type == DiscountType.FIXED:
        discount_amount = discount.value
    elif discount.type in (DiscountType.PERCENTAGE, DiscountType.FIRST_ORDER):
        discount_amount = subtotal * discount.value // 100
    else:
        discount_amount = 0

    # Cap at max_discount if set
    if discount.max_discount is not None:
        discount_amount = min(discount_amount, discount.max_discount)

    # Never discount more than the subtotal
    discount_amount = min(discount_amount, subtotal)

    return discount_amount, coupon.code


async def _build_line_items(
    db: AsyncSession,
    cart: Cart,
) -> list[CheckoutLineItem]:
    """Resolve product info for each cart item."""
    items: list[CheckoutLineItem] = []
    for ci in cart.items:
        stmt = (
            select(ProductVariant)
            .options(selectinload(ProductVariant.product))
            .where(ProductVariant.id == ci.variant_id)
        )
        result = await db.execute(stmt)
        variant = result.scalar_one_or_none()
        if variant is None:
            raise ValidationError(f"Variant {ci.variant_id} no longer exists")

        items.append(
            CheckoutLineItem(
                variant_id=variant.id,
                product_name=variant.product.name if variant.product else "Unknown",
                sku=variant.sku,
                quantity=ci.quantity,
                unit_price=variant.price,
                subtotal=variant.price * ci.quantity,
            )
        )
    return items


# ── Public API ─────────────────────────────────────────────────────────────


async def calculate_quote(
    db: AsyncSession,
    user_id: uuid.UUID,
    data: CheckoutQuoteRequest,
) -> CheckoutQuoteResponse:
    """Calculate a complete order quote without committing anything."""
    cart = await _load_active_cart(db, data.cart_id)

    # Verify ownership
    if cart.user_id != user_id:
        raise ValidationError("Cart does not belong to the authenticated user")

    address = await _load_address(db, data.address_id, user_id)
    shipping_method = await _load_shipping_method(db, data.shipping_method_id)

    # Build line items with live prices
    line_items = await _build_line_items(db, cart)
    subtotal = sum(item.subtotal for item in line_items)

    # Shipping
    shipping_cost = await _calculate_shipping(db, shipping_method, address.province, subtotal)

    # Discount
    discount_amount = 0
    coupon_applied: str | None = None
    if data.coupon_code:
        discount_amount, coupon_applied = await _apply_coupon(
            db, data.coupon_code, subtotal, user_id
        )

    # Tax — Iran currently has 9% VAT but many e-commerce platforms include
    # it in the item price.  We keep this at 0 and provide the hook.
    tax = 0

    total = subtotal + shipping_cost - discount_amount + tax
    total = max(total, 0)

    return CheckoutQuoteResponse(
        items=line_items,
        subtotal=subtotal,
        shipping_cost=shipping_cost,
        discount_amount=discount_amount,
        tax=tax,
        total=total,
        coupon_applied=coupon_applied,
    )


async def validate_checkout(
    db: AsyncSession,
    user_id: uuid.UUID,
    data: CheckoutQuoteRequest,
) -> CheckoutValidationResponse:
    """Validate that all checkout preconditions are satisfied."""
    issues: list[CheckoutValidationIssue] = []

    # 1. Cart
    try:
        cart = await _load_active_cart(db, data.cart_id)
        if cart.user_id != user_id:
            issues.append(CheckoutValidationIssue(
                field="cart_id", message="Cart does not belong to the authenticated user"
            ))
    except (NotFoundError, ValidationError) as e:
        issues.append(CheckoutValidationIssue(field="cart_id", message=str(e.detail)))
        return CheckoutValidationResponse(is_valid=False, issues=issues)

    # 2. Address
    try:
        await _load_address(db, data.address_id, user_id)
    except NotFoundError as e:
        issues.append(CheckoutValidationIssue(field="address_id", message=str(e.detail)))

    # 3. Shipping method
    try:
        await _load_shipping_method(db, data.shipping_method_id)
    except NotFoundError as e:
        issues.append(CheckoutValidationIssue(
            field="shipping_method_id", message=str(e.detail)
        ))

    # 4. Stock availability per item
    for ci in cart.items:
        variant_stmt = select(ProductVariant).where(
            ProductVariant.id == ci.variant_id, ProductVariant.is_active == True
        )
        variant_result = await db.execute(variant_stmt)
        variant = variant_result.scalar_one_or_none()
        if variant is None:
            issues.append(CheckoutValidationIssue(
                field=f"item_{ci.variant_id}",
                message=f"Variant {ci.variant_id} is no longer available",
            ))
            continue

        available = await inventory_service.check_availability(db, ci.variant_id, ci.quantity)
        if not available:
            issues.append(CheckoutValidationIssue(
                field=f"item_{ci.variant_id}",
                message=f"Insufficient stock for {variant.sku}",
            ))

    # 5. Coupon
    if data.coupon_code:
        try:
            subtotal = sum(ci.price_snapshot * ci.quantity for ci in cart.items)
            await _apply_coupon(db, data.coupon_code, subtotal, user_id)
        except ValidationError as e:
            issues.append(CheckoutValidationIssue(
                field="coupon_code", message=str(e.detail)
            ))

    return CheckoutValidationResponse(
        is_valid=len(issues) == 0,
        issues=issues,
    )


async def create_order(
    db: AsyncSession,
    user_id: uuid.UUID,
    data: CreateOrderRequest,
    ip_address: str | None = None,
) -> CreateOrderResponse:
    """Full checkout flow — atomic order creation.

    Steps:
    1. Idempotency check
    2. Validate cart items and stock
    3. Reserve inventory for every line item
    4. Apply discounts / coupons
    5. Create order with items
    6. Snapshot shipping address
    7. Mark cart as converted
    8. Return order for payment

    Everything runs inside the session's transaction — on any failure the
    entire operation is rolled back (including inventory reservations).
    """
    # ── 1. Idempotency ─────────────────────────────────────────────────
    existing_order_stmt = select(Order).where(
        Order.idempotency_key == data.idempotency_key
    )
    existing_result = await db.execute(existing_order_stmt)
    existing_order = existing_result.scalar_one_or_none()
    if existing_order is not None:
        await logger.ainfo(
            "idempotent_order_returned",
            order_id=str(existing_order.id),
            idempotency_key=data.idempotency_key,
        )
        return CreateOrderResponse(
            order_id=existing_order.id,
            order_number=existing_order.order_number,
            status=existing_order.status.value,
            subtotal=existing_order.subtotal,
            shipping_cost=existing_order.shipping_cost,
            discount_amount=existing_order.discount_amount,
            tax=existing_order.tax,
            total=existing_order.total,
            payment_url=None,
            created_at=existing_order.created_at,
        )

    # ── 2. Load and validate cart ──────────────────────────────────────
    cart = await _load_active_cart(db, data.cart_id)
    if cart.user_id != user_id:
        raise ValidationError("Cart does not belong to the authenticated user")

    # ── 3. Load address and shipping ───────────────────────────────────
    address = await _load_address(db, data.address_id, user_id)
    shipping_method = await _load_shipping_method(db, data.shipping_method_id)

    # Build line items (with live prices)
    line_items = await _build_line_items(db, cart)
    subtotal = sum(item.subtotal for item in line_items)

    # ── 4. Reserve inventory for each item ─────────────────────────────
    reservation_ids: list[uuid.UUID] = []
    for ci in cart.items:
        # Check availability before reserving
        available = await inventory_service.check_availability(db, ci.variant_id, ci.quantity)
        if not available:
            # Release any reservations we've already made
            for rid in reservation_ids:
                try:
                    await inventory_service.release_reservation(db, rid)
                except Exception:
                    pass  # Best-effort cleanup; the transaction will roll back anyway
            raise ConflictError(
                detail=f"Insufficient stock for variant {ci.variant_id}"
            )

        reservation = await inventory_service.reserve_stock(
            db,
            variant_id=ci.variant_id,
            quantity=ci.quantity,
            cart_id=cart.id,
            ttl_minutes=30,  # 30-minute reservation during checkout
        )
        reservation_ids.append(reservation.id)

    # ── 5. Apply discount / coupon ─────────────────────────────────────
    discount_amount = 0
    if data.coupon_code:
        discount_amount, _ = await _apply_coupon(db, data.coupon_code, subtotal, user_id)

    # ── 6. Calculate shipping ──────────────────────────────────────────
    shipping_cost = await _calculate_shipping(
        db, shipping_method, address.province, subtotal
    )

    # Tax
    tax = 0
    total = subtotal + shipping_cost - discount_amount + tax
    total = max(total, 0)

    # ── 7. Create order ────────────────────────────────────────────────
    order_number = _generate_order_number()

    # Snapshot address
    address_snapshot = {
        "title": address.title,
        "province": address.province,
        "city": address.city,
        "district": address.district,
        "postal_code": address.postal_code,
        "full_address": address.full_address,
        "lat": address.lat,
        "lng": address.lng,
    }

    order = Order(
        user_id=user_id,
        order_number=order_number,
        status=OrderStatus.PENDING,
        subtotal=subtotal,
        shipping_cost=shipping_cost,
        tax=tax,
        discount_amount=discount_amount,
        total=total,
        shipping_address_snapshot=address_snapshot,
        notes=data.notes,
        idempotency_key=data.idempotency_key,
        ip_address=ip_address,
    )
    db.add(order)
    await db.flush()  # Get order.id

    # ── 8. Create order items ──────────────────────────────────────────
    for li in line_items:
        order_item = OrderItem(
            order_id=order.id,
            variant_id=li.variant_id,
            product_name=li.product_name,
            variant_info=None,
            sku=li.sku,
            quantity=li.quantity,
            unit_price=li.unit_price,
            total_price=li.subtotal,
        )
        db.add(order_item)

    # ── 9. Status history ──────────────────────────────────────────────
    status_entry = OrderStatusHistory(
        order_id=order.id,
        from_status=None,
        to_status=OrderStatus.PENDING.value,
        changed_by=user_id,
        reason="Order created via checkout",
    )
    db.add(status_entry)

    # ── 10. Confirm inventory reservations ─────────────────────────────
    for rid in reservation_ids:
        await inventory_service.confirm_reservation(db, rid)

    # ── 11. Update coupon usage ────────────────────────────────────────
    if data.coupon_code:
        coupon_stmt = select(Coupon).where(
            Coupon.code == data.coupon_code.upper()
        ).with_for_update()
        coupon_result = await db.execute(coupon_stmt)
        coupon = coupon_result.scalar_one_or_none()
        if coupon is not None:
            coupon.usage_count += 1
            if coupon.discount:
                coupon.discount.usage_count += 1

    # ── 12. Mark cart as converted ─────────────────────────────────────
    cart.status = CartStatus.CONVERTED
    await db.flush()

    await logger.ainfo(
        "order_created",
        order_id=str(order.id),
        order_number=order_number,
        user_id=str(user_id),
        total=total,
        items=len(line_items),
    )

    # ── 13. Build response ─────────────────────────────────────────────
    # In a full implementation, payment_url would be generated by calling
    # the payment gateway.  For now we return None and let the payments
    # module handle gateway initialisation separately.
    return CreateOrderResponse(
        order_id=order.id,
        order_number=order.order_number,
        status=order.status.value,
        subtotal=subtotal,
        shipping_cost=shipping_cost,
        discount_amount=discount_amount,
        tax=tax,
        total=total,
        payment_url=None,
        created_at=order.created_at,
    )
