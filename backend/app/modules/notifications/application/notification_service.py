"""Notification application service – create, send, and manage notifications."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast

import structlog
from sqlalchemy import CursorResult, func, select, update

from app.modules.notifications.domain.models import (
    Notification,
    NotificationChannel,
    NotificationTemplate,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
logger: structlog.stdlib.BoundLogger = structlog.get_logger()


# ── Provider Abstraction ──────────────────────────────────────────────────


class BaseNotificationProvider:
    """Abstract base for notification channel providers."""

    channel: NotificationChannel

    async def send(
        self, recipient: str, title: str, body: str, data: dict[str, Any] | None = None
    ) -> bool:
        raise NotImplementedError


class MockEmailProvider(BaseNotificationProvider):
    """Mock email provider for development."""

    channel = NotificationChannel.EMAIL

    async def send(
        self, recipient: str, title: str, body: str, data: dict[str, Any] | None = None
    ) -> bool:
        await logger.ainfo("mock_email_sent", recipient=recipient, title=title)
        return True


class SMTPEmailProvider(BaseNotificationProvider):
    """Real SMTP email provider backed by the email delivery service.

    ``recipient`` is the user's email address; when it is blank the send
    is skipped (returns False) so callers can pass ``user.email or ""``
    without branching. When SMTP is unconfigured the service itself falls
    back to mock behavior with a warning, so this provider never raises
    for configuration gaps.
    """

    channel = NotificationChannel.EMAIL

    def __init__(self, db: Any | None = None) -> None:
        self._db = db

    async def send(
        self, recipient: str, title: str, body: str, data: dict[str, Any] | None = None
    ) -> bool:
        from app.modules.notifications.application import email_service

        if "@" not in (recipient or ""):
            await logger.ainfo(
                "email_skipped_no_recipient", title=title, recipient=recipient
            )
            return False

        # The in-app body is plain text; wrap it in the RTL HTML shell so
        # generic notifications still arrive as readable emails. The header
        # carries the operator's store name, resolved the same way every other
        # email resolves it — this used to read SMTP_FROM_NAME, so a store that
        # renamed itself in Settings got the new name on order confirmations
        # and the old one on notifications.
        html = await email_service.wrap_html_for_store(
            self._db,
            f"<p>{body}</p>".replace("\n", "<br>"),
        )
        success, _ = await email_service.send_email(
            self._db,
            recipient=recipient,
            subject=title,
            html_body=html,
            text_body=body,
            notification_id=(data or {}).get("notification_id"),
        )
        return success


class MockSMSProvider(BaseNotificationProvider):
    """Mock SMS provider for development."""

    channel = NotificationChannel.SMS

    async def send(
        self, recipient: str, title: str, body: str, data: dict[str, Any] | None = None
    ) -> bool:
        await logger.ainfo("mock_sms_sent", recipient=recipient, body=body[:100])
        return True


class MockTelegramProvider(BaseNotificationProvider):
    """Mock Telegram provider for development (kept for tests and reference).

    The live channel uses :class:`TelegramBotProvider` below; this mock is
    retained because the telegram service itself falls back to simulated
    sends when unconfigured, and tests target the real provider.
    """

    channel = NotificationChannel.TELEGRAM

    async def send(
        self, recipient: str, title: str, body: str, data: dict[str, Any] | None = None
    ) -> bool:
        await logger.ainfo("mock_telegram_sent", recipient=recipient, title=title)
        return True


class TelegramBotProvider(BaseNotificationProvider):
    """Real Telegram provider backed by the Bot API delivery service.

    ``recipient`` is the user's Telegram ``chat_id`` (looked up from their
    notification preferences by the dispatch layer, which passes it via
    ``data["telegram_chat_id"]``); when it is blank the send is skipped
    (returns False) so unlinked users never hit the Bot API. When the bot
    token is unconfigured the service itself falls back to mock behavior
    with a warning, so this provider never raises for configuration gaps.
    """

    channel = NotificationChannel.TELEGRAM

    def __init__(self, db: Any | None = None) -> None:
        self._db = db

    async def send(
        self, recipient: str, title: str, body: str, data: dict[str, Any] | None = None
    ) -> bool:
        from app.modules.notifications.application import telegram_service

        chat_id = (data or {}).get("telegram_chat_id") or ""
        if not str(chat_id).strip():
            await logger.ainfo("telegram_skipped_no_chat_id", title=title)
            return False

        success, _ = await telegram_service.send_telegram_message(
            self._db,
            chat_id=str(chat_id),
            title=title,
            body=body,
            notification_id=(data or {}).get("notification_id"),
        )
        return success


class MockPushProvider(BaseNotificationProvider):
    """Mock push notification provider for development (kept for tests).

    The live channel uses :class:`WebPushProvider` below; this mock is
    retained for reference and targeted tests.
    """

    channel = NotificationChannel.PUSH

    async def send(
        self, recipient: str, title: str, body: str, data: dict[str, Any] | None = None
    ) -> bool:
        await logger.ainfo("mock_push_sent", recipient=recipient, title=title)
        return True


class WebPushProvider(BaseNotificationProvider):
    """VAPID web-push provider backed by the push delivery service shell.

    ``recipient`` is the user id (string); subscriptions are looked up from
    ``push_subscriptions`` by the service. Until ``pywebpush`` is installed
    (documented dependency gap in push_service.py) the service reports the
    simulated fallback instead of raising.
    """

    channel = NotificationChannel.PUSH

    def __init__(self, db: Any | None = None) -> None:
        self._db = db

    async def send(
        self, recipient: str, title: str, body: str, data: dict[str, Any] | None = None
    ) -> bool:
        from app.modules.notifications.application import push_service

        try:
            user_id = uuid.UUID(recipient)
        except (ValueError, AttributeError, TypeError):
            await logger.ainfo("webpush_skipped_bad_recipient", title=title)
            return False

        success, _delivered = await push_service.send_push_notification(
            self._db, user_id=user_id, title=title, body=body, data=data
        )
        return success


class InAppProvider(BaseNotificationProvider):
    """In-app notifications are stored in the database – no external send needed."""

    channel = NotificationChannel.IN_APP

    async def send(
        self, recipient: str, title: str, body: str, data: dict[str, Any] | None = None
    ) -> bool:
        # In-app notifications are persisted by the service itself.
        return True


# Channel → Provider mapping. The EMAIL/TELEGRAM/PUSH entries are stateless
# placeholders — fresh providers are built per dispatch so the DB session
# (delivery-log persistence) never outlives a request. SMS stays mock at
# this layer (the real Kavenegar/Ghasedak path lives in the messaging hub).
_PROVIDERS: dict[NotificationChannel, BaseNotificationProvider] = {
    NotificationChannel.EMAIL: SMTPEmailProvider(),
    NotificationChannel.SMS: MockSMSProvider(),
    NotificationChannel.TELEGRAM: TelegramBotProvider(),
    NotificationChannel.PUSH: WebPushProvider(),
    NotificationChannel.IN_APP: InAppProvider(),
}


# ── Service ───────────────────────────────────────────────────────────────


class NotificationService:
    """Manages notification creation, delivery, and read-state."""

    # ── Create ────────────────────────────────────────────────────────

    @staticmethod
    async def create_notification(
        db: AsyncSession,
        user_id: uuid.UUID,
        type: str,  # noqa: A002  # API parameter name is the public contract
        title: str,
        body: str,
        data: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> Notification:
        """Create an in-app notification record.

        ``idempotency_key`` deduplicates at-least-once outbox retries: when a
        notification with the same key already exists for the user, the
        existing row is returned instead of inserting a duplicate.
        """
        if idempotency_key:
            existing_stmt = (
                select(Notification)
                .where(
                    Notification.user_id == user_id,
                    Notification.data["_idem"].astext == idempotency_key,
                )
                .limit(1)
            )
            existing = (await db.execute(existing_stmt)).scalar_one_or_none()
            if existing is not None:
                await logger.ainfo(
                    "notification_deduplicated",
                    notification_id=str(existing.id),
                    user_id=str(user_id),
                    type=type,
                )
                return existing
            data = {**(data or {}), "_idem": idempotency_key}

        notification = Notification(
            user_id=user_id,
            type=type,
            title=title,
            body=body,
            data=data,
            is_read=False,
        )
        db.add(notification)
        await db.flush()
        await logger.ainfo(
            "notification_created",
            notification_id=str(notification.id),
            user_id=str(user_id),
            type=type,
        )
        return notification

    # ── Send ──────────────────────────────────────────────────────────

    @staticmethod
    async def send_notification(
        db: AsyncSession,
        notification_id: uuid.UUID,
        channels: list[NotificationChannel],
    ) -> dict[str, bool]:
        """Send a notification through the specified channels.

        Returns a dict mapping channel name to success status.
        """
        stmt = select(Notification).where(Notification.id == notification_id)
        result = await db.execute(stmt)
        notification = result.scalar_one_or_none()
        if not notification:
            raise ValueError(f"Notification {notification_id} not found.")

        results: dict[str, bool] = {}
        for channel in channels:
            provider = _PROVIDERS.get(channel)
            if provider is None:
                results[channel.value] = False
                continue

            # Per-user preferences: an opted-out channel (or opted-out
            # category for this notification type) is skipped BEFORE any
            # provider is touched. The IN_APP record itself is never
            # suppressed here — it was already created by
            # create_notification; preference filtering only gates the
            # external side-effect channels plus in-app provider calls.
            from app.modules.notifications.application import preferences_service

            try:
                allowed = await preferences_service.is_channel_enabled(
                    db, notification.user_id, channel, notification.type
                )
            except Exception:
                # Preference lookup must never block delivery: a broken read
                # falls back to the default-on contract.
                await logger.awarning(
                    "notification_preference_check_failed",
                    notification_id=str(notification_id),
                    channel=channel.value,
                )
                allowed = True
            if not allowed:
                await logger.ainfo(
                    "notification_skipped_opt_out",
                    notification_id=str(notification_id),
                    channel=channel.value,
                    type=notification.type,
                )
                results[channel.value] = False
                continue

            try:
                if channel is NotificationChannel.EMAIL:
                    # Email needs the user's address and the session for the
                    # delivery log; a fresh provider per dispatch keeps the
                    # session bound to this request only.
                    recipient = ""
                    try:
                        from app.modules.users.domain.models import User

                        user = await db.get(User, notification.user_id)
                        recipient = (user.email or "") if user else ""
                    except Exception:
                        await logger.awarning(
                            "email_recipient_lookup_failed",
                            notification_id=str(notification_id),
                        )
                    provider = SMTPEmailProvider(db)
                    data = {**(notification.data or {}), "notification_id": str(notification.id)}
                    success = await provider.send(
                        recipient=recipient,
                        title=notification.title,
                        body=notification.body,
                        data=data,
                    )
                elif channel is NotificationChannel.TELEGRAM:
                    # Telegram needs the user's linked chat_id; a fresh
                    # provider per dispatch keeps the session bound to this
                    # request only (delivery-log persistence).
                    chat_id = ""
                    try:
                        from app.modules.notifications.domain.models import (
                            NotificationPreference,
                        )

                        pref_stmt = select(NotificationPreference).where(
                            NotificationPreference.user_id == notification.user_id
                        )
                        pref = (await db.execute(pref_stmt)).scalar_one_or_none()
                        chat_id = (pref.telegram_chat_id or "") if pref else ""
                    except Exception:
                        await logger.awarning(
                            "telegram_chat_id_lookup_failed",
                            notification_id=str(notification_id),
                        )
                    provider = TelegramBotProvider(db)
                    data = {
                        **(notification.data or {}),
                        "notification_id": str(notification.id),
                        "telegram_chat_id": chat_id,
                    }
                    success = await provider.send(
                        recipient=str(notification.user_id),
                        title=notification.title,
                        body=notification.body,
                        data=data,
                    )
                elif channel is NotificationChannel.PUSH:
                    provider = WebPushProvider(db)
                    success = await provider.send(
                        recipient=str(notification.user_id),
                        title=notification.title,
                        body=notification.body,
                        data=notification.data,
                    )
                else:
                    success = await provider.send(
                        recipient=str(notification.user_id),
                        title=notification.title,
                        body=notification.body,
                        data=notification.data,
                    )
                results[channel.value] = success
            except Exception:
                await logger.aexception(
                    "notification_send_failed",
                    notification_id=str(notification_id),
                    channel=channel.value,
                )
                results[channel.value] = False

        await logger.ainfo(
            "notification_sent",
            notification_id=str(notification_id),
            results=results,
        )
        return results

    # ── Template-based ────────────────────────────────────────────────

    @staticmethod
    async def send_from_template(
        db: AsyncSession,
        user_id: uuid.UUID,
        template_name: str,
        variables: dict[str, str] | None = None,
        channels: list[NotificationChannel] | None = None,
    ) -> Notification:
        """Create and send a notification based on a template."""
        stmt = select(NotificationTemplate).where(NotificationTemplate.name == template_name)
        result = await db.execute(stmt)
        template = result.scalar_one_or_none()
        if not template:
            raise ValueError(f"Template '{template_name}' not found.")

        body = template.body_template
        title = template.subject or template_name
        if variables:
            for key, value in variables.items():
                body = body.replace(f"{{{{{key}}}}}", value)
                title = title.replace(f"{{{{{key}}}}}", value)

        notification = await NotificationService.create_notification(
            db, user_id, type=template_name, title=title, body=body
        )

        send_channels = channels or [template.channel]
        await NotificationService.send_notification(db, notification.id, send_channels)

        return notification

    # ── Read Management ───────────────────────────────────────────────

    @staticmethod
    async def mark_as_read(
        db: AsyncSession, user_id: uuid.UUID, notification_id: uuid.UUID
    ) -> bool:
        """Mark a single notification as read."""
        now = datetime.now(UTC)
        stmt = (
            update(Notification)
            .where(
                Notification.id == notification_id,
                Notification.user_id == user_id,
                Notification.is_read.is_(False),
            )
            .values(is_read=True, read_at=now)
        )
        result = cast("CursorResult[Any]", await db.execute(stmt))
        if result.rowcount > 0:
            await logger.ainfo(
                "notification_marked_read",
                notification_id=str(notification_id),
                user_id=str(user_id),
            )
            return True
        return False

    @staticmethod
    async def mark_all_read(db: AsyncSession, user_id: uuid.UUID) -> int:
        """Mark all unread notifications as read for a user."""
        now = datetime.now(UTC)
        stmt = (
            update(Notification)
            .where(
                Notification.user_id == user_id,
                Notification.is_read.is_(False),
            )
            .values(is_read=True, read_at=now)
        )
        result = cast("CursorResult[Any]", await db.execute(stmt))
        count = int(result.rowcount or 0)
        await logger.ainfo(
            "notifications_marked_all_read",
            user_id=str(user_id),
            count=count,
        )
        return count

    # ── Queries ───────────────────────────────────────────────────────

    @staticmethod
    async def get_notifications(
        db: AsyncSession,
        user_id: uuid.UUID,
        *,
        is_read: bool | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[Notification], int, int]:
        """Return paginated notifications and unread count.

        Returns (items, total, unread_count).
        """
        base = select(Notification).where(Notification.user_id == user_id)
        count_base = (
            select(func.count()).select_from(Notification).where(Notification.user_id == user_id)
        )

        if is_read is not None:
            base = base.where(Notification.is_read == is_read)
            count_base = count_base.where(Notification.is_read == is_read)

        total = (await db.execute(count_base)).scalar_one()

        # Unread count (always full)
        unread_stmt = (
            select(func.count())
            .select_from(Notification)
            .where(
                Notification.user_id == user_id,
                Notification.is_read.is_(False),
            )
        )
        unread_count = (await db.execute(unread_stmt)).scalar_one()

        stmt = base.order_by(Notification.created_at.desc()).offset(skip).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all()), total, unread_count
