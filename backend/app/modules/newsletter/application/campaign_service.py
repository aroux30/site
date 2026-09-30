"""Newsletter campaign service — create, schedule, and send to the list.

The missing half of the newsletter module: subscribers existed but nothing
could mail them. Campaigns are admin-authored HTML mails rendered with a
mandatory per-recipient unsubscribe footer, snapshotted against the
currently-confirmed list at send time, and dispatched in chunks through the
notifications ``send_email`` transport (SMTP with delivery-log rows).

Guarantees:

- Only ``subscribed`` (i.e. confirmed via double opt-in) addresses are ever
  snapshotted as recipients, and each address is re-checked against its
  subscriber row immediately before its personal send — an unsubscribe that
  lands mid-send (clicking the footer link of an earlier batch) removes the
  recipient instead of mailing them.
- The (campaign, subscriber) unique pair makes snapshotting idempotent, so
  an API pre-snapshot plus the worker task's own snapshot never duplicates
  recipient rows, and a ``failed`` campaign can be re-sent safely.
- Sending is chunked (``SEND_BATCH_SIZE`` rows per pass) so a large list
  cannot turn one task into one unbounded SMTP burst.
"""

from __future__ import annotations

import html
import re
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from urllib.parse import quote

import structlog
from sqlalchemy import select

from app.core.exceptions.handlers import NotFoundError, ValidationError
from app.modules.newsletter.domain.models import (
    CampaignStatus,
    NewsletterCampaign,
    NewsletterCampaignRecipient,
    NewsletterStatus,
    NewsletterSubscriber,
    RecipientStatus,
)
from app.modules.notifications.application.email_service import send_email

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# Recipients are processed in passes of this size: query a page of pending
# rows, send them, flush, repeat. Bounds memory and gives the DB a natural
# checkpoint between batches (the task commits per pass).
SEND_BATCH_SIZE = 50

# Substitution token an admin may place anywhere in body_html / body_text;
# it is replaced with the recipient's personal one-click unsubscribe link.
UNSUBSCRIBE_TOKEN = "{{unsubscribe_url}}"

_BODY_SHELL = (
    '<!DOCTYPE html><html lang="fa" dir="rtl"><head><meta charset="utf-8">'
    '<meta name="viewport" content="width=device-width, initial-scale=1">'
    "</head><body style=\"margin:0;padding:0;background:#f4f5f7;"
    'font-family:Tahoma,Arial,sans-serif;">'
    '<div style="max-width:600px;margin:24px auto;background:#fff;'
    'border-radius:12px;border:1px solid #e5e7eb;padding:24px;'
    'color:#111827;line-height:1.8">__PREHEADER____BODY__'
    '<div style="margin-top:24px;padding-top:12px;border-top:1px solid #e5e7eb;'
    'font-size:12px;color:#6b7280">'
    '<a href="__UNSUBSCRIBE_URL__">لغو عضویت در خبرنامه</a>'
    "</div></div></body></html>"
)

_FOOTER_TEXT = (
    "\n\n—————\nبرای لغو عضویت در خبرنامه به این نشانی بروید:\n{unsubscribe_url}"
)


def _utcnow() -> datetime:
    return datetime.now(UTC)


async def _base_url(db: AsyncSession) -> str:
    """Public base URL for links inside emails (same source as confirm mails)."""
    from app.modules.newsletter.application.newsletter_service import _base_url as _svc_base

    return await _svc_base(db)


def _unsubscribe_url(base: str, email: str) -> str:
    """One-click unsubscribe link carrying the (token, email) pair.

    The token is the deterministic HMAC of the address (same scheme as the
    confirm mails) so only genuine campaign emails can unsubscribe an
    address. The address travels in the link it was sent to — no probing
    surface.
    """
    from app.modules.newsletter.application.newsletter_service import token_for_email

    return f"{base}/newsletter/unsubscribe?token={token_for_email(email)}&email={quote(email)}"


