"""Unit tests for discount and coupon calculation rules."""

from datetime import datetime, timezone
from app.modules.discounts.application.discount_service import calculate_discount
from app.modules.discounts.domain.models import Discount, DiscountScope, DiscountType


def test_fixed_discount_calculation():
    """Verify fixed amount discount logic."""
    discount = Discount(
        name="تخفیف ۵۰ هزار تومانی",
        type=DiscountType.FIXED,
        value=500_000,  # 50,000 Toman in Rials
        starts_at=datetime.now(timezone.utc),
        ends_at=datetime.now(timezone.utc),
        scope=DiscountScope.GLOBAL,
    )

    # Regular cart > discount
    amount = calculate_discount(discount, cart_total=2_000_000)
    assert amount == 500_000

    # Cart smaller than discount -> discount capped to cart total
    amount_small_cart = calculate_discount(discount, cart_total=300_000)
    assert amount_small_cart == 300_000


def test_percentage_discount_calculation():
    """Verify percentage discount (basis points, 1000 = 10%)."""
    discount = Discount(
        name="تخفیف ۱۵ درصدی",
        type=DiscountType.PERCENTAGE,
        value=1500,  # 15% (1500 basis points)
        starts_at=datetime.now(timezone.utc),
        ends_at=datetime.now(timezone.utc),
        scope=DiscountScope.GLOBAL,
    )

    # 15% of 10,000,000 Rials = 1,500,000 Rials
    amount = calculate_discount(discount, cart_total=10_000_000)
    assert amount == 1_500_000


def test_percentage_discount_with_max_cap():
    """Verify max_discount caps large percentages."""
    discount = Discount(
        name="تخفیف ۵۰ درصدی تا سقف ۲۰۰ هزار تومان",
        type=DiscountType.PERCENTAGE,
        value=5000,  # 50%
        max_discount=2_000_000,  # Max 200,000 Toman (2,000,000 Rials)
        starts_at=datetime.now(timezone.utc),
        ends_at=datetime.now(timezone.utc),
        scope=DiscountScope.GLOBAL,
    )

    # 50% of 10,000,000 = 5,000,000, but capped at 2,000,000
    amount = calculate_discount(discount, cart_total=10_000_000)
    assert amount == 2_000_000
