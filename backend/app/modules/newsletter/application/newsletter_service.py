"""Newsletter service — double opt-in subscription lifecycle.

WordPress has no newsletter entity in core; this fills that gap with a
confirm-first flow: an address only becomes mailable after the owner clicks
the emailed link. Responses are deliberately uniform so the public endpoint
cannot be used to probe which addresses exist.

Tokens are deterministic: ``base64url(HMAC-SHA256(server_secret, email))``.
The link carries ``(token, email)`` and the pair is accepted only when the
MAC recomputes exactly, so a leaked address list alone cannot confirm or
unsubscribe anyone. Rows are fetched by primary key (the address itself) —
one lookup per request, no secondary queries.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import structlog

from app.core.exceptions.handlers import NotFoundError, ValidationError
from app.modules.newsletter.domain.models import NewsletterStatus, NewsletterSubscriber

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger()

# Resending a confirmation email to a still-pending address is throttled so
# the endpoint cannot be turned into a mail-bombing loop against a victim's
# inbox. Updated_at is refreshed on every subscribe attempt, which makes it
# a natural "last attempt" marker.
CONFIRM_RESEND_THROTTLE = timedelta(minutes=1)

GENERIC_SUBSCRIBE_MESSAGE = (
    "اگر ایمیل واردشده معتبر باشد، لینک تأیید عضویت برایتان ارسال شد. "
    "پس از کلیک روی لینک، عضویت شما نهایی می‌شود."
)

_CONFIRM_EMAIL_SUBJECT = "تأیید عضویت در خبرنامه"

# Domain separation for the token MAC so the same secret never authenticates
# newsletter tokens as anything else.
_TOKEN_DOMAIN = b"newsletter:confirm:v1"


def token_for_email(email: str) -> str:
    """Deterministic, URL-safe confirm/unsubscribe token for one address."""
    digest = hmac.new(_token_secret(), _TOKEN_DOMAIN + email.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def _token_secret() -> bytes:
    """Server-side secret for the token MAC (never leaves the process)."""
    from app.core.config.settings import get_settings

    secret = get_settings().JWT_SECRET_KEY
    if not secret:
        # Without a provisioned secret, confirmation links cannot be secured —
        # fail loudly instead of issuing forgeable tokens.
        raise ValidationError(detail="توکن تأیید در دسترس نیست؛ تنظیمات سرور ناقص است.")
    return secret.encode()


def _resolve_token(email: str | None, token: str) -> str | None:
    """Return the address a ``(token, email)`` pair authenticates, or None.

    The MAC is not reversible, so the emailed link carries both values and
    the pair is accepted only when the token recomputes exactly.
    Constant-time comparison keeps token guessing off the timing wire.
    """
    if not email:
        return None
    expected = token_for_email(email)
    if not hmac.compare_digest(expected, token or ""):
        return None
    return email


def _normalize_email(email: str) -> str:
    normalized = email.strip().lower()
    if "@" not in normalized:
        raise ValidationError(detail="ایمیل معتبر نیست.")
    return normalized


async def _base_url(db: AsyncSession) -> str:
    """Public base URL for links inside emails, from the ``home`` option."""
    from app.modules.settings.application.site_options_service import SiteOptionsService

    home = await SiteOptionsService.get(db, "home")
    if home:
        return str(home).rstrip("/")
    return "http://localhost:3000"


_BUTTON_STYLE = (
    "display:inline-block;padding:10px 22px;background:#0f766e;"
    "color:#fff;border-radius:8px;text-decoration:none"
)
_NOTE_STYLE = "font-size:12px;color:#666"


def _confirm_email_bodies(confirm_url: str, unsubscribe_url: str) -> tuple[str, str]:
    html_body = f"""<div dir="rtl" style="font-family:Tahoma,Arial,sans-serif;line-height:1.8">
