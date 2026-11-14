"""Build and send Telegram order-notification messages.

Reuses the existing TelegramClient from the chat module — no duplicate HTTP
logic. Each order-status change produces an HTML message with inline action
buttons, routed to the chat/topic configured for that status.

Delivery is best-effort: a Telegram outage never rolls back the order
transaction.
"""

from __future__ import annotations

import uuid as uuid_mod
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.chat.application.telegram_client import TelegramClient, TelegramConfig
from app.modules.orders.domain.models import Order, OrderStatus
from app.modules.tgnotif.application.tgnotif_config import get_config, is_ready

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


# ── Status display mapping ────────────────────────────────────────────────

_STATUS_LABELS: dict[str, tuple[str, str]] = {
    # status_value: (persian_label, emoji)
    # Synced with frontend/lib/admin/order-domain.ts STATUS_VISUALS
    "waiting_payment_gateway": ("در انتظار تایید پرداخت", "⏳"),
    "waiting_payment_card": ("در انتظار تایید کارت به کارت", "💳"),
    "pending": ("در حال انجام", "🔵"),
    "processing": ("در حال پردازش", "🟣"),
    "doing_verified": ("در حال انجام (احراز شده)", "🟢"),
    "completed": ("تکمیل شده", "✅"),
    "canceled": ("لغو شده", "🔴"),
    "refunded": ("بازگشت وجه", "⬜"),
}


def _format_rial(amount: int | None) -> str:
    """Format a Rial amount with thousand separators."""
    if amount is None:
        return "0"
    return f"{amount:,}"


def _status_label(status: str) -> tuple[str, str]:
    return _STATUS_LABELS.get(status, (status, "📋"))


# ── Message builder ───────────────────────────────────────────────────────


