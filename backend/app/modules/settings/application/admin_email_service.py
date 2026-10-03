"""Change the site's admin email the way WordPress does: propose, confirm, review.

P1 "کاربران: تغییر ایمیل مدیریتی با تأییدیه و بازبینی دوره‌ای". The admin
address is where password resets, order alerts and the store's own notices
arrive — a typo silently swallows all of them, and whoever controls the
mailbox controls the account. WordPress solves this with two mechanisms this
module mirrors:

* ``new_admin_email`` — a *proposed* address that only becomes ``admin_email``
  after a confirmation link sent to the new address is clicked. Until then the
  old address stays in force, so a mistaken edit cannot redirect the store's
  mail;
* ``admin_email_check_interval`` — a periodic "is this address still correct?"
  review, so a working-but-abandoned address (a departed employee's inbox)
  does not stay the recovery channel for years.

State lives in site options, exactly like WordPress — no table, no migration.
The token is derived from the address plus a secret, stored hashed; it is
single-use in the useful direction (a second click reports "already confirmed"
rather than re-applying).
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import structlog

from app.core.config.settings import get_settings
from app.modules.settings.application.site_options_service import SiteOptionsService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

settings = get_settings()

ADMIN_EMAIL_OPTION = "admin_email"
PENDING_ADMIN_EMAIL_OPTION = "new_admin_email"
#: Hash of the token that confirms the pending address. The plaintext only
#: ever exists in the confirmation email.
PENDING_TOKEN_HASH_OPTION = "new_admin_email_token_hash"
PENDING_REQUESTED_AT_OPTION = "new_admin_email_requested_at"
#: When the current address was last confirmed (by a change or a review).
ADMIN_EMAIL_CONFIRMED_AT_OPTION = "admin_email_confirmed_at"

#: WordPress's default review cadence is six months. The value is a number of
#: days so the settings screen can edit it as one field.
DEFAULT_REVIEW_INTERVAL_DAYS = 180

#: How long a confirmation link stays usable.
ADMIN_EMAIL_CONFIRM_TTL_HOURS = 24


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def normalize_email(raw: str | None) -> str | None:
    """Lower-cased, trimmed address, or None when unusable."""
    if raw is None:
        return None
    candidate = raw.strip().lower()
    return candidate or None


def _confirmation_link(token: str) -> str:
    # The admin is the one who clicks, and the settings screen is where they
    # are when they request the change — so the link lands there. Being signed
    # in as an admin is required to redeem, which is WordPress's behaviour too:
    # the token proves the address, the session proves the operator.
    return (
        f"{settings.STOREFRONT_BASE_URL.rstrip('/')}"
        f"/admin/settings?admin_email_token={token}"
    )


async def request_admin_email_change(
    db: AsyncSession,
    *,
    new_email: str,
    requested_by: str | None = None,
) -> dict[str, Any]:
    """Record a proposed admin address and email a confirmation link to it.

    The current ``admin_email`` is untouched. Returns what happened rather
    than raising on a mail failure — the proposal is already stored and can be
    re-sent.
    """
    target = normalize_email(new_email)
    if not target or "@" not in target or "." not in target.split("@")[-1]:
        return {"status": "invalid", "message": "نشانی ایمیل معتبر نیست."}

    current = normalize_email(await SiteOptionsService.get(db, ADMIN_EMAIL_OPTION))
    if current == target:
        return {"status": "unchanged", "message": "این همان ایمیل مدیریت فعلی است."}

    token = secrets.token_urlsafe(48)
    now = datetime.now(UTC)
    await SiteOptionsService.set(db, PENDING_ADMIN_EMAIL_OPTION, target)
    await SiteOptionsService.set(db, PENDING_TOKEN_HASH_OPTION, _hash_token(token))
    await SiteOptionsService.set(db, PENDING_REQUESTED_AT_OPTION, now.isoformat())

    sent = False
    try:
        from app.modules.notifications.application.email_service import send_email

        link = _confirmation_link(token)
        sent, _log = await send_email(
            db,
            recipient=target,
            subject="تأیید ایمیل مدیریت سایت",
            html_body=(
                '<div dir="rtl" style="font-family:Tahoma,sans-serif">'
                "<p>درخواست تغییر ایمیل مدیریت سایت به این نشانی ثبت شده است.</p>"
                "<p>برای تأیید، روی پیوند زیر کلیک کنید:</p>"
                f'<p><a href="{link}">{link}</a></p>'
                f"<p>این پیوند تا {ADMIN_EMAIL_CONFIRM_TTL_HOURS} ساعت معتبر است. "
                "تا پیش از تأیید، ایمیل مدیریت فعلی تغییری نمی‌کند. "
                "اگر شما این درخواست را نداده‌اید، این ایمیل را نادیده بگیرید.</p>"
                "</div>"
            ),
            text_body=(
                "درخواست تغییر ایمیل مدیریت سایت به این نشانی ثبت شده است.\n\n"
                f"{link}\n\n"
                f"این پیوند تا {ADMIN_EMAIL_CONFIRM_TTL_HOURS} ساعت معتبر است."
            ),
        )
        sent = bool(sent)
    except Exception:  # noqa: BLE001 — a mail outage must not lose the proposal
        logger.exception("admin_email_confirmation_send_failed", target=target)

    logger.info(
        "admin_email_change_requested",
        target=target,
        requested_by=requested_by,
        sent=sent,
    )
    return {
        "status": "pending",
        "message": (
            "پیوند تأیید به نشانی جدید فرستاده شد. تا کلیک روی پیوند، ایمیل فعلی تغییر نمی‌کند."
            if sent
            else "درخواست ثبت شد، ولی ارسال ایمیل ناموفق بود. لطفاً کمی بعد دوباره تلاش کنید."
        ),
        "email_sent": sent,
        "expires_in_hours": ADMIN_EMAIL_CONFIRM_TTL_HOURS,
    }


async def confirm_admin_email_change(
    db: AsyncSession,
    *,
    token: str,
    actor_id: str | None = None,
) -> dict[str, Any]:
    """Redeem the confirmation token and move ``admin_email``."""
    supplied = (token or "").strip()
    if not supplied:
        return {"status": "invalid", "message": "توکن تأیید ارسال نشده است."}

    stored_hash = await SiteOptionsService.get(db, PENDING_TOKEN_HASH_OPTION)
    pending = normalize_email(await SiteOptionsService.get(db, PENDING_ADMIN_EMAIL_OPTION))
    requested_at_raw = await SiteOptionsService.get(db, PENDING_REQUESTED_AT_OPTION)

    if not stored_hash or not pending:
        return {"status": "no_pending", "message": "درخواست تغییر ایمیل در انتظاری وجود ندارد."}

    if stored_hash != _hash_token(supplied):
        return {"status": "invalid_token", "message": "لینک تأیید معتبر نیست."}

    # Expiry is derived from the recorded request time rather than stored as a
    # separate deadline: two fields that must agree are one field too many.
    if requested_at_raw:
        try:
            requested_at = datetime.fromisoformat(requested_at_raw)
        except ValueError:
            requested_at = None
        if requested_at is not None:
            if requested_at.tzinfo is None:
                requested_at = requested_at.replace(tzinfo=UTC)
            if datetime.now(UTC) - requested_at > timedelta(hours=ADMIN_EMAIL_CONFIRM_TTL_HOURS):
                return {
                    "status": "expired",
                    "message": "مهلت این لینک به پایان رسیده است. لطفاً دوباره درخواست دهید.",
                }

    await SiteOptionsService.set(db, ADMIN_EMAIL_OPTION, pending)
    await SiteOptionsService.set(db, ADMIN_EMAIL_CONFIRMED_AT_OPTION, datetime.now(UTC).isoformat())
    # Consumed: clearing the pending state is what makes a second click report
    # "no pending request" instead of re-applying an old proposal.
    await SiteOptionsService.set(db, PENDING_ADMIN_EMAIL_OPTION, None)
    await SiteOptionsService.set(db, PENDING_TOKEN_HASH_OPTION, None)
    await SiteOptionsService.set(db, PENDING_REQUESTED_AT_OPTION, None)

    logger.info("admin_email_changed", new_email=pending, actor_id=actor_id)
    return {"status": "confirmed", "email": pending}


async def get_admin_email_status(db: AsyncSession) -> dict[str, Any]:
    """Everything the settings card and the review notice need."""
    current = await SiteOptionsService.get(db, ADMIN_EMAIL_OPTION)
    pending = await SiteOptionsService.get(db, PENDING_ADMIN_EMAIL_OPTION)
    requested_at_raw = await SiteOptionsService.get(db, PENDING_REQUESTED_AT_OPTION)
    confirmed_at_raw = await SiteOptionsService.get(db, ADMIN_EMAIL_CONFIRMED_AT_OPTION)

    interval_days = await SiteOptionsService.get_int(
        db, "admin_email_check_interval", DEFAULT_REVIEW_INTERVAL_DAYS, minimum=1
    )

    # "Needs review" is a real question the operator should see: an address
    # that was confirmed long ago (or never recorded as confirmed) may belong
    # to somebody who left. Never-confirmed counts as overdue — the seed value
    # is a placeholder nobody has proven they receive mail at.
    needs_review = False
    due_since: str | None = None
    now = datetime.now(UTC)
    if confirmed_at_raw:
        try:
            confirmed_at = datetime.fromisoformat(confirmed_at_raw)
            if confirmed_at.tzinfo is None:
                confirmed_at = confirmed_at.replace(tzinfo=UTC)
            needs_review = (now - confirmed_at) > timedelta(days=interval_days)
            due_since = confirmed_at.isoformat()
        except ValueError:
            needs_review = True
    else:
        needs_review = True

    return {
        "admin_email": current,
        "pending_email": pending,
        "pending_requested_at": requested_at_raw,
        "confirmed_at": confirmed_at_raw,
        "review_interval_days": interval_days,
        "needs_review": needs_review,
        "due_since": due_since,
    }


async def confirm_current_admin_email(
    db: AsyncSession,
    *,
    actor_id: str | None = None,
) -> dict[str, Any]:
    """The periodic review's "yes, this address is still correct" button.

    Records a fresh confirmation timestamp; changes nothing else. Without
    this, the only way to clear the review notice would be to change the
    address, which is not what "still correct" means.
    """
    current = await SiteOptionsService.get(db, ADMIN_EMAIL_OPTION)
    if not current:
        return {"status": "no_email", "message": "ایمیلی برای تأیید ثبت نشده است."}
    await SiteOptionsService.set(db, ADMIN_EMAIL_CONFIRMED_AT_OPTION, datetime.now(UTC).isoformat())
    logger.info("admin_email_reviewed", admin_email=current, actor_id=actor_id)
    return {"status": "confirmed", "email": current}