def render_email(
    campaign: NewsletterCampaign,
    *,
    unsubscribe_url: str,
) -> tuple[str, str]:
    """Render the campaign into (html, text) for ONE recipient.

    ``{{unsubscribe_url}}`` inside the stored bodies is substituted first,
    and an unsubscribe footer is always appended — a campaign email without
    a working opt-out is never sent, regardless of what the admin typed.
    """
    preheader_html = (
        '<div style="display:none;max-height:0;overflow:hidden">'
        f"{html.escape(campaign.preheader)}</div>"
        if campaign.preheader
        else ""
    )
    body_html = campaign.body_html.replace(UNSUBSCRIBE_TOKEN, unsubscribe_url)
    body_html = (
        _BODY_SHELL.replace("__PREHEADER__", preheader_html)
        .replace("__BODY__", body_html)
        .replace("__UNSUBSCRIBE_URL__", unsubscribe_url)
    )

    if campaign.body_text:
        body_text = campaign.body_text
    else:
        # Cheap tag-strip fallback: the text part is a deliverability aid,
        # not a rendering surface.
        body_text = re.sub(r"<[^>]+>", " ", campaign.body_html)
        body_text = re.sub(r"\s+", " ", body_text).strip()
    body_text = body_text.replace(UNSUBSCRIBE_TOKEN, unsubscribe_url)
    body_text += _FOOTER_TEXT.format(unsubscribe_url=unsubscribe_url)
    return body_html, body_text


# ── CRUD ──────────────────────────────────────────────────────────────────


async def create_campaign(
    db: AsyncSession,
    *,
    name: str,
    subject: str,
    body_html: str,
    body_text: str | None = None,
    preheader: str | None = None,
    created_by: uuid.UUID | None = None,
) -> NewsletterCampaign:
    campaign = NewsletterCampaign(
        name=name[:200],
        subject=subject[:255],
        preheader=preheader[:255] if preheader is not None else None,
        body_html=body_html,
        body_text=body_text,
        created_by=created_by,
    )
    db.add(campaign)
    await db.flush()
    await logger.ainfo("newsletter_campaign_created", campaign_id=str(campaign.id))
    return campaign


async def get_campaign(db: AsyncSession, campaign_id: uuid.UUID) -> NewsletterCampaign:
    campaign = await db.get(NewsletterCampaign, campaign_id)
    if campaign is None:
        raise NotFoundError(resource="Campaign")
    return campaign


async def update_campaign(
    db: AsyncSession,
    campaign_id: uuid.UUID,
    *,
    name: str | None = None,
    subject: str | None = None,
    preheader: str | None = None,
    body_html: str | None = None,
    body_text: str | None = None,
) -> NewsletterCampaign:
    """Patch a draft. Scheduled campaigns must be un-scheduled conceptually:
    only ``scheduled_at`` moves (via :func:`schedule_campaign`), content is
    frozen once the send is queued."""
    campaign = await get_campaign(db, campaign_id)
    if campaign.status != CampaignStatus.DRAFT:
        raise ValidationError(detail="فقط کمپین‌های پیش‌نویس قابل ویرایش هستند.")
    if name is not None:
        campaign.name = name[:200]
    if subject is not None:
        campaign.subject = subject[:255]
    if preheader is not None:
        campaign.preheader = preheader[:255] if preheader else None
    if body_html is not None:
        campaign.body_html = body_html
    if body_text is not None:
        campaign.body_text = body_text
    await db.flush()
    return campaign


async def delete_campaign(db: AsyncSession, campaign_id: uuid.UUID) -> None:
    """Delete a draft or a failed campaign (and its recipient rows)."""
    campaign = await get_campaign(db, campaign_id)
    if campaign.status in (CampaignStatus.SENDING, CampaignStatus.SENT):
        raise ValidationError(detail="کمپین در حال ارسال یا ارسال‌شده قابل حذف نیست.")
    recipients = await _recipients_for_campaign(db, campaign.id)
    for recipient in recipients:
        await db.delete(recipient)
    await db.delete(campaign)
    await db.flush()
    await logger.ainfo("newsletter_campaign_deleted", campaign_id=str(campaign_id))