def build_order_message(
    order: Order,
    config: dict[str, Any],
    *,
    site_url: str = "",
) -> str:
    """Build an HTML Telegram message for an order status change.

    Fields are conditionally included based on config toggles. Every field
    maps to a real column/relationship on the Order/OrderItem/User models.
    """
    status_val = order.status.value if isinstance(order.status, OrderStatus) else str(order.status)
    label, emoji = _status_label(status_val)

    lines: list[str] = []

    if config.get("show_order_id", True):
        lines.append(f"<b>🛒 شماره سفارش:</b> <code>{order.order_number}</code>")

    if config.get("show_status", True):
        lines.append(f"<b>⌛️ وضعیت سفارش:</b> {label} {emoji}")

    # ── Items ──────────────────────────────────────────────────────────
    if config.get("show_items", True) and order.items:
        lines.append("<b>🛍 محصولات:</b>")
        for item in order.items:
            name = getattr(item, "product_name", None) or "—"
            qty = getattr(item, "quantity", 1)
            price = _format_rial(getattr(item, "total_price", None))
            lines.append(f"  • {name} × {qty} — {price} ریال")

            # Variant info (color/size) — stored as snapshot on OrderItem
            if config.get("show_variant_info", True):
                variant_info = getattr(item, "variant_info", None)
                if variant_info:
                    lines.append(f"    📋 تنوع: {variant_info}")

            # SKU
            if config.get("show_sku", False):
                sku = getattr(item, "sku", None)
                if sku:
                    lines.append(f"    🏷 SKU: <code>{sku}</code>")

            # Custom fields (digital products: account name / numeric ID + all others)
            custom = getattr(item, "custom_fields", None) or {}
            if isinstance(custom, dict) and custom:
                if config.get("show_custom_fields", True):
                    # Known keys first
                    acct = custom.get("اسم اکانت") or custom.get("account_name")
                    num_id = custom.get("آیدی عددی") or custom.get("numeric_id")
                    if acct:
                        lines.append(f"    🆎 اسم اکانت: <code>{acct}</code>")
                    if num_id:
                        lines.append(f"    🆔 آیدی عددی: <code>{num_id}</code>")
                    # All other custom fields
                    _known = {"اسم اکانت", "account_name", "آیدی عددی", "numeric_id"}
                    for ck, cv in custom.items():
                        if ck not in _known and cv:
                            lines.append(f"    📎 {ck}: <code>{cv}</code>")

    # ── Money ──────────────────────────────────────────────────────────
    if config.get("show_subtotal", False):
        subtotal = getattr(order, "subtotal", None)
        if subtotal:
            lines.append(f"<b>💰 مبلغ قبل از تخفیف:</b> {_format_rial(subtotal)} ریال")

    if config.get("show_total", True):
        lines.append(f"<b>💵 مبلغ کل:</b> {_format_rial(order.total)} ریال")

    if config.get("show_shipping", False):
        shipping = getattr(order, "shipping_cost", None)
        if shipping and shipping > 0:
            lines.append(f"<b>🚚 هزینه ارسال:</b> {_format_rial(shipping)} ریال")

    if config.get("show_tax", False):
        tax = getattr(order, "tax", None)
        if tax and tax > 0:
            lines.append(f"<b>🧾 مالیات:</b> {_format_rial(tax)} ریال")

    if config.get("show_coupon", True):
        discount = order.discount_amount
        if discount and discount > 0:
            coupon_info = ""
            snapshot = getattr(order, "shipping_address_snapshot", None) or {}
            if isinstance(snapshot, dict):
                coupon_info = snapshot.get("coupon_codes", "") or snapshot.get("coupon_code", "")
            if coupon_info:
                lines.append(f"<b>🎟 کد تخفیف:</b> {coupon_info} ({_format_rial(discount)} ریال)")
            else:
                lines.append(f"<b>🎟 تخفیف:</b> {_format_rial(discount)} ریال")

    # ── Payment ────────────────────────────────────────────────────────
    if config.get("show_payment_method", True):
        if hasattr(order, "payments") and order.payments:
            first_payment = order.payments[0]
            # Payment model has `provider` enum (zarinpal/nextpay/wallet/card_transfer)
            provider = getattr(first_payment, "provider", None)
            if provider:
                provider_label = str(provider.value) if hasattr(provider, "value") else str(provider)
                _PROVIDER_LABELS = {
                    "zarinpal": "زرین‌پال",
                    "nextpay": "نکست‌پی",
                    "wallet": "کیف پول",
                    "card_transfer": "کارت‌به‌کارت",
                }
                lines.append(f"<b>💳 روش پرداخت:</b> {_PROVIDER_LABELS.get(provider_label, provider_label)}")

    if config.get("show_payment_status", False):
        if hasattr(order, "payments") and order.payments:
            first_payment = order.payments[0]
            pay_status = getattr(first_payment, "status", None)
            if pay_status:
                pay_status_val = pay_status.value if hasattr(pay_status, "value") else str(pay_status)
                _PAY_STATUS_LABELS = {
                    "pending": "در انتظار ⏳",
                    "processing": "در حال پردازش 🔄",
                    "completed": "موفق ✅",
                    "failed": "ناموفق ❌",
                    "refunded": "بازگشت داده شده 🔄",
                }
                lines.append(f"<b>🏦 وضعیت پرداخت:</b> {_PAY_STATUS_LABELS.get(pay_status_val, pay_status_val)}")

    if config.get("show_payment_ref", False):
        if hasattr(order, "payments") and order.payments:
            first_payment = order.payments[0]
            ref = getattr(first_payment, "provider_transaction_id", None)
            if ref:
                lines.append(f"<b>🔢 شناسه تراکنش:</b> <code>{ref}</code>")

    # ── Link & Date ────────────────────────────────────────────────────
    if config.get("show_order_link", True) and site_url:
        admin_link = f"{site_url.rstrip('/')}/admin/orders/{order.id}"
        lines.append(f'<b>🔗 لینک سفارش:</b> <a href="{admin_link}">مشاهده در پنل</a>')

    if config.get("show_date", True):
        created = getattr(order, "created_at", None)
        if created and isinstance(created, datetime):
            lines.append(f"<b>⏱️ تاریخ ثبت:</b> {created.strftime('%Y/%m/%d %H:%M:%S')}")

    # ── Customer info ──────────────────────────────────────────────────
    user = getattr(order, "user", None)
    if user:
        if config.get("show_customer_name", True):
            profile = getattr(user, "profile", None)
            full_name = ""
            if profile:
                first = getattr(profile, "first_name", "") or ""
                last = getattr(profile, "last_name", "") or ""
                full_name = f"{first} {last}".strip()
            if not full_name:
                full_name = getattr(user, "phone", "") or "—"
            lines.append(f"<b>👤 نام مشتری:</b> {full_name}")

        if config.get("show_phone", True):
            phone = getattr(user, "phone", "")
            if phone:
                lines.append(f"<b>📞 تلفن:</b> {phone}")

        if config.get("show_national_code", False):
            profile = getattr(user, "profile", None)
            if profile:
                nc = getattr(profile, "national_code", None)
                if nc:
                    lines.append(f"<b>🪪 کد ملی:</b> <code>{nc}</code>")

        if config.get("show_verified", True):
            is_verified = getattr(user, "is_verified", False)
            badge = "✅ احراز شده" if is_verified else "⚠️ احراز نشده"
            lines.append(f"<b>🛡 وضعیت احراز:</b> {badge}")

    # ── Address ────────────────────────────────────────────────────────
    if config.get("show_address", False):
        snapshot = getattr(order, "shipping_address_snapshot", None) or {}
        if isinstance(snapshot, dict) and snapshot:
            parts = []
            province = snapshot.get("province") or snapshot.get("state")
            city = snapshot.get("city")
            address = snapshot.get("address") or snapshot.get("full_address")
            postal = snapshot.get("postal_code") or snapshot.get("postcode")
            if province:
                parts.append(str(province))
            if city:
                parts.append(str(city))
            if address:
                parts.append(str(address))
            if postal:
                parts.append(f"کد پستی: {postal}")
            if parts:
                lines.append(f"<b>📍 آدرس:</b> {' — '.join(parts)}")

    if config.get("show_ip", False):
        ip = getattr(order, "ip_address", "")
        if ip:
            lines.append(f"<b>🌐 آیپی:</b> {ip}")

    if config.get("show_notes", False):
        notes = getattr(order, "notes", "")
        if notes:
            lines.append(f"<b>📝 یادداشت:</b> {notes}")

    return "\n".join(lines)