<p>سلام،</p>
<p>برای نهایی‌کردن عضویت در خبرنامه، روی دکمه‌ی زیر کلیک کنید:</p>
<p><a href="{confirm_url}" style="{_BUTTON_STYLE}">تأیید عضویت</a></p>
<p style="{_NOTE_STYLE}">اگر شما این درخواست را نداده‌اید، این ایمیل را نادیده بگیرید.</p>
<p style="{_NOTE_STYLE}"><a href="{unsubscribe_url}">لغو عضویت</a></p>
</div>"""
    text_body = (
        "برای نهایی‌کردن عضویت در خبرنامه به آدرس زیر بروید:\n"
        f"{confirm_url}\n\n"
        "اگر شما این درخواست را نداده‌اید، این ایمیل را نادیده بگیرید."
    )
    return html_body, text_body


async def _send_confirmation_email(
    db: AsyncSession, subscriber: NewsletterSubscriber
) -> bool:
    from app.modules.notifications.application.email_service import send_email

    base = await _base_url(db)
    confirm_url = f"{base}/newsletter/confirm?token={subscriber.confirm_token}"
    unsubscribe_url = f"{base}/newsletter/unsubscribe?token={subscriber.confirm_token}"
    html_body, text_body = _confirm_email_bodies(confirm_url, unsubscribe_url)

    success, _ = await send_email(
        db,
        recipient=subscriber.email,
        subject=_CONFIRM_EMAIL_SUBJECT,
        html_body=html_body,
        text_body=text_body,
        template="newsletter_confirm",
    )
    if not success:
        await logger.awarning(
            "newsletter_confirm_email_failed", subscriber_id=str(subscriber.id)
        )
    return success


# ── Public lifecycle ──────────────────────────────────────────────────────


async def subscribe(
    db: AsyncSession,
    *,
    email: str,
    source: str | None = None,
) -> tuple[NewsletterSubscriber, bool]:
    """Record a signup request and email the confirm link.

    Idempotent and enumeration-safe: an already-subscribed address is
    returned without emailing, a pending address gets a throttled resend,
    and an unsubscribed one re-enters the confirm flow.
    Returns ``(subscriber, emailed)``.
    """
    normalized = _normalize_email(email)
    subscriber = await db.get(NewsletterSubscriber, normalized)

    if subscriber is not None and subscriber.status == NewsletterStatus.SUBSCRIBED:
        return subscriber, False

    token = token_for_email(normalized)
    if subscriber is None:
        subscriber = NewsletterSubscriber(
            email=normalized,
            status=NewsletterStatus.PENDING,
            confirm_token=token,
            source=(source or "footer")[:50],
        )
        db.add(subscriber)
    else:
        # Pending or previously unsubscribed: back to pending.
        subscriber.confirm_token = token
        subscriber.status = NewsletterStatus.PENDING
        subscriber.unsubscribed_at = None
        if source:
            subscriber.source = source[:50]
        last_attempt = subscriber.updated_at
        if (
            last_attempt is not None
            and datetime.now(UTC) - last_attempt < CONFIRM_RESEND_THROTTLE
        ):
            await db.flush()
            return subscriber, False

    await db.flush()
    emailed = await _send_confirmation_email(db, subscriber)
    await logger.ainfo(
        "newsletter_subscribed",
        subscriber_id=subscriber.email,
        status=str(subscriber.status),
        emailed=emailed,
    )
    return subscriber, emailed


async def confirm(db: AsyncSession, *, email: str, token: str) -> NewsletterSubscriber:
    """Finalize a pending subscription with the emailed token+address pair."""
    address = _resolve_token(email, token)
    if address is None:
        raise NotFoundError(resource="Subscription", detail="لینک تأیید نامعتبر است.")
    subscriber = await db.get(NewsletterSubscriber, address)
    if subscriber is None:
        raise NotFoundError(resource="Subscription", detail="لینک تأیید نامعتبر است.")
    if subscriber.status == NewsletterStatus.SUBSCRIBED:
        return subscriber

    subscriber.status = NewsletterStatus.SUBSCRIBED
    subscriber.confirmed_at = datetime.now(UTC)
    await db.flush()

    await logger.ainfo("newsletter_confirmed", subscriber_id=subscriber.email)
    return subscriber


async def unsubscribe(db: AsyncSession, *, email: str, token: str) -> NewsletterSubscriber:
    """Opt an address out via the one-click link from any campaign email."""
    address = _resolve_token(email, token)
    if address is None:
        raise NotFoundError(resource="Subscription", detail="لینک لغو عضویت نامعتبر است.")
    subscriber = await db.get(NewsletterSubscriber, address)
    if subscriber is None:
        raise NotFoundError(resource="Subscription", detail="لینک لغو عضویت نامعتبر است.")
    if subscriber.status == NewsletterStatus.UNSUBSCRIBED:
        return subscriber

    subscriber.status = NewsletterStatus.UNSUBSCRIBED
    subscriber.unsubscribed_at = datetime.now(UTC)
    await db.flush()

    await logger.ainfo("newsletter_unsubscribed", subscriber_id=subscriber.email)
    return subscriber


async def admin_delete_subscriber(
    db: AsyncSession,
    *,
    email: str,
    actor_id: uuid.UUID,
) -> None:
    """Hard-delete one subscriber row (GDPR erasure on the list)."""
    from app.modules.audit.application.audit_service import log_action

    subscriber = await db.get(NewsletterSubscriber, email)
    if subscriber is None:
        raise NotFoundError(resource="Subscriber")

    await db.delete(subscriber)
    await db.flush()

    await log_action(
        db,
        actor_id=actor_id,
        action="newsletter.subscriber_deleted",
        resource="newsletter_subscriber",
        resource_id=email,
        before={"email": email},
    )
    await logger.ainfo("newsletter_subscriber_deleted", subscriber_id=email)
