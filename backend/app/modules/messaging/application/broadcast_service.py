"""Broadcast Messaging application service (پیام‌رسانی انبوه و بخش‌بندی کاربران)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Sequence

import structlog
from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.cart.domain.models import Cart, CartStatus
from app.modules.messaging.domain.models import (
    BroadcastCampaign,
    BroadcastRecipient,
    CampaignChannel,
    CampaignStatus,
    RecipientStatus,
    TargetSegment,
)
from app.modules.messaging.schemas.campaign import (
    BroadcastCampaignCreate,
    BroadcastCampaignUpdate,
)
from app.modules.notifications.application.notification_service import (
    NotificationService,
    _PROVIDERS,
)
from app.modules.notifications.domain.models import NotificationChannel
from app.modules.orders.domain.models import Order
from app.modules.users.domain.models import User
from app.modules.wishlist.domain.models import Wishlist, WishlistItem

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


# ── Campaign CRUD ─────────────────────────────────────────────────────────


async def create_campaign(
    db: AsyncSession,
    data: BroadcastCampaignCreate,
) -> BroadcastCampaign:
    """Create a new broadcast campaign in draft or scheduled state."""
    initial_status = data.status or CampaignStatus.DRAFT
    if data.scheduled_at and initial_status == CampaignStatus.DRAFT:
        initial_status = CampaignStatus.SCHEDULED

    campaign = BroadcastCampaign(
        title=data.title,
        channel=data.channel,
        target_segment=data.target_segment,
        message_template=data.message_template,
        scheduled_at=data.scheduled_at,
        status=initial_status,
        ab_test_enabled=data.ab_test_enabled,
        variant_b_template=data.variant_b_template,
    )
    db.add(campaign)
    await db.flush()
    await db.refresh(campaign)

    await logger.ainfo(
        "campaign_created",
        campaign_id=str(campaign.id),
        title=campaign.title,
        channel=campaign.channel.value,
        target_segment=campaign.target_segment.value,
        status=campaign.status.value,
    )
    return campaign


async def get_campaign(
    db: AsyncSession,
    campaign_id: uuid.UUID,
) -> Optional[BroadcastCampaign]:
    """Retrieve a single broadcast campaign by its UUID."""
    stmt = select(BroadcastCampaign).where(BroadcastCampaign.id == campaign_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_campaigns(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    status: Optional[CampaignStatus] = None,
) -> tuple[Sequence[BroadcastCampaign], int]:
    """List broadcast campaigns with pagination and optional status filter."""
    page = max(1, page)
    page_size = max(1, min(100, page_size))
    offset = (page - 1) * page_size

    base_query = select(BroadcastCampaign)
    count_query = select(func.count(BroadcastCampaign.id))

    if status is not None:
        base_query = base_query.where(BroadcastCampaign.status == status)
        count_query = count_query.where(BroadcastCampaign.status == status)

    total = (await db.execute(count_query)).scalar() or 0
    items = (
        await db.execute(
            base_query.order_by(BroadcastCampaign.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
    ).scalars().all()

    return items, total


async def update_campaign(
    db: AsyncSession,
    campaign_id: uuid.UUID,
    data: BroadcastCampaignUpdate,
) -> BroadcastCampaign:
    """Update mutable fields of a draft or scheduled campaign."""
    campaign = await get_campaign(db, campaign_id)
    if not campaign:
        raise ValueError(f"Campaign with ID {campaign_id} not found")

    if campaign.status in (CampaignStatus.PROCESSING, CampaignStatus.SENT):
        raise ValueError("Cannot modify a campaign that is already processing or sent")

    update_fields = data.model_dump(exclude_unset=True)
    for field, value in update_fields.items():
        setattr(campaign, field, value)

    await db.flush()
    await db.refresh(campaign)

    await logger.ainfo("campaign_updated", campaign_id=str(campaign.id))
    return campaign


# ── Audience Segmentation & Estimation ────────────────────────────────────


def _build_segment_query(segment: TargetSegment):
    """Build SQLAlchemy query returning target User IDs for a given segment.

    Criteria:
    - all_users: total active users
    - active_buyers: users with orders in last 60 days
    - inactive_users: users with no orders in last 90 days
    - abandoned_carts: users with active carts older than 2 hours
    - wishlist_users: users with >= 1 items in wishlist
    """
    now = datetime.now(timezone.utc)

    if segment == TargetSegment.ALL_USERS:
        return select(User.id).where(User.is_active.is_(True))

    elif segment == TargetSegment.ACTIVE_BUYERS:
        cutoff_60d = now - timedelta(days=60)
        return (
            select(distinct(Order.user_id))
            .join(User, User.id == Order.user_id)
            .where(
                User.is_active.is_(True),
                Order.created_at >= cutoff_60d,
            )
        )

    elif segment == TargetSegment.INACTIVE_USERS:
        cutoff_90d = now - timedelta(days=90)
        recent_orders_subquery = (
            select(Order.user_id)
            .where(
                Order.user_id.isnot(None),
                Order.created_at >= cutoff_90d,
            )
            .scalar_subquery()
        )
        return select(User.id).where(
            User.is_active.is_(True),
            ~User.id.in_(recent_orders_subquery),
        )

    elif segment == TargetSegment.ABANDONED_CARTS:
        cutoff_2h = now - timedelta(hours=2)
        return (
            select(distinct(Cart.user_id))
            .join(User, User.id == Cart.user_id)
            .where(
                User.is_active.is_(True),
                Cart.user_id.isnot(None),
                Cart.status == CartStatus.ACTIVE,
                func.coalesce(Cart.updated_at, Cart.created_at) <= cutoff_2h,
            )
        )

    elif segment == TargetSegment.WISHLIST_USERS:
        return (
            select(distinct(Wishlist.user_id))
            .join(WishlistItem, WishlistItem.wishlist_id == Wishlist.id)
            .join(User, User.id == Wishlist.user_id)
            .where(
                User.is_active.is_(True),
            )
        )

    else:
        raise ValueError(f"Unsupported target segment: {segment}")


async def estimate_segment_size(
    db: AsyncSession,
    segment: TargetSegment | str,
) -> int:
    """Count users matching the target segment criteria."""
    if isinstance(segment, str):
        try:
            segment = TargetSegment(segment)
        except ValueError:
            raise ValueError(f"Invalid segment name: '{segment}'")

    subquery = _build_segment_query(segment)
    count_stmt = select(func.count()).select_from(subquery.subquery())
    result = await db.execute(count_stmt)
    count = result.scalar() or 0

    await logger.ainfo(
        "segment_estimated",
        segment=segment.value,
        estimated_count=count,
    )
    return count


# ── Campaign Execution & Dispatch ─────────────────────────────────────────


async def _dispatch_single_recipient(
    db: AsyncSession,
    channel: CampaignChannel,
    title: str,
    body: str,
    user: Optional[User],
) -> tuple[bool, Optional[str]]:
    """Dispatch a message to a single user through the specified channel."""
    if not user:
        return False, "Target user not found"

    try:
        if channel == CampaignChannel.IN_APP:
            await NotificationService.create_notification(
                db=db,
                user_id=user.id,
                type="broadcast",
                title=title,
                body=body,
            )
            return True, None

        elif channel == CampaignChannel.SMS:
            if not user.phone:
                return False, "User has no phone number"
            provider = _PROVIDERS.get(NotificationChannel.SMS)
            if provider:
                success = await provider.send(
                    recipient=user.phone,
                    title=title,
                    body=body,
                )
                return (True, None) if success else (False, "SMS provider returned failure")
            return True, None

        elif channel == CampaignChannel.EMAIL:
            if not user.email:
                return False, "User has no email address"
            provider = _PROVIDERS.get(NotificationChannel.EMAIL)
            if provider:
                success = await provider.send(
                    recipient=user.email,
                    title=title,
                    body=body,
                )
                return (True, None) if success else (False, "Email provider returned failure")
            return True, None

        elif channel == CampaignChannel.PUSH:
            provider = _PROVIDERS.get(NotificationChannel.PUSH)
            if provider:
                success = await provider.send(
                    recipient=str(user.id),
                    title=title,
                    body=body,
                )
                return (True, None) if success else (False, "Push provider returned failure")
            return True, None

        else:
            return False, f"Unsupported channel: {channel}"

    except Exception as exc:
        await logger.aerror(
            "dispatch_error",
            channel=channel.value,
            user_id=str(user.id) if user else None,
            error=str(exc),
        )
        return False, str(exc)


async def send_campaign(
    db: AsyncSession,
    campaign_id: uuid.UUID,
) -> BroadcastCampaign:
    """Execute a broadcast campaign.

    Steps:
    1. Validate campaign existence and state.
    2. Mark status as PROCESSING.
    3. Query target audience based on segment criteria.
    4. Create recipient log rows with A/B variant split.
    5. Dispatch messages via notification providers / service.
    6. Update success/fail counters and transition status to SENT or FAILED.
    """
    campaign = await get_campaign(db, campaign_id)
    if not campaign:
        raise ValueError(f"Campaign with ID {campaign_id} not found")

    if campaign.status in (CampaignStatus.SENT, CampaignStatus.PROCESSING):
        raise ValueError(f"Campaign is already in '{campaign.status.value}' state")

    # Transition to PROCESSING
    campaign.status = CampaignStatus.PROCESSING
    await db.flush()

    await logger.ainfo(
        "campaign_send_started",
        campaign_id=str(campaign.id),
        segment=campaign.target_segment.value,
        channel=campaign.channel.value,
    )

    try:
        # Query target user IDs
        segment_query = _build_segment_query(campaign.target_segment)
        target_user_ids = list((await db.execute(segment_query)).scalars().all())
        campaign.total_recipients = len(target_user_ids)

        if not target_user_ids:
            campaign.status = CampaignStatus.SENT
            campaign.sent_at = datetime.now(timezone.utc)
            campaign.success_count = 0
            campaign.fail_count = 0
            await db.flush()
            await db.refresh(campaign)
            await logger.ainfo("campaign_empty_audience", campaign_id=str(campaign.id))
            return campaign

        # Load users for contact details
        users_result = await db.execute(
            select(User).where(User.id.in_(target_user_ids))
        )
        users_by_id = {u.id: u for u in users_result.scalars().all()}

        success_count = 0
        fail_count = 0

        # Create recipient records and dispatch
        for idx, user_id in enumerate(target_user_ids):
            user = users_by_id.get(user_id)

            # A/B variant assignment
            if campaign.ab_test_enabled and campaign.variant_b_template:
                variant_used = "A" if idx % 2 == 0 else "B"
                template_to_use = (
                    campaign.message_template
                    if variant_used == "A"
                    else campaign.variant_b_template
                )
            else:
                variant_used = "A"
                template_to_use = campaign.message_template

            recipient = BroadcastRecipient(
                campaign_id=campaign.id,
                user_id=user_id,
                variant_used=variant_used,
                status=RecipientStatus.PENDING,
            )
            db.add(recipient)
            await db.flush()

            # Dispatch
            delivered, error = await _dispatch_single_recipient(
                db=db,
                channel=campaign.channel,
                title=campaign.title,
                body=template_to_use,
                user=user,
            )

            if delivered:
                recipient.status = RecipientStatus.SENT
                recipient.sent_at = datetime.now(timezone.utc)
                success_count += 1
            else:
                recipient.status = RecipientStatus.FAILED
                recipient.error_message = error
                fail_count += 1

        campaign.success_count = success_count
        campaign.fail_count = fail_count
        campaign.sent_at = datetime.now(timezone.utc)
        campaign.status = (
            CampaignStatus.SENT
            if success_count > 0 or len(target_user_ids) == 0
            else CampaignStatus.FAILED
        )

        await db.flush()
        await db.refresh(campaign)

        await logger.ainfo(
            "campaign_sent",
            campaign_id=str(campaign.id),
            total=campaign.total_recipients,
            success=campaign.success_count,
            fail=campaign.fail_count,
            status=campaign.status.value,
        )
        return campaign

    except Exception as exc:
        await logger.aerror(
            "campaign_send_failed",
            campaign_id=str(campaign.id),
            error=str(exc),
        )
        campaign.status = CampaignStatus.FAILED
        await db.flush()
        await db.refresh(campaign)
        raise