def build_inline_keyboard(order_id: str | uuid_mod.UUID, current_status: str) -> dict[str, Any]:
    """Build Telegram inline keyboard with only valid transition buttons.

    callback_data format: ``tgn_{status}_{order_id}``

    Buttons are filtered by the current order status so only valid state-machine
    transitions are shown. This prevents confusing "این تغییر وضعیت مجاز نیست!"
    errors when an admin presses an unavailable action.

    Allowed transitions (from order_service._VALID_TRANSITIONS):
      pending         → processing, doing_verified
      processing      → completed
      doing_verified  → processing, completed
      completed       → (terminal — no buttons)
      canceled        → (terminal — no buttons)
      others          → show all non-terminal actions
    """
    oid = str(order_id)

    # Map target status → button label
    # Synced with frontend/lib/admin/order-domain.ts STATUS_VISUALS
    _ALL_BUTTONS = [
        ("pending",        "در حال انجام 🔵"),
        ("doing_verified", "احراز شده 🟢"),
        ("processing",     "در حال پردازش 🟣"),
        ("completed",      "تکمیل سفارش ✅"),
    ]

    # Which transitions are valid per current status
    _VALID: dict[str, frozenset[str]] = {
        "waiting_payment_gateway": frozenset({"pending"}),
        "waiting_payment_card":    frozenset({"pending"}),
        "pending":                 frozenset({"processing", "doing_verified"}),
        "doing_verified":          frozenset({"processing", "completed"}),
        "processing":              frozenset({"completed"}),
        "completed":               frozenset(),
        "canceled":                frozenset(),
        "refunded":                frozenset(),
    }

    allowed = _VALID.get(current_status, frozenset({"pending", "processing", "doing_verified", "completed"}))
    if not allowed:
        return {}  # Terminal state — no buttons

    row1 = []
    row2 = []
    for status_slug, label in _ALL_BUTTONS:
        if status_slug in allowed:
            btn = {"text": label, "callback_data": f"tgn_{status_slug}_{oid}"}
            if len(row1) < 2:
                row1.append(btn)
            else:
                row2.append(btn)

    rows = [r for r in [row1, row2] if r]
    if not rows:
        return {}

    return {"inline_keyboard": rows}


