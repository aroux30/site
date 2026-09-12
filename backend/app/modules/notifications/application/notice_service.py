"""Time-bounded notices and seen notices business logic (Karta Phase 6/8).

Implements:
- Querying active notices within time window (start_at <= now <= end_at)
- Filtering out notices already seen by the user (Karta seen_notices)
- Atomic tracking of dismissed/seen notices
- Admin notice management
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.exceptions.handlers import ValidationError
from app.modules.notifications.domain.notice_models import (
    Notice,
    NoticeType,
    SeenNotice,
    TargetPage,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


async def get_active_notices_for_user(
    db: AsyncSession,
    user_id: uuid.UUID | None = None,
    target_page: str = "all",
) -> list[Notice]:
    """Fetch active, in-window notices, omitting popups already seen by the user."""
    now = datetime.now(UTC)
    clean_page = target_page.strip().lower()

    # Query active notices in time window
    stmt = (
        select(Notice)
        .where(
            Notice.is_active.is_(True),
            Notice.start_at <= now,
            Notice.end_at >= now,
        )
        .order_by(Notice.start_at.desc())
    )
    candidates = list((await db.execute(stmt)).scalars().all())

    # Filter target page in memory
    filtered = [
        n for n in candidates
        if n.target_page == TargetPage.ALL or n.target_page.value == clean_page
    ]

    if not user_id:
        return filtered

    safe_user_id = uuid.UUID(str(user_id))

    # Query seen notice IDs for this user
    seen_stmt = select(SeenNotice.notice_id).where(SeenNotice.user_id == safe_user_id)
    seen_ids = set((await db.execute(seen_stmt)).scalars().all())

    return [n for n in filtered if n.id not in seen_ids]


async def mark_notice_as_seen(
    db: AsyncSession,
    user_id: uuid.UUID,
    notice_id: uuid.UUID,
) -> SeenNotice:
    """Record that a user has seen or dismissed a notice (Karta seen_notices)."""
    safe_user_id = uuid.UUID(str(user_id))
    safe_notice_id = uuid.UUID(str(notice_id))

    seen = SeenNotice(
        user_id=safe_user_id,
        notice_id=safe_notice_id,
        seen_at=datetime.now(UTC),
    )

    try:
        async with db.begin_nested():
            db.add(seen)
            await db.flush()
    except IntegrityError:
        pass  # Already marked as seen (idempotent)

    await logger.ainfo("notice_marked_seen", user_id=str(safe_user_id), notice_id=str(safe_notice_id))
    return seen


async def create_notice(
    db: AsyncSession,
    title: str,
    content_html: str,
    notice_type: NoticeType = NoticeType.POPUP,
    target_page: TargetPage = TargetPage.ALL,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
) -> Notice:
    """Admin creation of a scheduled notice."""
    clean_title = title.strip()
    if not clean_title:
        raise ValidationError("عنوان اطلاعیه الزامی است")

    now = datetime.now(UTC)
    effective_start = start_at or now
    effective_end = end_at or (now + datetime.resolution)

    if effective_end <= effective_start:
        raise ValidationError("تاریخ پایان اطلاعیه باید بعد از تاریخ شروع باشد")

    notice = Notice(
        title=clean_title,
        content_html=content_html,
        notice_type=notice_type,
        target_page=target_page,
        start_at=effective_start,
        end_at=effective_end,
        is_active=True,
    )
    db.add(notice)
    await db.flush()

    await logger.ainfo("notice_created", notice_id=str(notice.id), title=clean_title)
    return notice


async def list_all_notices(
    db: AsyncSession,
) -> list[Notice]:
    """List all notices for admin management."""
    stmt = select(Notice).order_by(Notice.created_at.desc())
    return list((await db.execute(stmt)).scalars().all())
