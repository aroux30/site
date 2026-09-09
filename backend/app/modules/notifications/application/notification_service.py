"""Notification application service – create, send, and manage notifications."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import structlog
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.notifications.domain.models import (
    Notification,
    NotificationChannel,
    NotificationTemplate,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger()


# ── Provider Abstraction ──────────────────────────────────────────────────


class BaseNotificationProvider:
    """Abstract base for notification channel providers."""

    channel: NotificationChannel

    async def send(self, recipient: str, title: str, body: str, data: Optional[dict] = None) -> bool:
        raise NotImplementedError


class MockEmailProvider(BaseNotificationProvider):
    """Mock email provider for development."""

    channel = NotificationChannel.EMAIL

    async def send(self, recipient: str, title: str, body: str, data: Optional[dict] = None) -> bool:
        await logger.ainfo("mock_email_sent", recipient=recipient, title=title)
        return True


class MockSMSProvider(BaseNotificationProvider):
    """Mock SMS provider for development."""

    channel = NotificationChannel.SMS

    async def send(self, recipient: str, title: str, body: str, data: Optional[dict] = None) -> bool:
        await logger.ainfo("mock_sms_sent", recipient=recipient, body=body[:100])
        return True


class MockTelegramProvider(BaseNotificationProvider):
    """Mock Telegram provider for development."""

    channel = NotificationChannel.TELEGRAM

    async def send(self, recipient: str, title: str, body: str, data: Optional[dict] = None) -> bool:
        await logger.ainfo("mock_telegram_sent", recipient=recipient, title=title)
        return True


class MockPushProvider(BaseNotificationProvider):
    """Mock push notification provider for development."""

    channel = NotificationChannel.PUSH

    async def send(self, recipient: str, title: str, body: str, data: Optional[dict] = None) -> bool:
        await logger.ainfo("mock_push_sent", recipient=recipient, title=title)
        return True


class InAppProvider(BaseNotificationProvider):
    """In-app notifications are stored in the database – no external send needed."""

    channel = NotificationChannel.IN_APP

    async def send(self, recipient: str, title: str, body: str, data: Optional[dict] = None) -> bool:
        # In-app notifications are persisted by the service itself.
        return True


# Channel → Provider mapping
_PROVIDERS: dict[NotificationChannel, BaseNotificationProvider] = {
    NotificationChannel.EMAIL: MockEmailProvider(),
    NotificationChannel.SMS: MockSMSProvider(),
    NotificationChannel.TELEGRAM: MockTelegramProvider(),
    NotificationChannel.PUSH: MockPushProvider(),
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
        type: str,
        title: str,
        body: str,
        data: Optional[dict[str, Any]] = None,
    ) -> Notification:
        """Create an in-app notification record."""
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
            try:
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
        variables: Optional[dict[str, str]] = None,
        channels: Optional[list[NotificationChannel]] = None,
    ) -> Notification:
        """Create and send a notification based on a template."""
        stmt = select(NotificationTemplate).where(
            NotificationTemplate.name == template_name
        )
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
        now = datetime.now(timezone.utc)
        stmt = (
            update(Notification)
            .where(
                Notification.id == notification_id,
                Notification.user_id == user_id,
                Notification.is_read == False,  # noqa: E712
            )
            .values(is_read=True, read_at=now)
        )
        result = await db.execute(stmt)
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
        now = datetime.now(timezone.utc)
        stmt = (
            update(Notification)
            .where(
                Notification.user_id == user_id,
                Notification.is_read == False,  # noqa: E712
            )
            .values(is_read=True, read_at=now)
        )
        result = await db.execute(stmt)
        count = result.rowcount
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
        is_read: Optional[bool] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[Notification], int, int]:
        """Return paginated notifications and unread count.

        Returns (items, total, unread_count).
        """
        base = select(Notification).where(Notification.user_id == user_id)
        count_base = (
            select(func.count())
            .select_from(Notification)
            .where(Notification.user_id == user_id)
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
                Notification.is_read == False,  # noqa: E712
            )
        )
        unread_count = (await db.execute(unread_stmt)).scalar_one()

        stmt = (
            base.order_by(Notification.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all()), total, unread_count