# ── Chat/topic routing ────────────────────────────────────────────────────


def _resolve_target(
    config: dict[str, Any], status: str
) -> tuple[str, int | None]:
    """Return (chat_id, topic_id) for the given order status.

    Falls back to the processing chat/topic if the status-specific one is
    empty (WP plugin falls back to chat_id_new_order).
    """
    chat_id = str(config.get(f"chat_id_{status}", "") or "").strip()
    topic_raw = str(config.get(f"topic_id_{status}", "") or "").strip()

    # Fallback chain: status-specific → processing → first non-empty
    if not chat_id:
        chat_id = str(config.get("chat_id_processing", "") or "").strip()
    if not chat_id:
        for key in ("chat_id_pending", "chat_id_doing_verified", "chat_id_completed", "chat_id_canceled"):
            chat_id = str(config.get(key, "") or "").strip()
            if chat_id:
                break

    topic_id: int | None = None
    if topic_raw:
        try:
            topic_id = int(topic_raw)
        except (ValueError, TypeError):
            pass

    return chat_id, topic_id


# ── Main send function ────────────────────────────────────────────────────


async def send_order_notification(
    db: AsyncSession,
    order_id: str | uuid_mod.UUID,
    *,
    site_url: str = "",
) -> bool:
    """Send the Telegram notification for an order.

    Returns True if the message was sent successfully, False otherwise.
    Never raises — delivery failures are logged only.
    """
    try:
        config = await get_config(db)
        if not is_ready(config):
            await logger.adebug("tgnotif_not_ready")
            return False

        # Load order with items, user, payments
        oid = uuid_mod.UUID(str(order_id))
        order = await db.get(
            Order,
            oid,
            options=(
                selectinload(Order.items),
                selectinload(Order.user),
                selectinload(Order.payments),
            ),
        )
        if order is None:
            await logger.awarning("tgnotif_order_not_found", order_id=str(order_id))
            return False

        status_val = order.status.value if isinstance(order.status, OrderStatus) else str(order.status)

        # Resolve target chat/topic
        chat_id, topic_id = _resolve_target(config, status_val)
        if not chat_id:
            await logger.awarning(
                "tgnotif_no_chat_id", status=status_val, order_id=str(order_id)
            )
            return False

        # Build message
        message = build_order_message(order, config, site_url=site_url)
        if not message.strip():
            await logger.awarning("tgnotif_empty_message", order_id=str(order_id))
            return False

        # Build inline keyboard (only valid transitions for this status)
        keyboard = build_inline_keyboard(order.id, status_val)

        # Create client for the resolved chat_id
        tg_config = TelegramConfig(
            bot_token=str(config.get("bot_token", "")),
            chat_id=chat_id,
        )
        client = TelegramClient(tg_config)

        # Send
        result = await client.send_message(
            message,
            thread_id=topic_id,
            reply_markup=keyboard,
        )

        if result.ok:
            await logger.ainfo(
                "tgnotif_sent",
                order_id=str(order.id),
                order_number=order.order_number,
                status=status_val,
                chat_id=chat_id,
            )
        else:
            await logger.awarning(
                "tgnotif_send_failed",
                order_id=str(order.id),
                status=status_val,
                error=result.error,
            )

        return result.ok

    except Exception as exc:
        await logger.aerror(
            "tgnotif_send_error",
            order_id=str(order_id),
            error=str(exc),
            exc_info=True,
        )
        return False
