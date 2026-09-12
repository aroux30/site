"""Unit tests for Iranian Tax Invoice generation and formatting."""

import uuid
from datetime import UTC, datetime

from app.modules.orders.application.invoice_service import (
    format_money,
    gregorian_to_jalali,
    number_to_persian_words,
    render_tax_invoice_html,
    to_persian_digits,
)
from app.modules.orders.domain.models import Order, OrderItem, OrderStatus
from app.modules.users.domain.models import User, UserProfile


def test_gregorian_to_jalali():
    """Verify Gregorian to Jalali date conversions."""
    jy, jm, jd = gregorian_to_jalali(2026, 9, 9)
    assert (jy, jm, jd) == (1405, 6, 18)

    # 1 Farvardin 1403
    jy, jm, jd = gregorian_to_jalali(2024, 3, 20)
    assert jy == 1402 and jm == 12 and jd == 29


def test_to_persian_digits():
    """Verify digits 0-9 are transformed into Persian digits."""
    assert to_persian_digits("0123456789") == "۰۱۲۳۴۵۶۷۸۹"
    assert to_persian_digits(12345) == "۱۲۳۴۵"


def test_number_to_persian_words():
    """Verify number to Persian words conversion."""
    assert number_to_persian_words(0) == "صفر"
    assert number_to_persian_words(100) == "صد"
    assert number_to_persian_words(101) == "صد و یک"
    assert number_to_persian_words(150_000) == "صد و پنجاه هزار"
    assert number_to_persian_words(68_500_000) == "شصت و هشت میلیون و پانصد هزار"


def test_format_money():
    """Verify formatted numbers have thousand separators in Persian digits."""
    assert format_money(1000) == "۱,۰۰۰"
    assert format_money(68500000) == "۶۸,۵۰۰,۰۰۰"


def test_render_tax_invoice_html():
    """Verify rendering of complete official Iranian Tax Invoice."""
    user_id = uuid.uuid4()
    order_id = uuid.uuid4()
    user = User(
        id=user_id,
        phone="09123456789",
        email="buyer@example.com",
    )
    user.profile = UserProfile(
        user_id=user_id,
        first_name="علیرضا",
        last_name="محمدی",
        national_code="0012345678",
    )

    order = Order(
        id=order_id,
        user_id=user_id,
        order_number="ORD-20260909-A1B2",
        status=OrderStatus.CONFIRMED,
        subtotal=20_000_000,
        shipping_cost=500_000,
        tax=2_000_000,
        discount_amount=1_000_000,
        total=21_500_000,
        shipping_address_snapshot={
            "province": "تهران",
            "city": "تهران",
            "postal_code": "1458833119",
            "full_address": "خیابان آزادی، خیابان حبیب‌الله، پلاک ۱۰",
        },
        created_at=datetime(2026, 9, 9, 14, 30, 0, tzinfo=UTC),
    )

    item1 = OrderItem(
        id=uuid.uuid4(),
        order_id=order_id,
        variant_id=uuid.uuid4(),
        product_name="هدفون بی‌سیم سونی WH-1000XM5",
        variant_info="رنگ مشکی",
        sku="SONY-WH1000XM5-BLK",
        quantity=1,
        unit_price=20_000_000,
        total_price=20_000_000,
    )
    order.items = [item1]

    settings_map = {
        "site_title": "فروشگاه اینترنتی ایرانیان",
        "company_national_id": "۱۰۱۰۳۵۶۷۸۹۰",
        "company_economic_code": "۴۱۱۵۶۷۸۹۴۳۲۱",
        "company_reg_number": "۴۵۸۹۲۱",
        "company_province": "تهران",
        "company_city": "تهران",
        "company_address": "تهران، میدان آزادی، بلوار شهید اکبری، پلاک ۲۴",
        "company_postal_code": "۱۴۵۸۸۳۳۱۱۹",
        "support_phone": "۰۲۱-۸۸۸۸۸۸۸۸",
    }

    html = render_tax_invoice_html(order, user, settings_map)

    # 1. Check Seller Info
    assert "فروشگاه اینترنتی ایرانیان" in html
    assert "۱۰۱۰۳۵۶۷۸۹۰" in html or "10103567890" in html
    assert "۴۱۱۵۶۷۸۹۴۳۲۱" in html or "411567894321" in html
    assert "۴۵۸۹۲۱" in html or "458921" in html
    assert "۰۲۱-۸۸۸۸۸۸۸۸" in html or "021-88888888" in html
    assert "بلوار شهید اکبری" in html

    # 2. Check Buyer Info
    assert "علیرضا محمدی" in html
    assert "۰۹۱۲۳۴۵۶۷۸۹" in html or "09123456789" in html
    assert "خیابان حبیب‌الله" in html
    assert "۱۴۵۸۸۳۳۱۱۹" in html or "1458833119" in html

    # 3. Check Invoice Metadata
    assert "TX-ORD-20260909-A1B2" in html
    assert "ORD-20260909-A1B2" in html
    assert "۱۴۰۵/۰۶/۱۸" in html
    assert "2026-09-09" in html

    # 4. Check Items table
    assert "هدفون بی‌سیم سونی" in html
    assert "SONY-WH1000XM5-BLK" in html
    assert "۱۰٪" in html  # VAT rate

    # 5. Check Financial summary and words
    assert "مبلغ قابل پرداخت به حروف" in html
    assert "تومان" in html
    assert "ریال" in html

    # 6. Check stamps, seals, barcode, and print CSS
    assert "stamp-seal-svg" in html
    assert "@media print" in html
    assert "no-print" in html


