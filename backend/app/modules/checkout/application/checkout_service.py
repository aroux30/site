"""Checkout application service — order creation with full transactional integrity."""

from __future__ import annotations

import contextlib
import uuid
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.exceptions.handlers import ConflictError, NotFoundError, ValidationError
from app.core.observability.tracer import get_tracer
from app.modules.cart.domain.models import Cart, CartStatus
from app.modules.catalog.domain.models import ProductVariant
from app.modules.checkout.application.tax_service import TaxService
from app.modules.checkout.schemas.checkout import (
    CheckoutLineItem,
    CheckoutQuoteRequest,
    CheckoutQuoteResponse,
    CheckoutValidationIssue,
    CheckoutValidationResponse,
    CreateOrderRequest,
    CreateOrderResponse,
)
from app.modules.inventory.application import inventory_service
from app.modules.orders.domain.models import Order, OrderItem, OrderStatus, OrderStatusHistory
from app.modules.shipping.domain.models import ShippingMethod, ShippingRate
from app.modules.users.domain.models import Address

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
logger: structlog.stdlib.BoundLogger = structlog.get_logger()


# ── Helpers ────────────────────────────────────────────────────────────────


async def _load_active_cart(
    db: AsyncSession,
    cart_id: uuid.UUID,
) -> Cart:
    stmt = (
        select(Cart)
        .options(selectinload(Cart.items))
        .where(Cart.id == cart_id, Cart.status == CartStatus.ACTIVE)
        .with_for_update()
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
        .where(ShippingMethod.id == method_id, ShippingMethod.is_active.is_(True))
    )
    result = await db.execute(stmt)
    method = result.scalar_one_or_none()
    if method is None:
        raise NotFoundError(
            resource="ShippingMethod", detail="Shipping method not found or inactive"
        )
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

    # No matching rate: a misconfigured rate table must fail the checkout,
    # never silently ship for free.
    raise ValidationError(
        "هیچ نرخ ارسالی برای این استان / مبلغ سفارش یافت نشد",
        error_code="NO_SHIPPING_RATE",
    )


async def _resolve_buyer_segment(db: AsyncSession, user_id: uuid.UUID) -> Any:
    """The shopper's price-list segment for this checkout (loyalty-tier derived)."""
    from app.modules.pricing.application.segment_resolver import resolve_user_segment

    return await resolve_user_segment(db, user_id)


async def _resolve_line_tax_identities(
    db: AsyncSession,
    cart: Cart,
) -> dict[uuid.UUID, dict[str, Any]]:
    """Map cart-item id → {product_id, category_id} for tax override resolution.

    The v1 tax engine resolves product > category > default per line, so the
    checkout flow needs each line's catalog identity (not exposed on the
    public CheckoutLineItem schema).
    """
    from app.modules.catalog.domain.models import Product

    variant_ids = [ci.variant_id for ci in cart.items]
    if not variant_ids:
        return {}
    stmt = (
        select(ProductVariant.id, ProductVariant.product_id, Product.category_id)
        .join(Product, Product.id == ProductVariant.product_id)
        .where(ProductVariant.id.in_(variant_ids))
    )
    rows = (await db.execute(stmt)).all()
    by_variant = {row[0]: {"product_id": row[1], "category_id": row[2]} for row in rows}
    return {
        ci.id: by_variant.get(
            ci.variant_id, {"product_id": None, "category_id": None}
        )
        for ci in cart.items
    }


async def _coupon_scope_items(
    db: AsyncSession,
    cart: Cart,
    segment: Any | None = None,
) -> list[dict[str, Any]]:
    """Build the per-item identity/subtotal list used for scoped coupons.

    Each entry carries ``product_id`` / ``category_id`` / ``brand_id`` /
    ``variant_id`` plus the item ``subtotal`` so the discounts service can
    compute a scope-aware basis instead of discounting the whole cart.
    """
    from app.modules.catalog.domain.models import Product

    variant_ids = [ci.variant_id for ci in cart.items]
    if not variant_ids:
        return []

    stmt = (
        select(
            ProductVariant.id,
            ProductVariant.product_id,
            Product.category_id,
            Product.brand_id,
            ProductVariant.price,
        )
        .join(Product, Product.id == ProductVariant.product_id)
        .where(ProductVariant.id.in_(variant_ids))
    )
    rows = (await db.execute(stmt)).all()
    info = {row[0]: row for row in rows}

    items: list[dict[str, Any]] = []
    for ci in cart.items:
        row = info.get(ci.variant_id)
        # Tier-aware live unit price — the coupon basis must match the money
        # math, which is computed by the same resolver at order creation.
        from app.modules.inventory.application import pricing_service as _pricing

        if row:
            live_price = await _pricing.resolve_unit_price(
                db,
                product_id=row[1],
                base_unit_price=row[4],
                quantity=ci.quantity,
                user_segment=segment,
                variant_id=ci.variant_id,
            )
        else:
            live_price = ci.price_snapshot
        items.append(
            {
                "variant_id": str(ci.variant_id),
                "product_id": str(row[1]) if row else None,
                "category_id": str(row[2]) if row else None,
                "brand_id": str(row[3]) if row else None,
                "subtotal": live_price * ci.quantity,
            }
        )
    return items


