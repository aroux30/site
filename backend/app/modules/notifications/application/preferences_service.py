"""Per-user notification preferences: channel/category opt-in matrix.

One :class:`NotificationPreference` row per user, created lazily on first
access. Semantics:

- **Default: all on.** A missing row, a missing channel/category key, or a
  ``null`` value all mean "enabled". Users only ever store their opt-outs,
  so channels or categories added to the platform later start enabled
  (opt-out model) — matching the v1 contract.
- Dispatch (``NotificationService.send_notification``) calls
  :func:`is_channel_enabled` before touching a provider; an opted-out
  channel is skipped and reported as ``skipped_opt_out`` in the results
  instead of a provider call.
- Category derivation: the notification ``type`` string is mapped to a
  :class:`NotificationCategory` by prefix (``order_*`` → order, ``payment_*``/
  ``wallet_*``/``refund_*`` → payment, ``shipment_*``/``shipping_*`` →
  shipping, ``promotion_*``/``discount_*``/``campaign_*`` → promotion,
  everything else → system).
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import select

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.notifications.domain.models import NotificationPreference

from app.modules.notifications.domain.models import (
    NotificationCategory,
    NotificationChannel,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# Notification type-prefix → category. First match wins; unknown types are
# SYSTEM so a new notification kind can never bypass an opt-out silently.
_CATEGORY_PREFIXES: tuple[tuple[str, NotificationCategory], ...] = (
    ("order_", NotificationCategory.ORDER),
    ("payment_", NotificationCategory.PAYMENT),
    ("wallet_", NotificationCategory.PAYMENT),
    ("refund_", NotificationCategory.PAYMENT),
    ("shipment_", NotificationCategory.SHIPPING),
    ("shipping_", NotificationCategory.SHIPPING),
    ("promotion_", NotificationCategory.PROMOTION),
    ("discount_", NotificationCategory.PROMOTION),
    ("campaign_", NotificationCategory.PROMOTION),
)


def category_for_type(notification_type: str) -> NotificationCategory:
    """Map a notification type string to its preference category."""
    lowered = (notification_type or "").lower()
    for prefix, category in _CATEGORY_PREFIXES:
        if lowered.startswith(prefix):
            return category
    return NotificationCategory.SYSTEM


async def get_or_create_preferences(
    db: AsyncSession, user_id: uuid.UUID
) -> "NotificationPreference":
    """Fetch the user's preference row, creating the default (all-on) row."""
    from app.modules.notifications.domain.models import NotificationPreference

    pref = (
        await db.execute(
            select(NotificationPreference).where(NotificationPreference.user_id == user_id)
        )
    ).scalar_one_or_none()
    if pref is None:
        pref = NotificationPreference(user_id=user_id)
        db.add(pref)
        await db.flush()
    return pref


def effective_channel_matrix(pref: "NotificationPreference | None") -> dict[str, bool]:
    """Resolved channel → enabled map, defaulting every channel to True."""
    stored = (pref.channels or {}) if pref is not None else {}
    return {
        channel.value: bool(stored.get(channel.value, True))
        for channel in NotificationChannel
    }


def effective_category_matrix(pref: "NotificationPreference | None") -> dict[str, bool]:
    """Resolved category → enabled map, defaulting every category to True."""
    stored = (pref.categories or {}) if pref is not None else {}
    return {
        category.value: bool(stored.get(category.value, True))
        for category in NotificationCategory
    }


async def update_preferences(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    channels: dict[str, bool] | None = None,
    categories: dict[str, bool] | None = None,
) -> "NotificationPreference":
    """Merge channel/category updates into the user's preference row.

    Unknown channel/category keys are dropped (never persisted) so a stale
    client cannot wedge undeletable keys into the JSONB blobs.
    """
    pref = await get_or_create_preferences(db, user_id)
    valid_channels = {c.value for c in NotificationChannel}
    valid_categories = {c.value for c in NotificationCategory}

    if channels is not None:
        merged = dict(pref.channels or {})
        for key, enabled in channels.items():
            if key in valid_channels:
                merged[key] = bool(enabled)
        pref.channels = merged
    if categories is not None:
        merged = dict(pref.categories or {})
        for key, enabled in categories.items():
            if key in valid_categories:
                merged[key] = bool(enabled)
        pref.categories = merged

    await db.flush()
    await logger.ainfo("notification_preferences_updated", user_id=str(user_id))
    return pref


def _is_enabled(matrix_value: Any) -> bool:
    """Default-on: only an explicit False disables a channel/category."""
    return matrix_value is not False


async def is_channel_enabled(
    db: AsyncSession,
    user_id: uuid.UUID,
    channel: NotificationChannel,
    notification_type: str,
) -> bool:
    """Whether a dispatch to ``channel`` for ``notification_type`` is allowed.

    Both the channel itself AND the category derived from the type must be
    enabled. A missing preference row (user never touched settings) means
    everything is on — no row is created by this read path.
    """
    from app.modules.notifications.domain.models import NotificationPreference

    pref = (
        await db.execute(
            select(NotificationPreference).where(NotificationPreference.user_id == user_id)
        )
    ).scalar_one_or_none()
    if pref is None:
        return True

    channels = pref.channels or {}
    categories = pref.categories or {}
    category = category_for_type(notification_type)

    if not _is_enabled(channels.get(channel.value)):
        return False
    return _is_enabled(categories.get(category.value))