async def list_campaigns(
    db: AsyncSession,
    *,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[NewsletterCampaign], int]:
    """Newest-first page of campaigns.

    Campaign rows are authored objects — a table of dozens, not millions —
    so paging happens over one fetched list instead of a COUNT round-trip.
    """
    stmt = select(NewsletterCampaign).order_by(NewsletterCampaign.created_at.desc())
    campaigns = list((await db.execute(stmt)).scalars().all())
    total = len(campaigns)
    offset = (page - 1) * page_size
    return campaigns[offset : offset + page_size], total


# ── Recipient snapshot ────────────────────────────────────────────────────


async def _recipients_for_campaign(
    db: AsyncSession, campaign_id: uuid.UUID
) -> list[NewsletterCampaignRecipient]:
    stmt = select(NewsletterCampaignRecipient).where(
        NewsletterCampaignRecipient.campaign_id == campaign_id
    )
    return list((await db.execute(stmt)).scalars().all())


async def list_recipients(
    db: AsyncSession,
    campaign_id: uuid.UUID,
    *,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[NewsletterCampaignRecipient], int]:
    """Stable page of a campaign's recipient rows (address-ordered)."""
    stmt = select(NewsletterCampaignRecipient).where(
        NewsletterCampaignRecipient.campaign_id == campaign_id
    )
    recipients = sorted(
        (await db.execute(stmt)).scalars().all(),
        key=lambda r: r.subscriber_id,
    )
    total = len(recipients)
    offset = (page - 1) * page_size
    return recipients[offset : offset + page_size], total


async def snapshot_recipients(db: AsyncSession, campaign: NewsletterCampaign) -> int:
    """Create pending recipient rows for every confirmed subscriber.

    Idempotent: rows already present (from an earlier attempt or a pre-send
    API snapshot) are kept, never duplicated. Returns the campaign's total
    recipient count.
    """
    confirmed_stmt = select(NewsletterSubscriber).where(
        NewsletterSubscriber.status == NewsletterStatus.SUBSCRIBED
    )
    confirmed = list((await db.execute(confirmed_stmt)).scalars().all())

    existing = {r.subscriber_id for r in await _recipients_for_campaign(db, campaign.id)}
    for subscriber in confirmed:
        if subscriber.email in existing:
            continue
        db.add(
            NewsletterCampaignRecipient(
                campaign_id=campaign.id,
                subscriber_id=subscriber.email,
            )
        )
    await db.flush()

    return len(await _recipients_for_campaign(db, campaign.id))


# ── Preview / test send ───────────────────────────────────────────────────


async def preview_campaign(
    db: AsyncSession, campaign: NewsletterCampaign
) -> tuple[str, str, str]:
    """(subject, html, text) rendered with a sample unsubscribe link.

    The sample address is not a real member; the token authenticates only
    itself, so preview mails cannot unsubscribe anyone else.
    """
    base = await _base_url(db)
    url = _unsubscribe_url(base, "preview@example.com")
    html_body, text_body = render_email(campaign, unsubscribe_url=url)
    return campaign.subject, html_body, text_body


async def send_test_email(
    db: AsyncSession, campaign: NewsletterCampaign, *, email: str
) -> bool:
    """Send the rendered campaign to one arbitrary address; no recipient rows."""
    base = await _base_url(db)
    html_body, text_body = render_email(
        campaign, unsubscribe_url=_unsubscribe_url(base, email)
    )
    success, _ = await send_email(
        db,
        recipient=email,
        subject=campaign.subject,
        html_body=html_body,
        text_body=text_body,
        template="newsletter_campaign_test",
    )
    await logger.ainfo(
        "newsletter_campaign_test_sent", campaign_id=str(campaign.id), success=success
    )
    return success