async def _apply_coupon(
    db: AsyncSession,
    coupon_code: str,
    subtotal: int,
    user_id: uuid.UUID,
    items: list[dict[str, Any]] | None = None,
) -> tuple[int, str, uuid.UUID]:
    """Validate a coupon via the canonical discounts service.

    Returns ``(discount_amount, code, coupon_id)``. All coupon business
    rules — usage limits, per-user redemption caps, scope coverage, and
    basis-point percentage math — live in ``discounts``; checkout must not
    duplicate them (an inline percent-vs-basis-point mismatch here used to
    discount 100× too much).
    """
    from app.modules.discounts.application import discount_service

    try:
        result = await discount_service.validate_coupon(
            db, code=coupon_code, user_id=user_id, cart_total=subtotal, items=items
        )
    except NotFoundError:
        raise ValidationError(f"Coupon code '{coupon_code}' is not valid") from None
    return result.discount_amount, result.code, result.coupon_id


async def _build_line_items(
    db: AsyncSession,
    cart: Cart,
    segment: Any | None = None,
) -> list[CheckoutLineItem]:
    """Resolve product info for each cart item with tier-aware pricing."""
    from app.modules.inventory.application import pricing_service

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

        unit_price = await pricing_service.resolve_unit_price(
            db,
            product_id=variant.product_id,
            base_unit_price=variant.price,
            quantity=ci.quantity,
            user_segment=segment,
            variant_id=variant.id,
        )
        items.append(
            CheckoutLineItem(
                cart_item_id=ci.id,
                variant_id=variant.id,
                product_name=variant.product.name if variant.product else "Unknown",
                sku=variant.sku,
                quantity=ci.quantity,
                unit_price=unit_price,
                subtotal=unit_price * ci.quantity,
            )
        )
    return items


async def _validate_line_quantities(db: AsyncSession, cart: Cart) -> None:
    """Re-enforce product min/max per invoice at order time (Sprint 1.5)."""
    from app.modules.catalog.domain.models import Product as _Product

    for ci in cart.items:
        variant = await db.get(ProductVariant, ci.variant_id)
        if variant is None:
            continue
        product = await db.get(_Product, variant.product_id)
        if product is None:
            continue
        min_q = int(product.min_order_quantity or 1)
        max_q = product.max_order_quantity
        if ci.quantity < min_q:
            raise ValidationError(
                detail=f"حداقل تعداد خرید «{product.name}» {min_q} عدد است",
                error_code="MIN_ORDER_QUANTITY",
            )
        if max_q is not None and ci.quantity > int(max_q):
            raise ValidationError(
                detail=f"حداکثر تعداد خرید «{product.name}» {int(max_q)} عدد است",
                error_code="MAX_ORDER_QUANTITY",
            )


