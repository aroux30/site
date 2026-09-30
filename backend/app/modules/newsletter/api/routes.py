"""Newsletter API routes — public double-opt-in + admin management."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import structlog
from fastapi import APIRouter, Depends, Query, Request, status

from app.core.database.session import get_db
from app.core.exceptions.handlers import ValidationError
from app.core.security.dependencies import RequirePermissions, get_current_user_id
from app.core.security.rate_limiter import limiter
from app.modules.newsletter.application import campaign_service, newsletter_service
from app.modules.newsletter.domain.models import (
    CampaignStatus,
    NewsletterCampaign,
    NewsletterSubscriber,
)
from app.modules.newsletter.schemas.newsletter import (
    CampaignCreate,
    CampaignListResponse,
    CampaignPreviewResponse,
    CampaignRecipientListResponse,
    CampaignRecipientResponse,
    CampaignResponse,
    CampaignScheduleRequest,
    CampaignSendResponse,
    CampaignTestSendRequest,
    CampaignTestSendResponse,
    CampaignUpdate,
    ConfirmRequest,
    SubscribeRequest,
    SubscribeResponse,
    SubscriberListResponse,
    SubscriberResponse,
    SubscriptionStatusResponse,
    UnsubscribeRequest,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

router = APIRouter()
admin_router = APIRouter()


# ── Public lifecycle ──────────────────────────────────────────────────────


@router.post(
    "/subscribe",
    response_model=SubscribeResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Request a newsletter subscription (double opt-in)",
)
@limiter.limit("5/minute")
async def subscribe(
    request: Request,
    body: SubscribeRequest,
    db: AsyncSession = Depends(get_db),
) -> SubscribeResponse:
    """Record the signup and email a confirmation link.

    The response is identical whether or not the address is new, pending, or
    already subscribed, so the endpoint cannot be used to probe which
    addresses exist on the list.
    """
    await newsletter_service.subscribe(db, email=body.email, source=body.source)
    return SubscribeResponse(message=newsletter_service.GENERIC_SUBSCRIBE_MESSAGE)


@router.post(
    "/confirm",
    response_model=SubscriptionStatusResponse,
    summary="Confirm a subscription with the emailed token",
)
@limiter.limit("20/minute")
async def confirm(
    request: Request,
    body: ConfirmRequest,
    db: AsyncSession = Depends(get_db),
) -> SubscriptionStatusResponse:
    subscriber = await newsletter_service.confirm(db, email=body.email, token=body.token)
    return SubscriptionStatusResponse(status=subscriber.status)


@router.post(
    "/unsubscribe",
    response_model=SubscriptionStatusResponse,
    summary="Opt out with the one-click link token",
)
@limiter.limit("20/minute")
async def unsubscribe(
    request: Request,
    body: UnsubscribeRequest,
    db: AsyncSession = Depends(get_db),
) -> SubscriptionStatusResponse:
    subscriber = await newsletter_service.unsubscribe(
        db, email=body.email, token=body.token
    )
    return SubscriptionStatusResponse(status=subscriber.status)


# ── Admin ─────────────────────────────────────────────────────────────────


@admin_router.get(
    "/admin/newsletter/subscribers",
    response_model=SubscriberListResponse,
    summary="Admin — Paginated subscriber list",
    dependencies=[Depends(RequirePermissions("newsletter:read"))],
)
async def admin_list_subscribers(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> SubscriberListResponse:
    """List subscribers newest-first with a per-status count summary.

    Declared before ``/subscribers/{email}`` on purpose: the parameter route
    would otherwise swallow the bare list path (same declaration-order rule
    as the settings ``/{key}`` route).
    """
    from app.modules.newsletter.application import admin_queries

    items, total, status_counts = await admin_queries.list_subscribers(
        db, page=page, page_size=page_size
    )
    return SubscriberListResponse(
        items=[SubscriberResponse.model_validate(s) for s in items],
        total=total,
        page=page,
        page_size=page_size,
        status_counts={
            "pending": status_counts.get("pending", 0),
            "subscribed": status_counts.get("subscribed", 0),
            "unsubscribed": status_counts.get("unsubscribed", 0),
        },
    )


@admin_router.get(
    "/admin/newsletter/export.csv",
    summary="Admin — CSV export of the subscriber list",
    dependencies=[Depends(RequirePermissions("newsletter:read"))],
)
async def admin_export_subscribers(db: AsyncSession = Depends(get_db)):
    """Download every subscriber as CSV (the WordPress export-users shape)."""
    from fastapi.responses import PlainTextResponse

    from app.modules.newsletter.application import admin_queries

    csv_text = await admin_queries.export_csv(db)
    return PlainTextResponse(
        csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=newsletter-subscribers.csv"},
    )


@admin_router.get(
    "/admin/newsletter/subscribers/{email}",
    response_model=SubscriberResponse,
    summary="Admin — Fetch one subscriber",
    dependencies=[Depends(RequirePermissions("newsletter:read"))],
)
async def admin_get_subscriber(
    email: str,
    db: AsyncSession = Depends(get_db),
) -> SubscriberResponse:
    from app.core.exceptions.handlers import NotFoundError

    subscriber = await db.get(NewsletterSubscriber, email.strip().lower())
    if subscriber is None:
        raise NotFoundError(resource="Subscriber")
    return SubscriberResponse.model_validate(subscriber)


@admin_router.delete(
    "/admin/newsletter/subscribers/{email}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Admin — Erase one subscriber (GDPR)",
    dependencies=[Depends(RequirePermissions("newsletter:write"))],
)
async def admin_delete_subscriber(
    email: str,
    actor_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> None:
    await newsletter_service.admin_delete_subscriber(
        db, email=email.strip().lower(), actor_id=actor_id
    )


# ── Admin — campaigns ─────────────────────────────────────────────────────


@admin_router.get(
    "/admin/newsletter/campaigns",
    response_model=CampaignListResponse,
    summary="Admin — List campaigns",
    dependencies=[Depends(RequirePermissions("newsletter:read"))],
)
async def admin_list_campaigns(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> CampaignListResponse:
    items, total = await campaign_service.list_campaigns(db, page=page, page_size=page_size)
    return CampaignListResponse(
        items=[CampaignResponse.model_validate(c) for c in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@admin_router.post(
    "/admin/newsletter/campaigns",
    response_model=CampaignResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Admin — Create a draft campaign",
    dependencies=[Depends(RequirePermissions("newsletter:write"))],
)
async def admin_create_campaign(
    body: CampaignCreate,
    actor_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> CampaignResponse:
    campaign = await campaign_service.create_campaign(
        db,
        name=body.name,
        subject=body.subject,
        body_html=body.body_html,
        body_text=body.body_text,
        preheader=body.preheader,
        created_by=actor_id,
    )
    await _audit(
        db,
        actor_id=actor_id,
        action="newsletter.campaign_created",
        campaign=campaign,
    )
    return CampaignResponse.model_validate(campaign)


@admin_router.get(
    "/admin/newsletter/campaigns/{campaign_id}",
    response_model=CampaignResponse,
    summary="Admin — Fetch one campaign",
    dependencies=[Depends(RequirePermissions("newsletter:read"))],
)
async def admin_get_campaign(
    campaign_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> CampaignResponse:
    campaign = await campaign_service.get_campaign(db, campaign_id)
    return CampaignResponse.model_validate(campaign)


@admin_router.patch(
    "/admin/newsletter/campaigns/{campaign_id}",
    response_model=CampaignResponse,
    summary="Admin — Update a draft campaign",
    dependencies=[Depends(RequirePermissions("newsletter:write"))],
)
async def admin_update_campaign(
    campaign_id: uuid.UUID,
    body: CampaignUpdate,
    actor_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> CampaignResponse:
    campaign = await campaign_service.update_campaign(
        db,
        campaign_id,
        name=body.name,
        subject=body.subject,
        preheader=body.preheader,
        body_html=body.body_html,
        body_text=body.body_text,
    )
    await _audit(
        db,
        actor_id=actor_id,
        action="newsletter.campaign_updated",
        campaign=campaign,
    )
    return CampaignResponse.model_validate(campaign)


@admin_router.delete(
    "/admin/newsletter/campaigns/{campaign_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Admin — Delete a draft/failed campaign",
    dependencies=[Depends(RequirePermissions("newsletter:write"))],
)
async def admin_delete_campaign(
    campaign_id: uuid.UUID,
    actor_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> None:
    await campaign_service.delete_campaign(db, campaign_id)
    await _audit(
        db,
        actor_id=actor_id,
        action="newsletter.campaign_deleted",
        resource_id=campaign_id,
    )


@admin_router.get(
    "/admin/newsletter/campaigns/{campaign_id}/preview",
    response_model=CampaignPreviewResponse,
    summary="Admin — Rendered preview (unsubscribe footer included)",
    dependencies=[Depends(RequirePermissions("newsletter:read"))],
)
async def admin_preview_campaign(
    campaign_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> CampaignPreviewResponse:
    campaign = await campaign_service.get_campaign(db, campaign_id)
    subject, html_body, text_body = await campaign_service.preview_campaign(db, campaign)
    return CampaignPreviewResponse(subject=subject, html=html_body, text=text_body)


@admin_router.post(
    "/admin/newsletter/campaigns/{campaign_id}/send",
    response_model=CampaignSendResponse,
    summary="Admin — Send now (Celery; inline fallback when no broker)",
    dependencies=[Depends(RequirePermissions("newsletter:write"))],
)
async def admin_send_campaign(
    campaign_id: uuid.UUID,
    actor_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> CampaignSendResponse:
    campaign = await campaign_service.get_campaign(db, campaign_id)
    if campaign.status in (CampaignStatus.SENDING, CampaignStatus.SENT):
        raise ValidationError(detail="این کمپین قبلاً ارسال شده است.")

    # Snapshot now (idempotent — the worker task reuses the same rows) so the
    # admin immediately sees the audience size and the recipients endpoint.
    total_recipients = await campaign_service.snapshot_recipients(db, campaign)
    if total_recipients == 0:
        raise ValidationError(detail="هیچ عضو تأییدشده‌ای برای ارسال وجود ندارد.")

    queued = campaign_service.enqueue_send(campaign.id)
    await _audit(
        db,
        actor_id=actor_id,
        action=(
            "newsletter.campaign_send_queued" if queued else "newsletter.campaign_send_inline"
        ),
        campaign=campaign,
        after={"total_recipients": total_recipients},
    )

    if queued:
        return CampaignSendResponse(
            id=campaign.id,
            status=campaign.status,
            mode="queued",
            total_recipients=total_recipients,
        )

    # No broker (dev / single-process deployment): send within this request
    # instead of failing the admin action. The counters dict mirrors the
    # task result; a ValidationError inside (e.g. list emptied concurrently)
    # propagates to the normal error envelope.
    result = await campaign_service.send_campaign(db, campaign.id)
    return CampaignSendResponse(
        id=campaign.id,
        status=CampaignStatus(str(result["status"])),
        mode="inline",
        total_recipients=int(result["total_recipients"]),  # type: ignore[arg-type]
        total_sent=int(result["total_sent"]),  # type: ignore[arg-type]
        total_failed=int(result["total_failed"]),  # type: ignore[arg-type]
    )


@admin_router.post(
    "/admin/newsletter/campaigns/{campaign_id}/schedule",
    response_model=CampaignResponse,
    summary="Admin — Schedule (or re-time) the campaign",
    dependencies=[Depends(RequirePermissions("newsletter:write"))],
)
async def admin_schedule_campaign(
    campaign_id: uuid.UUID,
    body: CampaignScheduleRequest,
    actor_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> CampaignResponse:
    campaign = await campaign_service.schedule_campaign(
        db, campaign_id, scheduled_at=body.scheduled_at
    )
    await _audit(
        db,
        actor_id=actor_id,
        action="newsletter.campaign_scheduled",
        campaign=campaign,
        after={"scheduled_at": body.scheduled_at.isoformat()},
    )
    return CampaignResponse.model_validate(campaign)


@admin_router.post(
    "/admin/newsletter/campaigns/{campaign_id}/test",
    response_model=CampaignTestSendResponse,
    summary="Admin — Send a preview of this campaign to one address",
    dependencies=[Depends(RequirePermissions("newsletter:write"))],
)
async def admin_test_campaign(
    campaign_id: uuid.UUID,
    body: CampaignTestSendRequest,
    db: AsyncSession = Depends(get_db),
) -> CampaignTestSendResponse:
    campaign = await campaign_service.get_campaign(db, campaign_id)
    sent = await campaign_service.send_test_email(db, campaign, email=body.email)
    return CampaignTestSendResponse(email=body.email, sent=sent)


@admin_router.get(
    "/admin/newsletter/campaigns/{campaign_id}/recipients",
    response_model=CampaignRecipientListResponse,
    summary="Admin — Per-recipient delivery status for one campaign",
    dependencies=[Depends(RequirePermissions("newsletter:read"))],
)
async def admin_list_campaign_recipients(
    campaign_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> CampaignRecipientListResponse:
    await campaign_service.get_campaign(db, campaign_id)  # 404 when unknown
    items, total = await campaign_service.list_recipients(
        db, campaign_id, page=page, page_size=page_size
    )
    return CampaignRecipientListResponse(
        items=[CampaignRecipientResponse.model_validate(r) for r in items],
        total=total,
        page=page,
        page_size=page_size,
    )


async def _audit(
    db: AsyncSession,
    *,
    actor_id: uuid.UUID,
    action: str,
    campaign: NewsletterCampaign | None = None,
    resource_id: uuid.UUID | None = None,
    after: dict[str, object] | None = None,
) -> None:
    """Best-effort audit row for an admin campaign action."""
    from app.modules.audit.application.audit_service import log_action

    await log_action(
        db,
        actor_id=actor_id,
        action=action,
        resource="newsletter_campaign",
        resource_id=(campaign.id if campaign is not None else resource_id),
        after=after,
    )
