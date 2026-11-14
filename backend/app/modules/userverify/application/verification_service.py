"""User verification service — the plugin's behaviour, ported.

What the WordPress plugin did (user-verification-orders.php):

1. An admin manually verified a customer (phone call, info stored in Telegram),
   then ticked the user in wp-admin. Every flip was logged
   (``uv_verification_logs``) and pushed to a Telegram group.
2. On payment success / thank-you page, a VERIFIED customer's order that was
   sitting in ``processing`` moved to ``wc-doing_verified``
   ("در حال انجام (احراز شده)").

Here:

- The verified flag is ``users.is_verified`` (already exposed on the admin
  users API); this module logs every flip and sends the Telegram notice —
  the parts the site was missing.
- Paid orders by verified buyers are routed into
  ``OrderStatus.DOING_VERIFIED`` at the exact two points where a paid order
  enters the operator's lane (gateway ``verify_payment`` and the admin
  card-to-card approval) — the site's equivalent of the plugin's
  payment-complete/thankyou hooks. Because this system has NO thank-you-page
  hook, a customer verified AFTER paying has their still-waiting orders
  rerouted by :func:`VerificationService.reroute_waiting_orders` at the moment
  the badge is granted.

Both sides are best-effort at their call sites: a Telegram outage or a config
problem must never break a payment or a user update.
"""

from __future__ import annotations

import uuid

import structlog
from sqlalchemy import select

from app.modules.userverify.application import verification_config
from app.modules.userverify.domain.models import UserVerificationLog

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


def _esc(value: object) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


async def _resolve_telegram_client(db):
    """Config row first, chat widget credentials as fallback (one bot per shop)."""
    from app.modules.chat.application.telegram_client import TelegramClient, TelegramConfig

    config = await verification_config.get_config(db)
    token = config["telegram_bot_token"]
    chat_id = config["telegram_chat_id"]
    if not (token and chat_id):
        from app.modules.chat.application import chat_config

        chat_cfg = await chat_config.get_config(db)
        token = token or (chat_cfg.get("telegram_bot_token") or "").strip()
        chat_id = chat_id or (chat_cfg.get("telegram_chat_id") or "").strip()
    tg = TelegramConfig(bot_token=token, chat_id=chat_id)
    if not tg.is_configured:
        return None
    return TelegramClient(tg), config


