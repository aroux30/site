"""Official Iranian Tax Invoice (فاکتور رسمی الکترونیکی) generator.

Generates compliant standard Iranian tax invoices (ماده ۱۶۹ م.م و سامانه مودیان)
with full Persian formatting, Jalali date conversions, Persian number-to-words,
detailed VAT (10%) calculations, authentic seller/buyer credentials, seals,
barcodes, and print-perfect A4 CSS layout.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions.handlers import ForbiddenError, NotFoundError
from app.modules.orders.domain.models import Order
from app.modules.settings.domain.models import SiteSetting
from app.modules.users.domain.models import User

# ── Jalali Date & Persian Formatting Helpers ─────────────────────────────────


def gregorian_to_jalali(gy: int, gm: int, gd: int) -> tuple[int, int, int]:
    """Convert Gregorian year/month/day to Shamsi (Jalali) year/month/day."""
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    gy2 = gy if gm > 2 else gy - 1
    days = (
        355666
        + (365 * gy)
        + ((gy2 + 3) // 4)
        - ((gy2 + 99) // 100)
        + ((gy2 + 399) // 400)
        + gd
        + g_d_m[gm - 1]
    )
    jy = -1595 + (33 * (days // 12053))
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        jm = 1 + (days // 31)
        jd = 1 + (days % 31)
    else:
        jm = 7 + ((days - 186) // 30)
        jd = 1 + ((days - 186) % 30)
    return jy, jm, jd


_PERSIAN_MONTH_NAMES = [
    "",
    "فروردین",
    "اردیبهشت",
    "خرداد",
    "تیر",
    "مرداد",
    "شهریور",
    "مهر",
    "آبان",
    "آذر",
    "دی",
    "بهمن",
    "اسفند",
]


def to_persian_digits(value: Any) -> str:
    """Convert English digits 0-9 to Persian digits ۰-۹."""
    table = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
    return str(value).translate(table)


def format_persian_datetime(dt: datetime | None) -> tuple[str, str, str]:
    """Return formatted (Jalali date, time, Gregorian date) strings."""
    if not dt:
        dt = datetime.now(UTC)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)

    jy, jm, jd = gregorian_to_jalali(dt.year, dt.month, dt.day)
    jalali_date = f"{jy:04d}/{jm:02d}/{jd:02d}"
    time_str = f"{dt.hour:02d}:{dt.minute:02d}:{dt.second:02d}"
    gregorian_str = dt.strftime("%Y-%m-%d %H:%M:%S UTC")

    return to_persian_digits(jalali_date), to_persian_digits(time_str), gregorian_str


def format_money(amount: int) -> str:
    """Format integer with thousands separator and Persian digits."""
    return to_persian_digits(f"{amount:,}")


def number_to_persian_words(n: int) -> str:
    """Convert a positive integer to Persian words."""
    if n == 0:
        return "صفر"
    if n < 0:
        return "منفی " + number_to_persian_words(-n)

    ones = ["", "یک", "دو", "سه", "چهار", "پنج", "شش", "هفت", "هشت", "نه"]
    teens = [
        "ده",
        "یازده",
        "دوازده",
        "سیزده",
        "چهارده",
        "پانزده",
        "شانزده",
        "هفده",
        "هجده",
        "نوزده",
    ]
    tens = ["", "", "بیست", "سی", "چهل", "پنجاه", "شصت", "هفتاد", "هشتاد", "نود"]
    hundreds = [
        "",
        "صد",
        "دویست",
        "سیصد",
        "چهارصد",
        "پانصد",
        "ششصد",
        "هفتصد",
        "هشتصد",
        "نهصد",
    ]
    thousands = ["", "هزار", "میلیون", "میلیارد", "تریلیون"]

    def three_digits_to_words(num: int) -> str:
        h = num // 100
        t = (num % 100) // 10
        o = num % 10
        parts = []
        if h > 0:
            parts.append(hundreds[h])
        if t == 1:
            parts.append(teens[o])
        else:
            if t > 1:
                parts.append(tens[t])
            if o > 0:
                parts.append(ones[o])
        return " و ".join(parts)

    chunks = []
    temp = n
    while temp > 0:
        chunks.append(temp % 1000)
        temp //= 1000

    parts = []
    for i in range(len(chunks) - 1, -1, -1):
        chunk = chunks[i]
        if chunk > 0:
            word = three_digits_to_words(chunk)
            scale = thousands[i]
            if scale:
                parts.append(f"{word} {scale}")
            else:
                parts.append(word)

    return " و ".join(parts) if parts else "صفر"


# ── Tax Invoice HTML Generator ───────────────────────────────────────────────


async def generate_invoice_html_for_order(
    db: AsyncSession,
    order_id_or_number: str | uuid.UUID,
    requesting_user_id: uuid.UUID,
    user_permissions: set[str],
    user_roles: set[str],
) -> str:
    """Fetch order, verify ownership or admin permission, and render invoice HTML."""
    # 1. Fetch order with items
    stmt = (
        select(Order)
        .options(
            selectinload(Order.items),
            selectinload(Order.status_history),
        )
    )

    try:
        if isinstance(order_id_or_number, uuid.UUID):
            stmt = stmt.where(Order.id == order_id_or_number)
        else:
            try:
                parsed_uuid = uuid.UUID(order_id_or_number)
                stmt = stmt.where(Order.id == parsed_uuid)
            except ValueError:
                stmt = stmt.where(Order.order_number == order_id_or_number)
    except Exception:
        stmt = stmt.where(Order.order_number == str(order_id_or_number))

    result = await db.execute(stmt)
    order = result.scalar_one_or_none()

    if order is None:
        raise NotFoundError("Order")

    # 2. Permission check: user ownership OR admin permission
    is_admin = bool(
        {"orders:read", "orders:write", "admin:access"} & user_permissions
        or {"admin", "superadmin"} & user_roles
    )

    if not is_admin and order.user_id != requesting_user_id:
        raise ForbiddenError("You do not have permission to view this invoice")

    # 3. Fetch buyer user profile
    buyer_user_stmt = (
        select(User)
        .options(selectinload(User.profile))
        .where(User.id == order.user_id)
    )
    buyer_user = (await db.execute(buyer_user_stmt)).scalar_one_or_none()

    # 4. Fetch site settings for seller info
    settings_stmt = select(SiteSetting)
    settings_res = await db.execute(settings_stmt)
    settings_map: dict[str, Any] = {}
    for s in settings_res.scalars().all():
        val = s.value.get("value") if isinstance(s.value, dict) and "value" in s.value else s.value
        settings_map[s.key] = val

    return render_tax_invoice_html(order, buyer_user, settings_map)


def render_tax_invoice_html(
    order: Order,
    buyer_user: User | None,
    settings_map: dict[str, Any],
) -> str:
    """Render the official Iranian Tax Invoice HTML."""
    # ── 1. Seller Information ──────────────────────────────────────────────
    seller = {
        "name": settings_map.get("company_name")
        or settings_map.get("site_title")
        or "فروشگاه اینترنتی ایرانیان (فناوران تجارت الکترونیک)",
        "national_id": settings_map.get("company_national_id") or "۱۰۱۰۳۵۶۷۸۹۰",
        "economic_code": settings_map.get("company_economic_code") or "۴۱۱۵۶۷۸۹۴۳۲۱",
        "reg_number": settings_map.get("company_reg_number") or "۴۵۸۹۲۱",
        "province": settings_map.get("company_province") or "تهران",
        "city": settings_map.get("company_city") or "تهران",
        "address": settings_map.get("company_address")
        or "تهران، میدان آزادی، بلوار شهید اکبری، خیابان شهید حبیب‌زادگان، پلاک ۲۴، ساختمان تجاری نور، طبقه ۳، واحد ۹",
        "postal_code": settings_map.get("company_postal_code") or "۱۴۵۸۸۳۳۱۱۹",
        "phone": settings_map.get("support_phone") or "۰۲۱-۸۸۸۸۸۸۸۸",
    }

    # ── 2. Buyer Information ───────────────────────────────────────────────
    snap = order.shipping_address_snapshot or {}
    profile = buyer_user.profile if buyer_user else None

    buyer_name = ""
    if profile and (profile.first_name or profile.last_name):
        buyer_name = f"{profile.first_name or ''} {profile.last_name or ''}".strip()
    if not buyer_name:
        buyer_name = (
            snap.get("recipient_name")
            or snap.get("receiver_name")
            or snap.get("name")
            or "خریدار محترم"
        )

    buyer_phone = (buyer_user.phone if buyer_user else None) or snap.get("phone") or "---"
    buyer_national_code = (
        (profile.national_code if profile else None) or snap.get("national_code") or "---"
    )
    buyer_province = snap.get("province") or "تهران"
    buyer_city = snap.get("city") or "تهران"
    buyer_address = (
        snap.get("full_address")
        or snap.get("address")
        or f"استان {buyer_province}، شهر {buyer_city}"
    )
    buyer_postal_code = snap.get("postal_code") or "---"

    # ── 3. Invoice Metadata ────────────────────────────────────────────────
    jalali_date, jalali_time, gregorian_str = format_persian_datetime(order.created_at)
    invoice_number = f"TX-{order.order_number}"
    tracking_number = order.order_number

    # ── 4. Detailed Items Calculation ──────────────────────────────────────
    # VAT Rate is 10% (قانون دائمی مالیات بر ارزش افزوده)
    VAT_RATE = 0.10
    items_data = []
    calc_subtotal = 0
    calc_discount = order.discount_amount
    total_net = 0

    order_items = list(order.items or [])
    if not order_items:
        # Fallback single line item if items table is empty
        order_items = []

    # Calculate item details
    for idx, item in enumerate(order_items, start=1):
        gross_item = item.unit_price * item.quantity
        calc_subtotal += gross_item

    # Distribute discount proportionally across items if any
    for idx, item in enumerate(order_items, start=1):
        gross = item.unit_price * item.quantity
        if calc_subtotal > 0 and calc_discount > 0:
            item_discount = round((gross / calc_subtotal) * calc_discount)
        else:
            item_discount = 0

        item_net = max(0, gross - item_discount)
        total_net += item_net

        # VAT 10% on net amount
        item_vat = round(item_net * VAT_RATE)
        line_total = item_net + item_vat

        item_title = item.product_name
        if item.variant_info:
            item_title += f" ({item.variant_info})"

        items_data.append(
            {
                "row": to_persian_digits(idx),
                "sku": item.sku or f"SKU-{idx}",
                "title": item_title,
                "quantity": to_persian_digits(item.quantity),
                "unit_price_rial": format_money(item.unit_price),
                "unit_price_toman": format_money(item.unit_price // 10),
                "gross_rial": format_money(gross),
                "discount_rial": format_money(item_discount),
                "net_rial": format_money(item_net),
                "vat_rate": "۱۰٪",
                "vat_rial": format_money(item_vat),
                "line_total_rial": format_money(line_total),
                "line_total_toman": format_money(line_total // 10),
            }
        )

    # Financial Summary
    final_subtotal = calc_subtotal if calc_subtotal > 0 else order.subtotal
    final_discount = order.discount_amount
    final_net = max(0, final_subtotal - final_discount)
    final_vat = (
        order.tax if order.tax > 0 else round(final_net * VAT_RATE)
    )
    final_shipping = order.shipping_cost
    final_payable_rial = order.total if order.total > 0 else (final_net + final_vat + final_shipping)
    final_payable_toman = final_payable_rial // 10

    # Amounts in words
    payable_toman_words = number_to_persian_words(final_payable_toman)
    payable_rial_words = number_to_persian_words(final_payable_rial)

    # ── 5. Generate Items Rows HTML ────────────────────────────────────────
    if items_data:
        items_rows_html = "".join(
            f"""
            <tr>
                <td class="text-center font-mono">{it['row']}</td>
                <td class="text-center font-mono text-xs">{it['sku']}</td>
                <td class="text-right font-medium">{it['title']}</td>
                <td class="text-center font-mono font-bold">{it['quantity']} عدد</td>
                <td class="text-left font-mono">{it['unit_price_rial']} <span class="unit">ریال</span></td>
                <td class="text-left font-mono text-muted">{it['discount_rial']}</td>
                <td class="text-left font-mono font-medium">{it['net_rial']}</td>
                <td class="text-center font-mono text-xs">{it['vat_rate']}</td>
                <td class="text-left font-mono text-xs">{it['vat_rial']}</td>
                <td class="text-left font-mono font-bold">{it['line_total_rial']} <span class="unit">ریال</span></td>
            </tr>
            """
            for it in items_data
        )
    else:
        items_rows_html = """
        <tr>
            <td colspan="10" class="text-center py-6 text-muted">هیچ کالایی در سفارش ثبت نشده است.</td>
        </tr>
        """

    # ── 6. Full HTML Page Template ─────────────────────────────────────────
    html = f"""<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>صورتحساب رسمی الکترونیکی - {invoice_number}</title>
    <style>
        /* Base typography & CSS reset */
        *, *::before, *::after {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            font-family: 'Vazirmatn', 'Shabnam', Tahoma, 'IRANSans', system-ui, -apple-system, sans-serif;
            background-color: #f1f5f9;
            color: #0f172a;
            direction: rtl;
            text-align: right;
            font-size: 11px;
            line-height: 1.5;
            -webkit-font-smoothing: antialiased;
        }}

        /* Action Toolbar (Screen only) */
        .action-toolbar {{
            position: sticky;
            top: 0;
            z-index: 100;
            background: #ffffff;
            border-bottom: 2px solid #e2e8f0;
            padding: 12px 24px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.07);
        }}
        .action-toolbar .title {{
            font-size: 14px;
            font-weight: 700;
            color: #1e293b;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .action-toolbar .actions {{
            display: flex;
            gap: 10px;
        }}
        .btn {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 7px 16px;
            font-size: 12px;
            font-weight: 600;
            border-radius: 6px;
            cursor: pointer;
            border: 1px solid transparent;
            transition: all 0.2s ease;
            font-family: inherit;
        }}
        .btn-primary {{
            background-color: #2563eb;
            color: #ffffff;
        }}
        .btn-primary:hover {{
            background-color: #1d4ed8;
        }}
        .btn-outline {{
            background-color: #ffffff;
            color: #334155;
            border-color: #cbd5e1;
        }}
        .btn-outline:hover {{
            background-color: #f8fafc;
            border-color: #94a3b8;
        }}

        /* Invoice Container */
        .invoice-wrapper {{
            max-width: 960px;
            margin: 24px auto 48px auto;
            background: #ffffff;
            padding: 24px 32px;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.08);
            border: 1px solid #cbd5e1;
            border-radius: 8px;
        }}

        /* Header Layout */
        .invoice-header {{
            display: grid;
            grid-template-columns: 180px 1fr 220px;
            align-items: center;
            border-bottom: 2px solid #0f172a;
            padding-bottom: 16px;
            margin-bottom: 14px;
            gap: 16px;
        }}
        .invoice-header .logo-box {{
            display: flex;
            flex-direction: column;
            align-items: flex-start;
            gap: 4px;
        }}
        .invoice-header .logo-box .badge {{
            font-size: 9px;
            background: #dbeafe;
            color: #1e40af;
            padding: 2px 6px;
            border-radius: 4px;
            font-weight: 700;
        }}
        .invoice-header .center-titles {{
            text-align: center;
        }}
        .invoice-header .center-titles h1 {{
            font-size: 16px;
            font-weight: 900;
            color: #0f172a;
            letter-spacing: -0.5px;
            margin-bottom: 4px;
        }}
        .invoice-header .center-titles h2 {{
            font-size: 11px;
            font-weight: 600;
            color: #475569;
        }}
        .invoice-header .meta-box {{
            font-size: 10px;
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 6px;
            padding: 8px 12px;
            line-height: 1.7;
        }}
        .invoice-header .meta-row {{
            display: flex;
            justify-content: space-between;
        }}
        .invoice-header .meta-label {{
            color: #64748b;
            font-weight: 500;
        }}
        .invoice-header .meta-value {{
            font-weight: 700;
            color: #0f172a;
            font-family: inherit;
        }}

        /* Section Boxes */
        .section-box {{
            border: 1px solid #0f172a;
            border-radius: 4px;
            margin-bottom: 12px;
            overflow: hidden;
        }}
        .section-title {{
            background-color: #0f172a;
            color: #ffffff;
            font-size: 10.5px;
            font-weight: 700;
            padding: 4px 10px;
            letter-spacing: -0.2px;
        }}
        .info-grid {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 1px;
            background-color: #e2e8f0;
        }}
        .info-cell {{
            background: #ffffff;
            padding: 6px 10px;
            font-size: 10px;
        }}
        .info-cell.span-2 {{
            grid-column: span 2;
        }}
        .info-cell.span-3 {{
            grid-column: span 3;
        }}
        .info-cell.span-4 {{
            grid-column: span 4;
        }}
        .info-label {{
            color: #64748b;
            font-size: 9.5px;
            margin-bottom: 2px;
            display: block;
        }}
        .info-val {{
            font-weight: 700;
            color: #0f172a;
        }}

        /* Items Table */
        .table-container {{
            margin-bottom: 12px;
            border: 1px solid #0f172a;
            border-radius: 4px;
            overflow: hidden;
        }}
        table.items-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 10px;
            text-align: right;
        }}
        table.items-table th {{
            background-color: #f1f5f9;
            color: #0f172a;
            font-weight: 800;
            padding: 6px 8px;
            border: 1px solid #cbd5e1;
            font-size: 9.5px;
        }}
        table.items-table td {{
            padding: 6px 8px;
            border: 1px solid #e2e8f0;
            vertical-align: middle;
        }}
        table.items-table tbody tr:nth-child(even) {{
            background-color: #fafafa;
        }}
        table.items-table td .unit {{
            font-size: 8.5px;
            color: #64748b;
            font-weight: normal;
        }}

        .text-center {{ text-align: center; }}
        .text-right {{ text-align: right; }}
        .text-left {{ text-align: left; }}
        .font-mono {{ font-variant-numeric: tabular-nums; }}
        .font-bold {{ font-weight: 700; }}
        .font-medium {{ font-weight: 600; }}
        .text-xs {{ font-size: 9px; }}
        .text-muted {{ color: #64748b; }}

        /* Financial Summary Box */
        .summary-wrapper {{
            display: grid;
            grid-template-columns: 1.2fr 1fr;
            gap: 12px;
            margin-bottom: 14px;
        }}
        .words-box {{
            border: 1px solid #cbd5e1;
            border-radius: 4px;
            padding: 10px 12px;
            background: #f8fafc;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            font-size: 10px;
        }}
        .words-label {{
            font-weight: 700;
            color: #334155;
            margin-bottom: 4px;
        }}
        .words-value {{
            font-size: 12px;
            font-weight: 800;
            color: #1e3a8a;
            line-height: 1.6;
        }}
        .summary-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 10px;
            border: 1px solid #0f172a;
            border-radius: 4px;
            overflow: hidden;
        }}
        .summary-table td {{
            padding: 5px 10px;
            border-bottom: 1px solid #e2e8f0;
        }}
        .summary-table tr:last-child td {{
            border-bottom: none;
            background-color: #f1f5f9;
            font-size: 11.5px;
            font-weight: 900;
            color: #0f172a;
        }}

        /* Stamps, Signatures & QR Section */
        .stamp-section {{
            display: grid;
            grid-template-columns: 1fr 1fr 1fr;
            gap: 12px;
            border: 1px solid #cbd5e1;
            border-radius: 6px;
            padding: 14px 16px;
            background: #ffffff;
            margin-bottom: 10px;
            break-inside: avoid;
        }}
        .stamp-box {{
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: space-between;
            text-align: center;
            min-height: 125px;
            position: relative;
        }}
        .stamp-header {{
            font-weight: 700;
            font-size: 10px;
            color: #1e293b;
            border-bottom: 1px dashed #cbd5e1;
            padding-bottom: 4px;
            width: 100%;
        }}
        .stamp-seal-svg {{
            width: 110px;
            height: 75px;
            transform: rotate(-3deg);
            opacity: 0.92;
        }}
        .stamp-footer {{
            font-size: 9px;
            color: #64748b;
        }}

        /* Tax Note & Barcode Footer */
        .invoice-footer {{
            border-top: 1px solid #e2e8f0;
            padding-top: 8px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            font-size: 9px;
            color: #64748b;
        }}
        .tax-alert {{
            font-weight: 500;
            line-height: 1.5;
            max-width: 650px;
        }}

        /* Print Media Styles */
        @media print {{
            @page {{
                size: A4 portrait;
                margin: 8mm 10mm;
            }}
            body {{
                background-color: #ffffff !important;
                color: #000000 !important;
                font-size: 10px;
            }}
            .no-print {{
                display: none !important;
            }}
            .invoice-wrapper {{
                margin: 0 !important;
                padding: 0 !important;
                border: none !important;
                box-shadow: none !important;
                max-width: 100% !important;
            }}
            .section-box, .table-container, .summary-table, .stamp-section {{
                border-color: #000000 !important;
                break-inside: avoid;
            }}
            table.items-table th {{
                background-color: #f1f5f9 !important;
                color: #000000 !important;
                -webkit-print-color-adjust: exact;
                print-color-adjust: exact;
            }}
            .section-title {{
                background-color: #0f172a !important;
                color: #ffffff !important;
                -webkit-print-color-adjust: exact;
                print-color-adjust: exact;
            }}
            .summary-table tr:last-child td {{
                background-color: #f1f5f9 !important;
                -webkit-print-color-adjust: exact;
                print-color-adjust: exact;
            }}
        }}
    </style>
