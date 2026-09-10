"""Discount / Coupon application service — validation, calculation, and redemption.

All monetary values are ``BigInteger`` (Rials).
"""

from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import structlog
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
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

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


# ══════════════════════════════════════════════════════════════════════════
# Coupon validation & application (customer-facing)
# ══════════════════════════════════════════════════════════════════════════


async def validate_coupon(
    db: AsyncSession,
    code: str,
    user_id: uuid.UUID,
    cart_total: int,
    items: Optional[list[dict[str, Any]]] = None,
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
    now = datetime.now(timezone.utc)

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
        raise ValidationError("کد تخفیف منقضی شده یا هنوز فعال نشده است", error_code="COUPON_EXPIRED")

    if coupon.usage_limit is not None and coupon.usage_count >= coupon.usage_limit:
        raise ValidationError("ظرفیت استفاده از این کد تخفیف تکمیل شده است", error_code="COUPON_LIMIT_REACHED")

    # 3. Discount validation
    discount = coupon.discount
    if discount is None:
        raise ValidationError("تخفیف مرتبط با این کد یافت نشد", error_code="DISCOUNT_MISSING")

    if not discount.is_active:
        raise ValidationError("تخفیف مرتبط غیرفعال شده است", error_code="DISCOUNT_INACTIVE")

    if now < discount.starts_at or now > discount.ends_at:
        raise ValidationError("تخفیف مرتبط منقضی شده است", error_code="DISCOUNT_EXPIRED")

    if discount.usage_limit is not None and discount.usage_count >= discount.usage_limit:
        raise ValidationError("ظرفیت استفاده از این تخفیف تکمیل شده است", error_code="DISCOUNT_LIMIT_REACHED")

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
        raise ValidationError("شما قبلاً از این کد تخفیف استفاده کرده‌اید", error_code="COUPON_ALREADY_USED")

    # 6. Calculate discount
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


def calculate_discount(
    discount: Discount,
    cart_total: int,
    items: Optional[list[dict[str, Any]]] = None,
) -> int:
    """Compute the discount amount in Rials.

    * ``fixed`` — the discount value is the amount directly.
    * ``percentage`` — ``value`` is in basis-points (e.g. 1000 = 10%).
    * ``first_order`` — same as percentage but flagged for first-order logic.

    The result is clamped to ``max_discount`` if set, and never exceeds
    ``cart_total``.
    """
    if discount.type == DiscountType.FIXED:
        amount = discount.value
    elif discount.type in (DiscountType.PERCENTAGE, DiscountType.FIRST_ORDER):
        # value stored as basis points: 1000 = 10%
        amount = (cart_total * discount.value) // 10000
    else:
        amount = 0

    # Cap at max_discount
    if discount.max_discount is not None and amount > discount.max_discount:
        amount = discount.max_discount

    # Never exceed cart total
    if amount > cart_total:
        amount = cart_total

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
    if coupon.usage_limit is not None and coupon.usage_count >= coupon.usage_limit:
        raise ValidationError("ظرفیت استفاده از این کد تخفیف تکمیل شده است", error_code="COUPON_LIMIT_REACHED")

    # Double-check that no duplicate redemption exists
    dup_stmt = select(CouponRedemption).where(
        CouponRedemption.coupon_id == coupon_id,
        CouponRedemption.user_id == user_id,
        CouponRedemption.order_id == order_id,
    )
    dup = (await db.execute(dup_stmt)).scalar_one_or_none()
    if dup is not None:
        raise ConflictError("Coupon already redeemed for this order")

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
        )

    try:
        scope = DiscountScope(data.scope)
    except ValueError:
        valid = ", ".join(s.value for s in DiscountScope)
        raise ValidationError(
            f"Invalid scope '{data.scope}'. Valid: {valid}",
            error_code="INVALID_DISCOUNT_SCOPE",
        )

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
            )

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
