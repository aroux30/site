"""Notification background Celery tasks."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

import structlog
from sqlalchemy import select

from app.core.database.session import async_session_factory

# Selecting Notification lazily initializes its mappers, and the mapper
# chain is cross-module: Notification -> User -> (roles -> UserRole) and
# User is also referenced by Order <-> Payment. Every model on that chain
# must be imported BEFORE the first query, or dispatch crashes with
# "When initializing mapper … not defined" (reproduced on a live worker
# 2026-09-18). Keep this list in sync with alembic/env.py.
from app.modules.notifications.domain.models import Notification
from app.modules.orders.domain.models import Order  # noqa: F401
from app.modules.payments.domain.models import Payment  # noqa: F401
from app.modules.rbac.domain.models import Role, UserRole  # noqa: F401
from app.modules.users.domain.models import User
from app.worker.celery_app import celery_app

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


async def _send_notification_async(
    notification_id_str: str,
    channels: list[str] | None = None,
) -> dict[str, Any]:
    """Dispatch a notification across configured channels."""
    notif_id = uuid.UUID(notification_id_str)
    channels = channels or ["in_app"]

    async with async_session_factory() as db:
        try:
            stmt = select(Notification).where(Notification.id == notif_id)
            notif = (await db.execute(stmt)).scalar_one_or_none()
            if not notif:
                return {"status": "error", "message": "Notification not found"}

            user_stmt = select(User).where(User.id == notif.user_id)
            user = (await db.execute(user_stmt)).scalar_one_or_none()

            dispatched_channels: list[str] = []
            for ch in channels:
                if ch == "in_app":
                    dispatched_channels.append("in_app")
                elif ch == "sms" and user and user.phone:
                    # In production, call SMS gateway (e.g. Kavenegar)
                    dispatched_channels.append("sms")
                elif ch == "email" and user and user.email:
                    from app.modules.notifications.application import email_service

                    html = email_service._wrap_html(
                        email_service.get_smtp_config().from_name or "فروشگاه اینترنتی",
                        f"<p>{notif.body}</p>".replace("\n", "<br>"),
                    )
                    success, _log = await email_service.send_email(
                        db,
                        recipient=user.email,
                        subject=notif.title,
                        html_body=html,
                        text_body=notif.body,
                        template=notif.type,
                        notification_id=notif.id,
                    )
                    # Persist the delivery-log row either way; a FAILED row
                    # is exactly what ops needs to see.
                    await db.commit()
                    if success:
                        dispatched_channels.append("email")
                    else:
                        await logger.aerror(
                            "notification_email_delivery_failed",
                            notification_id=str(notif.id),
                            recipient=user.email,
                        )

            await logger.ainfo(
                "notification_dispatched",
                notification_id=str(notif.id),
                user_id=str(notif.user_id),
                channels=dispatched_channels,
            )
            return {
                "status": "success",
                "notification_id": str(notif.id),
                "channels": dispatched_channels,
            }
        except Exception as exc:
            await logger.aerror("notification_dispatch_failed", error=str(exc))
            return {"status": "error", "message": str(exc)}


@celery_app.task(name="app.modules.notifications.application.tasks.send_notification_task")
def send_notification_task(
    notification_id: str,
    channels: list[str] | None = None,
) -> dict[str, Any]:
    """Celery task to dispatch a notification."""
    return asyncio.run(_send_notification_async(notification_id, channels))