# ── Scheduling / dispatch ─────────────────────────────────────────────────


def enqueue_send(campaign_id: uuid.UUID, *, eta: datetime | None = None) -> bool:
    """Hand the campaign to Celery (best-effort).

    The beat sweep (:func:`dispatch_due_scheduled`) is the safety net, so a
    broker hiccup here degrades to "sent by the next beat tick" rather than
    a failed admin action.
    """
    try:
        from app.modules.newsletter.application.tasks import send_newsletter_campaign

        if eta is not None:
            send_newsletter_campaign.apply_async(args=[str(campaign_id)], eta=eta)
        else:
            send_newsletter_campaign.apply_async(args=[str(campaign_id)])
        return True
    except Exception as exc:
        logger.warning(
            "newsletter_campaign_enqueue_failed",
            campaign_id=str(campaign_id),
            eta=eta.isoformat() if eta else None,
            error=str(exc),
        )
        return False


async def schedule_campaign(
    db: AsyncSession, campaign_id: uuid.UUID, *, scheduled_at: datetime
) -> NewsletterCampaign:
    """Queue a draft (or re-time a scheduled) campaign for a future send."""
    campaign = await get_campaign(db, campaign_id)
    if campaign.status in (CampaignStatus.SENDING, CampaignStatus.SENT):
        raise ValidationError(detail="کمپین در حال ارسال یا ارسال‌شده قابل زمان‌بندی نیست.")
    campaign.status = CampaignStatus.SCHEDULED
    campaign.scheduled_at = scheduled_at
    await db.flush()
    enqueue_send(campaign.id, eta=scheduled_at)
    await logger.ainfo(
        "newsletter_campaign_scheduled",
        campaign_id=str(campaign.id),
        scheduled_at=scheduled_at.isoformat(),
    )
    return campaign


async def dispatch_due_scheduled(
    db: AsyncSession, *, now: datetime | None = None
) -> int:
    """Beat sweep: enqueue every scheduled campaign whose time has come.

    Only enqueues — the task itself flips the status, so a late or repeated
    tick cannot double-send (the send guard rejects non-draft/scheduled).
    """
    now = now or _utcnow()
    stmt = select(NewsletterCampaign).where(
        NewsletterCampaign.status == CampaignStatus.SCHEDULED
    )
    due = [
        c
        for c in (await db.execute(stmt)).scalars().all()
        if c.scheduled_at is not None and c.scheduled_at <= now
    ]
    for campaign in due:
        enqueue_send(campaign.id)
    if due:
        await logger.ainfo(
            "newsletter_campaigns_dispatched", count=len(due)
        )
    return len(due)


# ── The send itself ───────────────────────────────────────────────────────


