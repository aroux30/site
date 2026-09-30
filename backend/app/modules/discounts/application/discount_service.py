"""Discount / Coupon application service — validation, calculation, and redemption.

All monetary values are ``BigInteger`` (Rials).
"""

from __future__ import annotations

import math
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.core.exceptions.handlers import (
    ConflictError,
    NotFoundError,
    ValidationError,
)
from app.modules.discounts.domain.models import (
    Coupon,
    CouponRedemption,
    Discount,
    DiscountScope,
    DiscountType,
)
from app.modules.discounts.schemas.discount import (
    CouponApplyResponse,
    DiscountCreateRequest,
    DiscountListResponse,
    DiscountResponse,
    DiscountUpdateRequest,
    PaginationMeta,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


# ══════════════════════════════════════════════════════════════════════════
# Coupon validation & application (customer-facing)
# ══════════════════════════════════════════════════════════════════════════


async def validate_coupon(
    db: AsyncSession,
    code: str,
    user_id: uuid.UUID,
    cart_total: int,
    items: list[dict[str, Any]] | None = None,
) -> CouponApplyResponse:
    """Validate a coupon code against all business rules and return the
    computed discount amount without recording a redemption.

    Checks performed:
    * Coupon exists and is active
    * Coupon date range is current
    * Coupon usage limit not exceeded
    * Underlying discount is active and within date range
    * Discount usage limit not exceeded
    * Minimum cart amount met
    * Per-user usage limit (one redemption per coupon per user by default)
    """
    now = datetime.now(UTC)

    # 1. Fetch coupon with its discount
    stmt = (
        select(Coupon)
        .options(selectinload(Coupon.discount))
        .where(Coupon.code == code.upper().strip())
    )
    result = await db.execute(stmt)
    coupon = result.scalar_one_or_none()

    if coupon is None:
        raise NotFoundError("Coupon", detail="کد تخفیف یافت نشد")

    # 2. Active checks
    if not coupon.is_active:
        raise ValidationError("این کد تخفیف غیرفعال شده است", error_code="COUPON_INACTIVE")

    if now < coupon.starts_at or now > coupon.ends_at:
        raise ValidationError(
            "کد تخفیف منقضی شده یا هنوز فعال نشده است", error_code="COUPON_EXPIRED"
        )

    if coupon.usage_limit is not None and coupon.usage_count >= coupon.usage_limit:
        raise ValidationError(
            "ظرفیت استفاده از این کد تخفیف تکمیل شده است", error_code="COUPON_LIMIT_REACHED"
        )

    # 3. Discount validation
    discount = coupon.discount
    if discount is None:
        raise ValidationError("تخفیف مرتبط با این کد یافت نشد", error_code="DISCOUNT_MISSING")

    if not discount.is_active:
        raise ValidationError("تخفیف مرتبط غیرفعال شده است", error_code="DISCOUNT_INACTIVE")

    if now < discount.starts_at or now > discount.ends_at:
        raise ValidationError("تخفیف مرتبط منقضی شده است", error_code="DISCOUNT_EXPIRED")

    if discount.usage_limit is not None and discount.usage_count >= discount.usage_limit:
        raise ValidationError(
            "ظرفیت استفاده از این تخفیف تکمیل شده است", error_code="DISCOUNT_LIMIT_REACHED"
        )

    # 4. Minimum cart amount
    if discount.min_cart_amount is not None and cart_total < discount.min_cart_amount:
        raise ValidationError(
            f"حداقل مبلغ سبد خرید برای استفاده از این تخفیف {discount.min_cart_amount:,} ریال است",
            error_code="MIN_CART_NOT_MET",
        )

    # 5. Per-user check (one redemption per coupon per user)
    user_usage_stmt = select(func.count()).where(
        CouponRedemption.coupon_id == coupon.id,
        CouponRedemption.user_id == user_id,
    )
    user_usage_count: int = (await db.execute(user_usage_stmt)).scalar_one()
    if user_usage_count > 0:
        raise ValidationError(
            "شما قبلاً از این کد تخفیف استفاده کرده‌اید", error_code="COUPON_ALREADY_USED"
        )

    # 6. Scope eligibility — a scoped discount must actually cover the cart.
    # USER scope: the customer must be listed in scope_ids. PRODUCT /
    # CATEGORY / BRAND scope: at least one cart item must match; without an
    # item list we cannot verify coverage, so the coupon is rejected rather
    # than silently applied cart-wide.
    if discount.scope == DiscountScope.USER:
        allowed_users = {str(s) for s in (discount.scope_ids or [])}
        if user_id and str(user_id) not in allowed_users:
            raise ValidationError(
                "این کد تخفیف برای حساب شما فعال نیست",
                error_code="COUPON_NOT_APPLICABLE",
            )
    elif discount.scope in (DiscountScope.PRODUCT, DiscountScope.CATEGORY, DiscountScope.BRAND):
        if _scoped_subtotal(discount, cart_total, items) <= 0:
            raise ValidationError(
                "این کد تخفیف شامل کالاهای سبد خرید شما نمی‌شود",
                error_code="COUPON_SCOPE_MISMATCH",
            )

    # 6b. FIRST_ORDER eligibility: the customer must have no prior order.
    # Without this the type behaved identically to PERCENTAGE and a repeat
    # buyer could claim the "first order" coupon on any later order.
    if discount.type == DiscountType.FIRST_ORDER:
        from app.modules.orders.domain.models import Order

        prior_orders = await db.scalar(
            select(func.count()).select_from(Order).where(Order.user_id == user_id)
        )
        if int(prior_orders or 0) > 0:
            raise ValidationError(
                "کد تخفیف سفارش اول فقط برای اولین خرید شما قابل استفاده است",
                error_code="NOT_FIRST_ORDER",
            )

    # 7. Calculate discount (scope-aware basis)
    discount_amount = calculate_discount(discount, cart_total, items)

    description = _build_description(discount, discount_amount)

    await logger.ainfo(
        "coupon_validated",
        code=code,
        user_id=str(user_id),
        discount_amount=discount_amount,
    )

    return CouponApplyResponse(
        coupon_id=coupon.id,
        code=coupon.code,
        discount_amount=discount_amount,
        discount_type=discount.type.value,
        description=description,
    )


_SCOPE_ITEM_FIELDS: dict[DiscountScope, tuple[str, ...]] = {
    DiscountScope.PRODUCT: ("product_id", "variant_id"),
    DiscountScope.CATEGORY: ("category_id",),
    DiscountScope.BRAND: ("brand_id",),
}


def _scoped_subtotal(
    discount: Discount,
    cart_total: int,
    items: list[dict[str, Any]] | None,
) -> int:
    """Subtotal of the cart items covered by the discount's scope.

    ``items`` entries carry identity fields (``product_id`` / ``variant_id`` /
    ``category_id`` / ``brand_id``) and a ``subtotal`` in Rials. GLOBAL and
    USER scope apply to the whole cart. Scoped discounts with no eligible
    items return 0 — the caller must reject the coupon in that case, never
    fall back to the full cart total.
    """
    if discount.scope in (DiscountScope.GLOBAL, DiscountScope.USER) or not discount.scope_ids:
        return cart_total

    if not items:
        return 0

    allowed = {str(s) for s in discount.scope_ids}
    fields = _SCOPE_ITEM_FIELDS.get(discount.scope, ())
    if not fields:
        return cart_total

    total = 0
    for item in items:
        subtotal = int(item.get("subtotal") or 0)
        if subtotal <= 0:
            continue
        if any(item.get(field) is not None and str(item[field]) in allowed for field in fields):
            total += subtotal
    return total


def calculate_discount(
    discount: Discount,
    cart_total: int,
    items: list[dict[str, Any]] | None = None,
) -> int:
    """Compute the discount amount in Rials.

    * ``fixed`` — the discount value is the amount directly.
    * ``percentage`` — ``value`` is in basis-points (e.g. 1000 = 10%).
    * ``first_order`` — same as percentage but flagged for first-order logic.

    The basis is the scoped subtotal (see ``_scoped_subtotal``): a
    PRODUCT/CATEGORY/BRAND-scoped discount only applies to the matching
    items, never to the whole cart. The result is clamped to
    ``max_discount`` if set, and never exceeds the scoped basis.
    """
    base = _scoped_subtotal(discount, cart_total, items)
    if base <= 0:
        return 0

    if discount.type == DiscountType.FIXED:
        amount = discount.value
    elif discount.type in (DiscountType.PERCENTAGE, DiscountType.FIRST_ORDER):
        # value stored as basis points: 1000 = 10%
        amount = (base * discount.value) // 10000
    else:
        amount = 0

    # Cap at max_discount
    if discount.max_discount is not None and amount > discount.max_discount:
        amount = discount.max_discount

    # Never exceed the covered subtotal
    if amount > base:
        amount = base

    return amount


def _build_description(discount: Discount, amount: int) -> str:
    """Build a human-readable Farsi description of the applied discount."""
    if discount.type == DiscountType.FIXED:
        return f"تخفیف ثابت {amount:,} ریال"
    elif discount.type == DiscountType.PERCENTAGE:
        pct = discount.value / 100  # basis points → percentage
        return f"تخفیف {pct:.0f}% (معادل {amount:,} ریال)"
    elif discount.type == DiscountType.FIRST_ORDER:
        pct = discount.value / 100
        return f"تخفیف سفارش اول {pct:.0f}% (معادل {amount:,} ریال)"
    return f"تخفیف {amount:,} ریال"


# ══════════════════════════════════════════════════════════════════════════
# Redemption recording
# ══════════════════════════════════════════════════════════════════════════


async def apply_discount(
    db: AsyncSession,
    coupon_id: uuid.UUID,
    user_id: uuid.UUID,
    order_id: uuid.UUID,
    amount: int,
) -> CouponRedemption:
    """Record a coupon redemption and increment usage counters.

    Call this *after* order creation has been committed to ensure we have a
    valid ``order_id``.
    """
    # 1. Fetch coupon with row-level lock (FOR UPDATE) to prevent concurrency race
    stmt = select(Coupon).where(Coupon.id == coupon_id).with_for_update()
    coupon = (await db.execute(stmt)).scalar_one_or_none()
    if coupon is None:
        raise NotFoundError("Coupon", detail="کد تخفیف یافت نشد")
    if not coupon.is_active:
        raise ValidationError("کد تخفیف غیرفعال است", error_code="COUPON_INACTIVE")

    # Re-validate expiration under row-level lock
    now = datetime.now(UTC)
    if now < coupon.starts_at:
        raise ValidationError(
            "زمان استفاده از این کد تخفیف هنوز فرا نرسیده است", error_code="COUPON_NOT_STARTED"
        )
    if now > coupon.ends_at:
        raise ValidationError(
            "مهلت استفاده از این کد تخفیف به پایان رسیده است", error_code="COUPON_EXPIRED"
        )

    if coupon.usage_limit is not None and coupon.usage_count >= coupon.usage_limit:
        raise ValidationError(
            "ظرفیت استفاده از این کد تخفیف تکمیل شده است", error_code="COUPON_LIMIT_REACHED"
        )

    # Double-check that no duplicate redemption exists
    dup_stmt = select(CouponRedemption).where(
        CouponRedemption.coupon_id == coupon_id,
        CouponRedemption.user_id == user_id,
        CouponRedemption.order_id == order_id,
    )
    dup = (await db.execute(dup_stmt)).scalar_one_or_none()
    if dup is not None:
        raise ConflictError("Coupon already redeemed for this order")

    # Re-check the per-user redemption limit while holding the coupon row
    # lock. validate_coupon's unlocked COUNT races with concurrent
    # checkouts by the same user; here the coupon lock serializes all
    # redemptions for this coupon, so this count sees prior committed
    # redemptions and the per-user rule cannot be exceeded.
    user_usage_stmt = (
        select(func.count())
        .select_from(CouponRedemption)
        .filter_by(coupon_id=coupon_id, user_id=user_id)
    )
    user_usage_count: int = (await db.execute(user_usage_stmt)).scalar_one()
    if user_usage_count > 0:
        raise ValidationError(
            "شما قبلاً از این کد تخفیف استفاده کرده‌اید",
            error_code="COUPON_ALREADY_USED",
        )

    redemption = CouponRedemption(
        coupon_id=coupon_id,
        user_id=user_id,
        order_id=order_id,
        amount=amount,
    )
    db.add(redemption)

    # Increment coupon usage count
    coupon.usage_count += 1
    if coupon.usage_limit is not None and coupon.usage_count >= coupon.usage_limit:
        coupon.is_active = False

    # Increment parent discount usage count
    if coupon.discount_id:
        disc_stmt = select(Discount).where(Discount.id == coupon.discount_id).with_for_update()
        disc = (await db.execute(disc_stmt)).scalar_one_or_none()
        if disc is not None:
            disc.usage_count += 1

    await db.flush()

    await logger.ainfo(
        "coupon_redeemed",
        coupon_id=str(coupon_id),
        user_id=str(user_id),
        order_id=str(order_id),
        amount=amount,
    )

    return redemption


# ══════════════════════════════════════════════════════════════════════════
# Admin operations
# ══════════════════════════════════════════════════════════════════════════


async def get_active_discounts(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    include_inactive: bool = False,
) -> DiscountListResponse:
    """Return a paginated list of discounts (admin)."""
    base = select(Discount)
    if not include_inactive:
        base = base.where(Discount.is_active.is_(True))

    count_stmt = select(func.count()).select_from(base.subquery())
    total_items: int = (await db.execute(count_stmt)).scalar_one()
    total_pages = max(1, math.ceil(total_items / page_size))

    stmt = (
        base.order_by(Discount.priority.desc(), Discount.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    discounts = result.scalars().all()

    await logger.ainfo("discounts_listed", total_items=total_items, page=page)

    return DiscountListResponse(
        items=[DiscountResponse.model_validate(d) for d in discounts],
        meta=PaginationMeta(
            page=page,
            page_size=page_size,
            total_items=total_items,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_prev=page > 1,
        ),
    )


async def create_discount(
    db: AsyncSession,
    data: DiscountCreateRequest,
) -> DiscountResponse:
    """Admin: create a new discount rule."""
    # Validate enum values
    try:
        discount_type = DiscountType(data.type)
    except ValueError:
        valid = ", ".join(t.value for t in DiscountType)
        raise ValidationError(
            f"Invalid discount type '{data.type}'. Valid: {valid}",
            error_code="INVALID_DISCOUNT_TYPE",
        ) from None

    try:
        scope = DiscountScope(data.scope)
    except ValueError:
        valid = ", ".join(s.value for s in DiscountScope)
        raise ValidationError(
            f"Invalid scope '{data.scope}'. Valid: {valid}",
            error_code="INVALID_DISCOUNT_SCOPE",
        ) from None

    if data.ends_at <= data.starts_at:
        raise ValidationError(
            "ends_at must be after starts_at",
            error_code="INVALID_DATE_RANGE",
        )

    discount = Discount(
        name=data.name,
        type=discount_type,
        value=data.value,
        min_cart_amount=data.min_cart_amount,
        max_discount=data.max_discount,
        scope=scope,
        scope_ids=data.scope_ids,
        starts_at=data.starts_at,
        ends_at=data.ends_at,
        is_active=data.is_active,
        is_stackable=data.is_stackable,
        usage_limit=data.usage_limit,
        priority=data.priority,
    )
    db.add(discount)
    await db.flush()
    await db.refresh(discount)

    await logger.ainfo(
        "discount_created",
        discount_id=str(discount.id),
        name=discount.name,
        type=discount.type.value,
    )

    return DiscountResponse.model_validate(discount)


async def update_discount(
    db: AsyncSession,
    discount_id: uuid.UUID,
    data: DiscountUpdateRequest,
) -> DiscountResponse:
    """Admin: partially update a discount rule."""
    discount = await db.get(Discount, discount_id)
    if discount is None:
        raise NotFoundError("Discount")

    update_data = data.model_dump(exclude_unset=True)

    # Validate enum fields if provided
    if "scope" in update_data and update_data["scope"] is not None:
        try:
            update_data["scope"] = DiscountScope(update_data["scope"])
        except ValueError:
            valid = ", ".join(s.value for s in DiscountScope)
            raise ValidationError(
                f"Invalid scope. Valid: {valid}",
                error_code="INVALID_DISCOUNT_SCOPE",
            ) from None

    for field, value in update_data.items():
        setattr(discount, field, value)

    db.add(discount)
    await db.flush()
    await db.refresh(discount)

    await logger.ainfo(
        "discount_updated",
        discount_id=str(discount_id),
        fields=list(update_data.keys()),
    )

    return DiscountResponse.model_validate(discount)
