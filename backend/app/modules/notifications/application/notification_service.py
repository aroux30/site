"""Notification application service – create, send, and manage notifications.

The email channel and the template machinery were removed on 2026-10-07
(the owner's store is phone-first: login is by phone number and SMS, so
SMTP and the editable email templates have no use). What remains are the
in-app records and the SMS channel stub; the real SMS transport lives in
the messaging hub (``app.modules.messaging``).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast

import structlog
from sqlalchemy import CursorResult, func, select, update

from app.modules.notifications.domain.models import (
    Notification,
    NotificationChannel,
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


class MockSMSProvider(BaseNotificationProvider):
    """Mock SMS provider for development."""

    channel = NotificationChannel.SMS

    async def send(
        self, recipient: str, title: str, body: str, data: dict[str, Any] | None = None
    ) -> bool:
        await logger.ainfo("mock_sms_sent", recipient=recipient, body=body[:100])
        return True


class InAppProvider(BaseNotificationProvider):
    """In-app notifications are stored in the database – no external send needed."""

    channel = NotificationChannel.IN_APP

    async def send(
        self, recipient: str, title: str, body: str, data: dict[str, Any] | None = None
    ) -> bool:
        # In-app notifications are persisted by the service itself.
        return True


# Channel → Provider mapping. SMS stays mock at this layer (the real
# Kavenegar/Ghasedak path lives in the messaging hub).
_PROVIDERS: dict[NotificationChannel, BaseNotificationProvider] = {
    NotificationChannel.SMS: MockSMSProvider(),
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