async def _resolve_item_custom_fields(
    db: AsyncSession,
    cart: Cart,
    item_fields: dict[str, dict[str, Any]] | None,
) -> dict[uuid.UUID, dict[str, Any]]:
    """Validate dynamic category-field answers per cart item (Sprint 1.7).

    Karta categoryFields: required fields must be answered, unknown keys and
    bad option values are rejected, and only validated data is persisted
    with the order items.
    """
    from app.modules.catalog.domain.models import Product as _Product
    from app.modules.inventory.application import custom_field_service

    validated: dict[uuid.UUID, dict[str, Any]] = {}
    if not item_fields:
        return validated

    for ci in cart.items:
        answers = item_fields.get(str(ci.id)) or {}
        variant = await db.get(ProductVariant, ci.variant_id)
        if variant is None:
            continue
        product = await db.get(_Product, variant.product_id)
        if product is None or product.category_id is None:
            if answers:
                raise ValidationError(
                    detail="این کالا فیلد سفارشی ندارد",
                    error_code="CUSTOM_FIELDS_NOT_ALLOWED",
                )
            continue
        validated[ci.id] = await custom_field_service.validate_answers(
            db, category_id=product.category_id, answers=answers
        )
    return validated


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
    segment = await _resolve_buyer_segment(db, user_id)
    line_items = await _build_line_items(db, cart, segment=segment)
    subtotal = sum(item.subtotal for item in line_items)

    # Shipping
    shipping_cost = await _calculate_shipping(db, shipping_method, address.province, subtotal)

    # Discount
    discount_amount = 0
    coupon_applied: str | None = None
    if data.coupon_code:
        coupon_items = await _coupon_scope_items(db, cart, segment=segment)
        discount_amount, coupon_applied, _coupon_id = await _apply_coupon(
            db, data.coupon_code, subtotal, user_id, items=coupon_items
        )

    # Tax calculation via authoritative server-side TaxService
    tax_info = await TaxService.calculate_tax(
        db, taxable_amount_rials=max(subtotal - discount_amount, 0)
    )
    tax = tax_info["tax_amount_rials"]

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
            issues.append(
                CheckoutValidationIssue(
                    field="cart_id", message="Cart does not belong to the authenticated user"
                )
            )
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
        issues.append(CheckoutValidationIssue(field="shipping_method_id", message=str(e.detail)))

    # 4. Stock availability per item
    for ci in cart.items:
        variant_stmt = select(ProductVariant).where(
            ProductVariant.id == ci.variant_id, ProductVariant.is_active.is_(True)
        )
        variant_result = await db.execute(variant_stmt)
        variant = variant_result.scalar_one_or_none()
        if variant is None:
            issues.append(
                CheckoutValidationIssue(
                    field=f"item_{ci.variant_id}",
                    message=f"Variant {ci.variant_id} is no longer available",
                )
            )
            continue

        available = await inventory_service.check_availability(db, ci.variant_id, ci.quantity)
        if not available:
            issues.append(
                CheckoutValidationIssue(
                    field=f"item_{ci.variant_id}",
                    message=f"Insufficient stock for {variant.sku}",
                )
            )

    # 5. Coupon
    if data.coupon_code:
        try:
            segment = await _resolve_buyer_segment(db, user_id)
            subtotal = sum(ci.price_snapshot * ci.quantity for ci in cart.items)
            coupon_items = await _coupon_scope_items(db, cart, segment=segment)
            await _apply_coupon(db, data.coupon_code, subtotal, user_id, items=coupon_items)
        except ValidationError as e:
            issues.append(CheckoutValidationIssue(field="coupon_code", message=str(e.detail)))

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
    # ── 1. Idempotency (Redis Distributed Lock + DB Check) ─────────────
    from app.core.cache.redis import get_redis
    from app.core.config.settings import get_settings

    settings = get_settings()
    redis_client = await get_redis()
    lock_key = f"{settings.REDIS_KEY_PREFIX}idempotency:checkout:{data.idempotency_key}"

    # Try acquiring distributed lock atomically to prevent concurrent submissions
    is_locked = await redis_client.set(lock_key, "processing", nx=True, ex=120)
    if not is_locked:
        existing_order_stmt = select(Order).where(Order.idempotency_key == data.idempotency_key)
        existing_result = await db.execute(existing_order_stmt)
        existing_order = existing_result.scalar_one_or_none()
        if existing_order is not None:
            if existing_order.user_id != user_id:
                raise ConflictError(detail="Idempotency key already in use by another order")
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
        raise ConflictError(detail="Order with this idempotency key is currently being processed")

    existing_order_stmt = select(Order).where(Order.idempotency_key == data.idempotency_key)
    existing_result = await db.execute(existing_order_stmt)
    existing_order = existing_result.scalar_one_or_none()
    if existing_order is not None:
        # Idempotency keys are scoped per user: a replay by the same user
        # returns their original order; a key already used by a DIFFERENT
        # user is rejected instead of leaking that user's order data.
        if existing_order.user_id != user_id:
            raise ConflictError(detail="Idempotency key already in use by another order")
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

    # Build line items (with live, tier-aware prices)
    segment = await _resolve_buyer_segment(db, user_id)
    line_items = await _build_line_items(db, cart, segment=segment)
    subtotal = sum(item.subtotal for item in line_items)

    # Re-enforce per-product quantity limits at order time (Sprint 1.5)
    await _validate_line_quantities(db, cart)

    # Validate dynamic category-field answers (Sprint 1.7)
    item_custom_fields = await _resolve_item_custom_fields(db, cart, data.item_fields)

    # ── 4. Reserve inventory for each item ─────────────────────────────
    reservation_ids: list[uuid.UUID] = []
    for ci in cart.items:
        # Check availability before reserving
        available = await inventory_service.check_availability(db, ci.variant_id, ci.quantity)
        if not available:
            # Release any reservations we've already made
            for rid in reservation_ids:
                # Best-effort cleanup; the transaction will roll back anyway
                with contextlib.suppress(Exception):
                    await inventory_service.release_reservation(db, rid)
            raise ConflictError(detail=f"Insufficient stock for variant {ci.variant_id}")

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
    coupon_id_for_redemption: uuid.UUID | None = None
    if data.coupon_code:
        coupon_items = await _coupon_scope_items(db, cart, segment=segment)
        discount_amount, _code, coupon_id_for_redemption = await _apply_coupon(
            db, data.coupon_code, subtotal, user_id, items=coupon_items
        )

    # ── 6. Calculate shipping ──────────────────────────────────────────
    shipping_cost = await _calculate_shipping(db, shipping_method, address.province, subtotal)

    # Tax — tax engine v1 (effective-dated rules, per-line breakdown, B2B
    # withholding). New orders route through the v2 engine; the legacy
    # TaxService.calculate_tax stays for calculate_quote and any legacy
    # callers. Falls back to the legacy single-rule path if the v2 path
    # fails so checkout never hard-breaks on tax misconfiguration.
    from app.modules.checkout.application import tax_service_v2
    from app.modules.checkout.application.tax_engine import OrderLineInput

    line_identities = await _resolve_line_tax_identities(db, cart)
    buyer_ctx = await tax_service_v2.resolve_buyer_tax_context(db, user_id)
    tax_engine_result = None
    try:
        tax_inputs: list[OrderLineInput] = []
        for li in line_items:
            identity = line_identities.get(li.cart_item_id, {})
            line_discount = (
                round(discount_amount * li.subtotal / subtotal) if subtotal > 0 else 0
            )
            tax_inputs.append(
                OrderLineInput(
                    variant_id=li.variant_id,
                    product_id=identity.get("product_id"),
                    category_id=identity.get("category_id"),
                    line_total_rial=max(li.subtotal - line_discount, 0),
                )
            )
        tax_engine_result = await tax_service_v2.calculate_order_tax_v2(
            db,
            lines=tax_inputs,
            customer_is_b2b=buyer_ctx["customer_is_b2b"],
            exemption_certificate=buyer_ctx["exemption_certificate"],
            shipping_rial=shipping_cost,
            subtotal_rial=subtotal,
            discount_rial=discount_amount,
        )
        tax = tax_engine_result.tax_total_rial
        tax_info = {
            "tax_amount_rials": tax,
            "rate_basis_points": 0,
            "rule_code": "TAX_ENGINE_V1",
        }
    except Exception:
        await logger.aexception(
            "tax_engine_v1_failed_falling_back_to_legacy",
            user_id=str(user_id),
        )
        tax_info = await TaxService.calculate_tax(
            db, taxable_amount_rials=max(subtotal - discount_amount, 0)
        )
        tax = tax_info["tax_amount_rials"]

    total = subtotal + shipping_cost - discount_amount + tax
    total = max(total, 0)

    # ── 7. Create order ────────────────────────────────────────────────
    # Shared generator with collision retry — a bare timestamp+3-byte
    # number occasionally violates the unique orders.order_number
    # constraint and would surface as a 500 at checkout.
    from app.modules.orders.application.order_service import generate_unique_order_number

    order_number = await generate_unique_order_number(db)

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
            custom_fields=(
                item_custom_fields.get(li.cart_item_id)
                if li.cart_item_id is not None and item_custom_fields
                else None
            ),
        )
        db.add(order_item)

    # ── 8b. Price snapshot (immutable, hash-sealed) ─────────────────────
    from app.modules.checkout.application import snapshot_service

    # When the v1 engine produced per-line tax, use its exact breakdown;
    # otherwise keep the legacy proportional allocation.
    engine_lines_by_variant: dict[str, Any] = {}
    if tax_engine_result is not None:
        engine_lines_by_variant = {
            str(b.variant_id): b for b in tax_engine_result.lines if b.variant_id
        }

    snapshot_lines: list[dict[str, Any]] = []
    tax_rate_bps = tax_info.get("rate_basis_points", 0)
    for li in line_items:
        # Proportional discount: each line's share of total discount
        line_discount = (
            round(discount_amount * li.subtotal / subtotal) if subtotal > 0 else 0
        )
        engine_line = engine_lines_by_variant.get(str(li.variant_id))
        if engine_line is not None:
            line_tax = engine_line.tax_amount_rial
            line_rate_percent = engine_line.rate_basis_points // 100
        else:
            # Legacy proportional tax: each line's share of total tax
            line_tax = round(tax * li.subtotal / subtotal) if subtotal > 0 else 0
            line_rate_percent = tax_rate_bps // 100
        snapshot_lines.append({
            "variant_id": str(li.variant_id),
            "product_name": li.product_name,
            "quantity": li.quantity,
            "unit_price_rial": li.unit_price,
            "line_total_rial": li.subtotal,
            "discount_amount_rial": line_discount,
            "discount_code": data.coupon_code,
            "tax_amount_rial": line_tax,
            "tax_rate_percent": line_rate_percent,
        })

    await snapshot_service.create_snapshot(
        db,
        order_id=order.id,
        line_items=snapshot_lines,
        subtotal_rial=subtotal,
        total_discount_rial=discount_amount,
        total_tax_rial=tax,
        shipping_rial=shipping_cost,
        grand_total_rial=total,
    )

    # ── 8c. Tax observation (immutable per-order fiscal record, v1) ─────
    if tax_engine_result is not None:
        await tax_service_v2.persist_tax_observation(
            db,
            order_id=order.id,
            result=tax_engine_result,
            customer_is_b2b=buyer_ctx["customer_is_b2b"],
            exemption_certificate_ref=buyer_ctx["exemption_certificate"],
        )

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
        await inventory_service.confirm_reservation(db, rid, order_id=order.id)

    # ── 11. Record coupon redemption (canonical discounts service) ─────
    # apply_discount re-locks the coupon row, re-checks the usage ceiling,
    # writes the per-user redemption ledger row (unique per coupon+order),
    # increments counters, and deactivates the coupon at its limit. A
    # concurrent checkout that raced past the earlier eligibility check
    # fails here and rolls the whole order back instead of overshooting.
    if coupon_id_for_redemption is not None:
        from app.modules.discounts.application import discount_service

        await discount_service.apply_discount(
            db,
            coupon_id=coupon_id_for_redemption,
            user_id=user_id,
            order_id=order.id,
            amount=discount_amount,
        )

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

    from app.core.observability.metrics import ORDERS_CREATED
    from app.shared.events.domain_events import (
        CheckoutCompleted,
        OrderCreated,
        record_domain_event,
    )

    ORDERS_CREATED.inc()
    tracer = get_tracer()
    with tracer.start_as_current_span("checkout.create_order") as span:
        span.set_attribute("checkout.total_rials", total)
        span.set_attribute("checkout.order_id", str(order.id))
        span.set_attribute("checkout.user_id", str(user_id))

    await record_domain_event(
        CheckoutCompleted(
            order_id=order.id,
            user_id=user_id,
            total_amount=total,
        ),
        aggregate_type="checkout",
        aggregate_id=order.id,
        db=db,
        publish_outbox=True,
    )
    await record_domain_event(
        OrderCreated(
            order_id=order.id,
            order_number=order.order_number,
            user_id=user_id,
            total=total,
        ),
        aggregate_type="order",
        aggregate_id=order.id,
        db=db,
        publish_outbox=True,
    )

    # ── 12b. Automation trigger ──────────────────────────────────────
    # ``order_created`` is one of the five triggers an AutomationRule can bind
    # to, and it had no call site anywhere: a rule bound to it never ran, with
    # nothing on screen to say so. Fired here rather than at the route because
    # this is where the order actually comes into existence and the domain
    # event above is published, so the two can never disagree about whether
    # the order happened.
    #
    # Fire-and-forget by design — see queue_automation_trigger. Automation is an
    # additive side-effect and a broker outage must not fail a checkout.
    try:
        from app.modules.automation.application.tasks import queue_automation_trigger

        queue_automation_trigger(
            "order_created",
            {
                "order_id": str(order.id),
                "order_number": str(order.order_number),
                "user_id": str(user_id),
                "total": total,
            },
        )
    except Exception as exc:  # noqa: BLE001 - never block commerce on automation
        logger.warning(
            "automation_order_created_enqueue_failed",
            order_id=str(order.id),
            error=str(exc)[:200],
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