async def send_campaign(
    db: AsyncSession,
    campaign_id: uuid.UUID,
    *,
    batch_size: int = SEND_BATCH_SIZE,
    commit_between_batches: bool = False,
) -> dict[str, object]:
    """Send a draft/scheduled/failed campaign to the confirmed list.

    Returns a counters dict for the caller (task result / API response).
    Raises ``ValidationError`` when the campaign is already sending/sent or
    has no confirmed recipients — both are caught by the Celery task and
    reported as ``skipped`` instead of retried.
    """
    campaign = await db.get(NewsletterCampaign, campaign_id)
    if campaign is None:
        raise NotFoundError(resource="Campaign")
    if campaign.status in (CampaignStatus.SENDING, CampaignStatus.SENT):
        raise ValidationError(detail="این کمپین قبلاً ارسال شده است.")

    campaign.status = CampaignStatus.SENDING
    campaign.total_recipients = await snapshot_recipients(db, campaign)
    if campaign.total_recipients == 0:
        await db.flush()
        raise ValidationError(detail="هیچ عضو تأییدشده‌ای برای ارسال وجود ندارد.")

    # A failed attempt is retryable: previous failures go back to pending so
    # the re-run covers them (sent rows stay sent — nobody gets mail twice).
    stmt_failed = select(NewsletterCampaignRecipient).where(
        NewsletterCampaignRecipient.campaign_id == campaign.id,
        NewsletterCampaignRecipient.status == RecipientStatus.FAILED,
    )
    for recipient in (await db.execute(stmt_failed)).scalars().all():
        recipient.status = RecipientStatus.PENDING
        recipient.error = None
        recipient.sent_at = None
    campaign.total_sent = 0
    campaign.total_failed = 0
    await db.flush()

    base = await _base_url(db)

    while True:
        stmt = (
            select(NewsletterCampaignRecipient)
            .where(
                NewsletterCampaignRecipient.campaign_id == campaign.id,
                NewsletterCampaignRecipient.status == RecipientStatus.PENDING,
            )
            .order_by(NewsletterCampaignRecipient.subscriber_id)
            .limit(batch_size)
        )
        batch = list((await db.execute(stmt)).scalars().all())
        if not batch:
            break

        for recipient in batch:
            # Honour unsubscribes mid-send: the row may be pending while the
            # member has opted out since the snapshot (another process, or an
            # earlier batch of this very campaign). Re-read the subscriber.
            fresh_stmt = (
                select(NewsletterSubscriber)
                .where(NewsletterSubscriber.email == recipient.subscriber_id)
                .execution_options(populate_existing=True)
            )
            subscriber = (await db.execute(fresh_stmt)).scalars().first()
            if subscriber is None or subscriber.status != NewsletterStatus.SUBSCRIBED:
                # No longer a member → not a recipient. Drop the row and the
                # count instead of recording a fake failure.
                await db.delete(recipient)
                campaign.total_recipients = max(0, campaign.total_recipients - 1)
                continue

            html_body, text_body = render_email(
                campaign,
                unsubscribe_url=_unsubscribe_url(base, recipient.subscriber_id),
            )
            try:
                ok, log_row = await send_email(
                    db,
                    recipient=recipient.subscriber_id,
                    subject=campaign.subject,
                    html_body=html_body,
                    text_body=text_body,
                    template="newsletter_campaign",
                )
            except Exception as exc:  # one bad address must not kill the batch
                await logger.aexception(
                    "newsletter_campaign_send_unexpected_error",
                    campaign_id=str(campaign.id),
                    recipient=recipient.subscriber_id,
                )
                ok, log_row = False, None
                recipient.error = f"{type(exc).__name__}: {exc}"[:2000]
            if ok:
                recipient.status = RecipientStatus.SENT
                recipient.sent_at = _utcnow()
                recipient.error = None
                campaign.total_sent += 1
            else:
                recipient.status = RecipientStatus.FAILED
                if log_row is not None and log_row.error:
                    recipient.error = log_row.error[:2000]
                campaign.total_failed += 1

        await db.flush()
        if commit_between_batches:
            await db.commit()

    campaign.sent_at = _utcnow()
    # All transports failed → surface as a failed campaign (retryable);
    # otherwise the campaign is done.
    campaign.status = (
        CampaignStatus.FAILED
        if campaign.total_sent == 0 and campaign.total_failed > 0
        else CampaignStatus.SENT
    )
    await db.flush()
    if commit_between_batches:
        await db.commit()

    await logger.ainfo(
        "newsletter_campaign_sent",
        campaign_id=str(campaign.id),
        total_recipients=campaign.total_recipients,
        total_sent=campaign.total_sent,
        total_failed=campaign.total_failed,
        status=str(campaign.status),
    )
    return {
        "id": str(campaign.id),
        # `.value`, not str(): the campaigns tab compares this against
        # "draft"/"scheduled"/"failed", which str(enum) never matches.
        "status": campaign.status.value,
        "total_recipients": campaign.total_recipients,
        "total_sent": campaign.total_sent,
        "total_failed": campaign.total_failed,
    }