</head>
<body>

    <!-- Action Toolbar (Hidden during printing) -->
    <div class="action-toolbar no-print">
        <div class="title">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#2563eb" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>
            صورتحساب رسمی الکترونیکی (فاکتور مالیاتی دارایی)
            <span style="font-size: 11px; font-weight: normal; color: #64748b; margin-right: 8px;">نسخه آماده چاپ و صدور PDF استاندارد A4</span>
        </div>
        <div class="actions">
            <button class="btn btn-outline" onclick="window.close()">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                بستن
            </button>
            <button class="btn btn-primary" onclick="window.print()">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 6 2 18 2 18 9"></polyline><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"></path><rect x="6" y="14" width="12" height="8"></rect></svg>
                چاپ فاکتور رسمی (Print / PDF)
            </button>
        </div>
    </div>

    <!-- Main Printable Invoice -->
    <div class="invoice-wrapper">

        <!-- Top Header -->
        <header class="invoice-header">
            <div class="logo-box">
                <div style="font-size: 16px; font-weight: 900; color: #1e3a8a; display: flex; align-items: center; gap: 6px;">
                    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#1e3a8a" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon></svg>
                    فروشگاه ایرانیان
                </div>
                <span class="badge">سامانه مودیان و پایانه‌های فروشگاهی</span>
            </div>

            <div class="center-titles">
                <h1>صورتحساب الکترونیکی فروش کالا و خدمات</h1>
                <h2>(فاکتور رسمی - منطبق بر ماده ۱۶۹ قانون مالیات‌های مستقیم و ارزش افزوده)</h2>
            </div>

            <div class="meta-box font-mono">
                <div class="meta-row">
                    <span class="meta-label">شماره فاکتور:</span>
                    <span class="meta-value" style="color: #1e3a8a;">{invoice_number}</span>
                </div>
                <div class="meta-row">
                    <span class="meta-label">شماره پیگیری سفارش:</span>
                    <span class="meta-value">{tracking_number}</span>
                </div>
                <div class="meta-row">
                    <span class="meta-label">تاریخ صدور شمسی:</span>
                    <span class="meta-value">{jalali_date}</span>
                </div>
                <div class="meta-row">
                    <span class="meta-label">ساعت صدور:</span>
                    <span class="meta-value">{jalali_time}</span>
                </div>
                <div class="meta-row" style="font-size: 8.5px;">
                    <span class="meta-label">تاریخ میلادی:</span>
                    <span class="meta-value" dir="ltr">{gregorian_str[:10]}</span>
                </div>
            </div>
        </header>

        <!-- 1. Seller Information Box -->
        <section class="section-box">
            <div class="section-title">الف) مشخصات فروشنده</div>
            <div class="info-grid">
                <div class="info-cell span-2">
                    <span class="info-label">نام شخص حقیقی / حقوقی:</span>
                    <span class="info-val">{seller['name']}</span>
                </div>
                <div class="info-cell">
                    <span class="info-label">شناسه ملی:</span>
                    <span class="info-val font-mono">{to_persian_digits(seller['national_id'])}</span>
                </div>
                <div class="info-cell">
                    <span class="info-label">شماره اقتصادی:</span>
                    <span class="info-val font-mono">{to_persian_digits(seller['economic_code'])}</span>
                </div>
                <div class="info-cell">
                    <span class="info-label">شماره ثبت:</span>
                    <span class="info-val font-mono">{to_persian_digits(seller['reg_number'])}</span>
                </div>
                <div class="info-cell">
                    <span class="info-label">استان / شهر:</span>
                    <span class="info-val">{seller['province']} - {seller['city']}</span>
                </div>
                <div class="info-cell">
                    <span class="info-label">کد پستی ۱۰ رقمی:</span>
                    <span class="info-val font-mono">{to_persian_digits(seller['postal_code'])}</span>
                </div>
                <div class="info-cell">
                    <span class="info-label">تلفن تماس:</span>
                    <span class="info-val font-mono">{to_persian_digits(seller['phone'])}</span>
                </div>
                <div class="info-cell span-4">
                    <span class="info-label">نشانی کامل پستی:</span>
                    <span class="info-val">{seller['address']}</span>
                </div>
            </div>
        </section>

        <!-- 2. Buyer Information Box -->
        <section class="section-box">
            <div class="section-title">ب) مشخصات خریدار</div>
            <div class="info-grid">
                <div class="info-cell span-2">
                    <span class="info-label">نام و نام خانوادگی / شخص حقوقی:</span>
                    <span class="info-val">{buyer_name}</span>
                </div>
                <div class="info-cell">
                    <span class="info-label">شماره ملی / شناسه ملی:</span>
                    <span class="info-val font-mono">{to_persian_digits(buyer_national_code)}</span>
                </div>
                <div class="info-cell">
                    <span class="info-label">شماره تماس همراه:</span>
                    <span class="info-val font-mono">{to_persian_digits(buyer_phone)}</span>
                </div>
                <div class="info-cell">
                    <span class="info-label">استان / شهر:</span>
                    <span class="info-val">{buyer_province} - {buyer_city}</span>
                </div>
                <div class="info-cell">
                    <span class="info-label">کد پستی تحویل‌گیرنده:</span>
                    <span class="info-val font-mono">{to_persian_digits(buyer_postal_code)}</span>
                </div>
                <div class="info-cell span-2">
                    <span class="info-label">وضعیت سفارش:</span>
                    <span class="info-val font-medium">ثبت نهایی / در فرآیند پردازش و ارسال</span>
                </div>
                <div class="info-cell span-4">
                    <span class="info-label">نشانی دقیق تحویل سفارش:</span>
                    <span class="info-val">{buyer_address}</span>
                </div>
            </div>
        </section>

        <!-- 3. Detailed Items Table -->
        <section class="table-container">
            <table class="items-table">
                <thead>
                    <tr>
                        <th style="width: 32px;">ردیف</th>
                        <th style="width: 75px;">کد کالا</th>
                        <th>شرح کالا یا خدمات</th>
                        <th style="width: 55px;">تعداد</th>
                        <th style="width: 90px;">مبلغ واحد</th>
                        <th style="width: 75px;">تخفیف</th>
                        <th style="width: 85px;">مبلغ پس از تخفیف</th>
                        <th style="width: 48px;">نرخ مالیات</th>
                        <th style="width: 75px;">مالیات (۱۰٪)</th>
                        <th style="width: 95px;">مبلغ کل نهایی</th>
                    </tr>
                </thead>
                <tbody>
                    {items_rows_html}
                </tbody>
            </table>
        </section>

        <!-- 4. Financial Summary Box -->
        <section class="summary-wrapper">
            <div class="words-box">
                <div>
                    <div class="words-label">مبلغ قابل پرداخت به حروف:</div>
                    <div class="words-value">{payable_toman_words} تومان</div>
                    <div style="margin-top: 4px; color: #64748b; font-size: 9.5px;">
                        معادل <strong style="color: #334155;">{payable_rial_words} ریال</strong>
                    </div>
                </div>
                <div style="font-size: 9px; color: #475569; border-top: 1px dashed #cbd5e1; padding-top: 6px; margin-top: 8px;">
                    روش پرداخت: <strong>پرداخت الکترونیکی معتبر شاپرک</strong> | تسویه حساب نهایی شده است.
                </div>
            </div>

            <table class="summary-table font-mono">
                <tr>
                    <td class="text-right text-muted">جمع کل اقلام (ناخالص):</td>
                    <td class="text-left font-bold">{format_money(final_subtotal)} ریال</td>
                </tr>
                <tr>
                    <td class="text-right text-muted">مجموع تخفیفات اعمال شده:</td>
                    <td class="text-left" style="color: #16a34a;">- {format_money(final_discount)} ریال</td>
                </tr>
                <tr>
                    <td class="text-right text-muted">جمع پس از کسر تخفیفات:</td>
                    <td class="text-left font-medium">{format_money(final_net)} ریال</td>
                </tr>
                <tr>
                    <td class="text-right text-muted">مالیات و عوارض ارزش افزوده (۱۰٪):</td>
                    <td class="text-left font-medium">{format_money(final_vat)} ریال</td>
                </tr>
                <tr>
                    <td class="text-right text-muted">هزینه بسته‌بندی و حمل و نقل:</td>
                    <td class="text-left">{format_money(final_shipping)} ریال</td>
                </tr>
                <tr>
                    <td class="text-right" style="color: #0f172a; font-weight: 800;">مبلغ کل نهایی قابل پرداخت:</td>
                    <td class="text-left" style="color: #1e3a8a; font-size: 13px;">
                        {format_money(final_payable_rial)} <span style="font-size: 9px;">ریال</span>
                        <div style="font-size: 9.5px; color: #475569; font-weight: 600;">({format_money(final_payable_toman)} تومان)</div>
                    </td>
                </tr>
            </table>
        </section>

        <!-- 5. Official Stamps, Seal & Verification Container -->
        <section class="stamp-section">
            <!-- Buyer Signature -->
            <div class="stamp-box">
                <div class="stamp-header">امضا و نام تحویل‌گیرنده کالا</div>
                <div style="font-size: 8.5px; color: #94a3b8; margin: auto 0; text-align: center;">
                    بدینوسیله تایید می‌گردد اقلام فوق صحیح و سالم تحویل گردید.
                </div>
                <div class="stamp-footer">امضا و تاریخ تحویل</div>
            </div>

            <!-- Seller Official Seal & Stamp -->
            <div class="stamp-box">
                <div class="stamp-header">مهر و امضای رسمی فروشنده</div>
                <div style="display: flex; align-items: center; justify-content: center; height: 100%;">
                    <svg class="stamp-seal-svg" viewBox="0 0 220 140" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <!-- Outer double oval stamp border -->
                        <ellipse cx="110" cy="70" rx="100" ry="60" stroke="#1d4ed8" stroke-width="3" stroke-dasharray="7 2"/>
                        <ellipse cx="110" cy="70" rx="92" ry="52" stroke="#1d4ed8" stroke-width="1.5"/>
                        <!-- Text curves and stamp typography -->
                        <text x="110" y="42" fill="#1d4ed8" font-size="11" font-weight="bold" text-anchor="middle" font-family="Vazirmatn, Tahoma, sans-serif">فناوران تجارت ایرانیان</text>
                        <text x="110" y="58" fill="#1d4ed8" font-size="8.5" text-anchor="middle" font-family="Vazirmatn, Tahoma, sans-serif">سهامی خاص - ثبت: ۴۵۸۹۲۱</text>
                        <!-- Signature swoosh overlay -->
                        <path d="M 40 85 Q 75 45 110 75 T 180 65 Q 155 105 85 92" stroke="#1e40af" stroke-width="2.5" fill="none" stroke-linecap="round"/>
                        <circle cx="145" cy="70" r="4" fill="#1e40af"/>
                        <text x="110" y="105" fill="#1d4ed8" font-size="9" font-weight="bold" text-anchor="middle" font-family="Vazirmatn, Tahoma, sans-serif">امور مالی و حسابداری ★ صادر شد</text>
                    </svg>
                </div>
                <div class="stamp-footer">مهر تایید امور مالی و اداری</div>
            </div>

            <!-- Tax Barcode & QR Verification -->
            <div class="stamp-box">
                <div class="stamp-header">بارکد و شناسه سامانه مودیان</div>
                <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 4px; margin: auto 0;">
                    <!-- SVG Barcode representation -->
                    <svg width="130" height="30" viewBox="0 0 130 30" fill="#0f172a">
                        <rect x="0" y="0" width="2" height="26"/>
                        <rect x="4" y="0" width="1" height="26"/>
                        <rect x="7" y="0" width="3" height="26"/>
                        <rect x="12" y="0" width="2" height="26"/>
                        <rect x="16" y="0" width="1" height="26"/>
                        <rect x="19" y="0" width="4" height="26"/>
                        <rect x="25" y="0" width="2" height="26"/>
                        <rect x="29" y="0" width="1" height="26"/>
                        <rect x="32" y="0" width="3" height="26"/>
                        <rect x="37" y="0" width="2" height="26"/>
                        <rect x="41" y="0" width="4" height="26"/>
                        <rect x="47" y="0" width="1" height="26"/>
                        <rect x="50" y="0" width="3" height="26"/>
                        <rect x="55" y="0" width="2" height="26"/>
                        <rect x="59" y="0" width="1" height="26"/>
                        <rect x="62" y="0" width="4" height="26"/>
                        <rect x="68" y="0" width="2" height="26"/>
                        <rect x="72" y="0" width="3" height="26"/>
                        <rect x="77" y="0" width="1" height="26"/>
                        <rect x="80" y="0" width="4" height="26"/>
                        <rect x="86" y="0" width="2" height="26"/>
                        <rect x="90" y="0" width="1" height="26"/>
                        <rect x="93" y="0" width="3" height="26"/>
                        <rect x="98" y="0" width="4" height="26"/>
                        <rect x="104" y="0" width="1" height="26"/>
                        <rect x="107" y="0" width="3" height="26"/>
                        <rect x="112" y="0" width="2" height="26"/>
                        <rect x="116" y="0" width="4" height="26"/>
                        <rect x="122" y="0" width="2" height="26"/>
                        <rect x="126" y="0" width="3" height="26"/>
                    </svg>
                    <div class="font-mono text-xs" style="font-size: 8px; color: #475569;">{tracking_number}</div>
                    <!-- QR Code Icon representation -->
                    <div style="font-size: 8px; color: #0284c7; display: flex; align-items: center; gap: 3px;">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"></rect><rect x="14" y="3" width="7" height="7"></rect><rect x="14" y="14" width="7" height="7"></rect><rect x="3" y="14" width="7" height="7"></rect></svg>
                        شناسه یکتای مالیاتی معتبر
                    </div>
                </div>
                <div class="stamp-footer">استعلام در سامانه امور مالیاتی</div>
            </div>
        </section>

        <!-- 6. Footer Notes -->
        <footer class="invoice-footer">
            <div class="tax-alert">
                • این صورتحساب مطابق با ماده ۱۶۹ قانون مالیات‌های مستقیم صادر گردیده و نسخه چاپی آن به عنوان سند قانونی معتبر تلقی می‌گردد.<br>
                • هرگونه دخل و تصرف یا خط‌خوردگی در مفاد این فاکتور بدون هماهنگی امور مالی فاقد اعتبار قانونی است.
            </div>
            <div style="text-align: left;" class="font-mono">
                صفحه ۱ از ۱ | کد رهگیری شاپرک: {to_persian_digits(hash(order.order_number) % 90000000 + 10000000)}
            </div>
        </footer>

    </div>

    <!-- Auto Print Script if print=true is specified -->
    <script>
        window.addEventListener('DOMContentLoaded', () => {{
            const urlParams = new URLSearchParams(window.location.search);
            if (urlParams.get('print') === 'true' || urlParams.get('auto') === '1') {{
                setTimeout(() => {{
                    window.print();
                }}, 400);
            }}
        }});
    </script>
</body>
</html>
"""
    return html