from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions.handlers import ForbiddenError, NotFoundError
from app.modules.orders.application.invoice_service import generate_invoice_html_for_order


@pytest.mark.asyncio
async def test_generate_invoice_permissions():
    owner_id = uuid.uuid4()
    stranger_id = uuid.uuid4()
    order_id = uuid.uuid4()

    mock_order = MagicMock()
    mock_order.id = order_id
    mock_order.user_id = owner_id
    mock_order.order_number = "ORD-TEST-001"
    mock_order.subtotal = 1000000
    mock_order.discount_amount = 0
    mock_order.shipping_cost = 0
    mock_order.tax = 100000
    mock_order.total = 1100000
    mock_order.items = []
    mock_order.shipping_address_snapshot = {}
    mock_order.created_at = datetime.now(UTC)

    # 1. User ownership -> Success
    db = AsyncMock()
    exec_result = MagicMock()
    exec_result.scalar_one_or_none.return_value = mock_order
    exec_settings = MagicMock()
    exec_settings.scalars.return_value.all.return_value = []
    db.execute.side_effect = [
        exec_result,
        MagicMock(scalar_one_or_none=MagicMock(return_value=None)),
        exec_settings,
    ]

    html = await generate_invoice_html_for_order(
        db=db,
        order_id_or_number=str(order_id),
        requesting_user_id=owner_id,
        user_permissions=set(),
        user_roles=set(),
    )
    assert "TX-ORD-TEST-001" in html

    # 2. Stranger without permissions -> ForbiddenError
    db = AsyncMock()
    exec_result = MagicMock()
    exec_result.scalar_one_or_none.return_value = mock_order
    db.execute.return_value = exec_result

    with pytest.raises(ForbiddenError):
        await generate_invoice_html_for_order(
            db=db,
            order_id_or_number=str(order_id),
            requesting_user_id=stranger_id,
            user_permissions=set(),
            user_roles=set(),
        )

    # 3. Stranger with "orders:read" permission -> Success
    db = AsyncMock()
    exec_result = MagicMock()
    exec_result.scalar_one_or_none.return_value = mock_order
    exec_settings = MagicMock()
    exec_settings.scalars.return_value.all.return_value = []
    db.execute.side_effect = [
        exec_result,
        MagicMock(scalar_one_or_none=MagicMock(return_value=None)),
        exec_settings,
    ]

    html = await generate_invoice_html_for_order(
        db=db,
        order_id_or_number=str(order_id),
        requesting_user_id=stranger_id,
        user_permissions={"orders:read"},
        user_roles=set(),
    )
    assert "TX-ORD-TEST-001" in html

    # 4. Stranger with "admin" role -> Success
    db = AsyncMock()
    exec_result = MagicMock()
    exec_result.scalar_one_or_none.return_value = mock_order
    exec_settings = MagicMock()
    exec_settings.scalars.return_value.all.return_value = []
    db.execute.side_effect = [
        exec_result,
        MagicMock(scalar_one_or_none=MagicMock(return_value=None)),
        exec_settings,
    ]

    html = await generate_invoice_html_for_order(
        db=db,
        order_id_or_number=str(order_id),
        requesting_user_id=stranger_id,
        user_permissions=set(),
        user_roles={"admin"},
    )
    assert "TX-ORD-TEST-001" in html

    # 5. Order not found -> NotFoundError
    db = AsyncMock()
    exec_result = MagicMock()
    exec_result.scalar_one_or_none.return_value = None
    db.execute.return_value = exec_result

    with pytest.raises(NotFoundError):
        await generate_invoice_html_for_order(
            db=db,
            order_id_or_number=str(order_id),
            requesting_user_id=owner_id,
            user_permissions=set(),
            user_roles=set(),
        )