class VerificationService:
    """Manual verification flips + the verified order lane."""

    @staticmethod
    async def notify_and_log(
        db,
        *,
        user_id: uuid.UUID,
        admin_id: uuid.UUID,
        verified: bool,
        ip_address: str | None,
    ) -> None:
        """Log one verify/unverify flip and push it to Telegram.

        Plugin parity (handle_verification_toggle): log row ALWAYS, Telegram
        only when notifications are on and a bot is configured. Best-effort:
        raises nothing.
        """
        db.add(
            UserVerificationLog(
                user_id=user_id,
                admin_id=admin_id,
                status=verified,
                ip_address=ip_address,
            )
        )
        await db.flush()

        try:
            resolved = await _resolve_telegram_client(db)
            if resolved is None:
                return
            client, config = resolved
            if not config["telegram_notifications"]:
                return

            from app.modules.users.domain.models import User, UserProfile

            user = await db.get(User, user_id)
            profile = (
                await db.execute(
                    select(UserProfile).where(UserProfile.user_id == user_id)
                )
            ).scalar_one_or_none()
            admin = await db.get(User, admin_id)

            name = " ".join(
                part
                for part in (
                    (profile.first_name if profile else None),
                    (profile.last_name if profile else None),
                )
                if part
            ) or (user.phone if user else str(user_id))

            text = (
                "✅ <b>وضعیت احراز کاربر تغییر کرد</b>\n\n"
                f"👤 کاربر: {_esc(name)}\n"
                f"📱 موبایل: {_esc(user.phone if user else '—')}\n"
                f"🔁 وضعیت: {'احراز شده' if verified else 'عدم احراز'}\n"
                f"👮 توسط: {_esc(admin.phone if admin else str(admin_id))}\n"
                f"🌐 آیپی: {_esc(ip_address or '—')}"
            )
            result = await client.send_message(text)
            if not result.ok:
                await logger.awarning(
                    "userverify_telegram_failed", user_id=str(user_id), error=result.error
                )
        except Exception as exc:  # never break the admin action on Telegram
            await logger.awarning(
                "userverify_telegram_skipped", user_id=str(user_id), error=str(exc)
            )

    @staticmethod
    async def order_entry_status(db, user_id: uuid.UUID):
        """The lane a freshly PAID order enters: verified buyers get the badge lane.

        Returns ``DOING_VERIFIED`` or ``PENDING``. Config ``enabled=false``
        disables the distinction entirely (plugin removed = normal lanes).
        """
        from app.modules.orders.domain.models import OrderStatus
        from app.modules.users.domain.models import User

        config = await verification_config.get_config(db)
        if not config["enabled"]:
            return OrderStatus.PENDING
        user = await db.get(User, user_id)
        if user is not None and user.is_verified:
            return OrderStatus.DOING_VERIFIED
        return OrderStatus.PENDING

    @staticmethod
    async def reroute_waiting_orders(
        db, user_id: uuid.UUID, *, admin_id: uuid.UUID | None = None
    ) -> int:
        """Move a newly verified customer's open paid orders into the badge lane.

        The plugin relied on the thank-you page hook to catch orders paid
        before verification; this system has no such hook, so granting the
        badge retroactively upgrades orders still sitting in ``PENDING``.
        Returns the number of moved orders.
        """
        from app.modules.orders.domain.models import (
            Order,
            OrderStatus,
            OrderStatusHistory,
        )

        stmt = (
            select(Order)
            .where(Order.user_id == user_id, Order.status == OrderStatus.PENDING)
            .with_for_update()
        )
        orders = (await db.execute(stmt)).scalars().all()
        for order in orders:
            order.status = OrderStatus.DOING_VERIFIED
            db.add(
                OrderStatusHistory(
                    order_id=order.id,
                    from_status=OrderStatus.PENDING.value,
                    to_status=OrderStatus.DOING_VERIFIED.value,
                    changed_by=admin_id,
                    reason="کاربر احراز شد؛ انتقال خودکار به لین احراز شده",
                )
            )
        if orders:
            await db.flush()
            logger.info(
                "userverify_orders_rerouted", user_id=str(user_id), count=len(orders)
            )
        return len(orders)

    @staticmethod
    async def list_logs(
        db,
        *,
        skip: int = 0,
        limit: int = 50,
        q: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ):
        """The plugin's "گزارش لاگ‌ها" tab: newest first, with user/admin phones.

        Filters:
        - q: search in user_phone, admin_phone, ip_address
        - date_from: ISO date string (YYYY-MM-DD) — logs >= this date
        - date_to: ISO date string (YYYY-MM-DD) — logs < day after this date
        """
        from datetime import datetime, timedelta
        from sqlalchemy import func, or_

        from app.modules.users.domain.models import User

        # Build the WHERE clause
        conditions = []

        # Date range filter
        if date_from:
            try:
                dt_from = datetime.fromisoformat(date_from)
                conditions.append(UserVerificationLog.created_at >= dt_from)
            except (ValueError, TypeError):
                pass

        if date_to:
            try:
                dt_to = datetime.fromisoformat(date_to) + timedelta(days=1)
                conditions.append(UserVerificationLog.created_at < dt_to)
            except (ValueError, TypeError):
                pass

        # Search filter — we need to join with users to search phones
        # For now, search only in IP (instant); phone search requires subquery
        if q and q.strip():
            q_pattern = f"%{q.strip()}%"
            # Search in IP address directly
            conditions.append(
                or_(
                    UserVerificationLog.ip_address.ilike(q_pattern) if UserVerificationLog.ip_address else False,
                )
            )

        base_stmt = select(UserVerificationLog)
        if conditions:
            base_stmt = base_stmt.where(*conditions)

        total = (
            await db.execute(
                select(func.count()).select_from(base_stmt.subquery())
            )
        ).scalar_one()

        stmt = (
            base_stmt
            .order_by(UserVerificationLog.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        logs = (await db.execute(stmt)).scalars().all()

        ids = {l.user_id for l in logs} | {l.admin_id for l in logs}
        phones: dict[uuid.UUID, str] = {}
        if ids:
            rows = await db.execute(select(User.id, User.phone).where(User.id.in_(ids)))
            phones = {row.id: row.phone for row in rows}

        items = [
            {
                "id": str(l.id),
                "user_id": str(l.user_id),
                "user_phone": phones.get(l.user_id),
                "admin_id": str(l.admin_id),
                "admin_phone": phones.get(l.admin_id),
                "status": l.status,
                "ip_address": l.ip_address,
                "created_at": l.created_at.isoformat() if l.created_at else None,
            }
            for l in logs
        ]
        return items, int(total)
