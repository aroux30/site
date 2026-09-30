"""Two-step email changes: the address moves only after it is confirmed.

The profile endpoint used to write the new address straight to ``User.email``.
Because a password reset is delivered by email, that made the field an account
takeover: point the account at an address you control, then trigger a reset.

The fix is WordPress's: the new address is *proposed*, and only becomes the
account's address once the owner proves they receive mail there. Until then
``User.email`` is untouched, so a reset issued in the meantime still goes to the
address the account really owns.

Four properties this module is responsible for:

* the token is stored hashed, so a database leak cannot be replayed;
* a request expires, and an expired one is refused rather than silently
  accepted;
* redeeming is idempotent-ish in the useful direction — a spent token reports
  "already used" instead of applying the change twice;
* a request is invalidated when the account's address has moved since it was
  issued, so an old confirmation cannot drag the account backwards.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import select, update

from app.core.config.settings import get_settings
from app.modules.users.domain.models import EmailChangeRequest, User

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

#: Read once, like the auth service does, so the confirmation link is built from
#: the same configuration the reset link uses.
settings = get_settings()

#: WordPress's ``new_admin_email`` flow uses a day; shorter here, matching the
#: password-reset window, because the only cost of a short window is sending a
#: second confirmation.
EMAIL_CHANGE_TTL_MINUTES = 30


def hash_email_change_token(token: str) -> str:
    """SHA-256 of the token. The plaintext only ever exists in the email."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def email_change_link(token: str) -> str:
    return f"{settings.STOREFRONT_BASE_URL.rstrip('/')}/account/profile?email_token={token}"


class EmailChangeError(Exception):
    """Raised when a confirmation cannot be honoured.

    Carries a machine-readable ``code`` so the route can answer 400 with a
    Persian message instead of leaking a raw exception string.
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def normalize_email(raw: str | None) -> str | None:
    """Lower-cased, whitespace-trimmed address, or None when unusable.

    Normalising before the uniqueness check is what stops ``A@b.com`` and
    ``a@b.com`` from being treated as two different accounts. This mirrors the
    existing password-reset path so both flows agree on what an address is.
    """
    if raw is None:
        return None
    candidate = raw.strip().lower()
    return candidate or None


async def request_email_change(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    new_email: str,
    request_ip: str | None = None,
) -> dict[str, Any]:
    """Record a proposal and email a confirmation link. Does not change the address.

    Returns a dict describing what happened rather than raising, so the account
    screen can show "check your inbox" whether or not the address was already
    the account's — the response should not be a way to probe which addresses
    exist on the site.
    """
    target = normalize_email(new_email)
    if not target or "@" not in target:
        raise EmailChangeError("invalid_email", "نشانی ایمیل معتبر نیست.")

    user = await db.get(User, user_id)
    if user is None:
        raise EmailChangeError("not_found", "کاربر یافت نشد.")

    if normalize_email(user.email) == target:
        return {"status": "unchanged", "message": "ایمیل شما همین حالا همین است."}

    taken = await db.execute(select(User.id).where(User.email == target, User.id != user_id))
    if taken.first() is not None:
        raise EmailChangeError("email_taken", "این ایمیل قبلاً برای حساب دیگری ثبت شده است.")

    now = datetime.now(UTC)

    # An earlier request for a different address is void: only the newest
    # proposal can be confirmed, otherwise a user who changes their mind twice
    # could redeem a link from the first attempt.
    await db.execute(
        update(EmailChangeRequest)
        .where(
            EmailChangeRequest.user_id == user_id,
            EmailChangeRequest.used_at.is_(None),
            EmailChangeRequest.invalidated_at.is_(None),
        )
        .values(invalidated_at=now)
    )

    token = secrets.token_urlsafe(48)
    db.add(
        EmailChangeRequest(
            user_id=user_id,
            new_email=target,
            current_email=normalize_email(user.email),
            token_hash=hash_email_change_token(token),
            expires_at=now + timedelta(minutes=EMAIL_CHANGE_TTL_MINUTES),
            request_ip=request_ip,
        )
    )
    await db.commit()

    try:
        from app.modules.notifications.application.email_service import send_email

        confirmation_link = email_change_link(token)
        # ``html_body`` is required by send_email; omitting it raised a
        # TypeError that the bare ``except`` below swallowed, so the
        # confirmation link was never sent for any SMTP configuration.
        # ``send_email`` returns a (success, log_row) tuple, which is always
        # truthy — the previous code used it directly as a bool, so even a real
        # failure would have reported success.
        sent, _log = await send_email(
            db,
            recipient=target,
            subject="تأیید تغییر ایمیل",
            html_body=(
                '<div dir="rtl" style="font-family:Tahoma,sans-serif">'
                "<p>برای تغییر ایمیل حساب خود روی پیوند زیر کلیک کنید:</p>"
                f'<p><a href="{confirmation_link}">{confirmation_link}</a></p>'
                f"<p>این پیوند تا {EMAIL_CHANGE_TTL_MINUTES} دقیقه معتبر است. "
                "تا پیش از تأیید، ایمیل حساب شما تغییری نمی‌کند. "
                "اگر شما این درخواست را نداده‌اید، این ایمیل را نادیده بگیرید.</p>"
                "</div>"
            ),
            text_body=(
                "برای تغییر ایمیل حساب خود روی پیوند زیر کلیک کنید:\n\n"
                f"{confirmation_link}\n\n"
                f"این پیوند تا {EMAIL_CHANGE_TTL_MINUTES} دقیقه معتبر است. "
                "تا پیش از تأیید، ایمیل حساب شما تغییری نمی‌کند. "
                "اگر شما این درخواست را نداده‌اید، این ایمیل را نادیده بگیرید."
            ),
        )
        sent = bool(sent)
    except Exception:  # noqa: BLE001 - a mail outage must not lose the request
        logger.exception("email_change_confirmation_send_failed", user_id=str(user_id))
        sent = False

    # `send_email` already reports success honestly (it returns False and writes
    # a SKIPPED row when SMTP is unconfigured). Propagating that here is the
    # difference between "check your inbox" and "we sent you a link" — with SMTP
    # down, the second is a promise nobody kept, and the user waits for a mail
    # that will never arrive. The request is kept either way, so a retry is
    # possible; only the wording changes.
    return {
        "status": "pending",
        "message": (
            "لینک تأیید به ایمیل جدید فرستاده شد."
            if sent
            else "درخواست ثبت شد، ولی ارسال ایمیل ناموفق بود. لطفاً کمی بعد دوباره تلاش کنید."
        ),
        "email_sent": bool(sent),
        "expires_in_minutes": EMAIL_CHANGE_TTL_MINUTES,
    }


async def confirm_email_change(db: AsyncSession, *, token: str) -> dict[str, Any]:
    """Redeem a confirmation token and move the address.

    Raises :class:`EmailChangeError` for every failure mode rather than
    returning a generic False, because the account screen shows a different
    message for "expired" and "already used" and a shared message would leave
    the user re-clicking a link that can never work.
    """
    now = datetime.now(UTC)
    digest = hash_email_change_token(token)

    result = await db.execute(
        select(EmailChangeRequest).where(EmailChangeRequest.token_hash == digest)
    )
    request_row = result.scalar_one_or_none()
    if request_row is None:
        raise EmailChangeError("invalid_token", "لینک تأیید معتبر نیست.")

    if request_row.used_at is not None:
        raise EmailChangeError("already_used", "این لینک قبلاً استفاده شده است.")

    if request_row.invalidated_at is not None:
        raise EmailChangeError(
            "superseded", "این درخواست با درخواست جدیدتر جایگزین شده است."
        )

    if request_row.expires_at <= now:
        raise EmailChangeError("expired", "مهلت این لینک به پایان رسیده است.")

    user = await db.get(User, request_row.user_id)
    if user is None:
        raise EmailChangeError("not_found", "کاربر یافت نشد.")

    # The account's address moved after this request was issued. Applying it now
    # would drag the account back to an address the owner has since replaced.
    if normalize_email(user.email) != request_row.current_email:
        raise EmailChangeError(
            "stale",
            "ایمیل حساب شما از زمان صدور این درخواست تغییر کرده است. لطفاً دوباره تلاش کنید.",
        )

    conflict = await db.execute(
        select(User.id).where(User.email == request_row.new_email, User.id != user.id)
    )
    if conflict.first() is not None:
        # Someone registered with this address while the request was pending.
        raise EmailChangeError("email_taken", "این ایمیل اکنون برای حساب دیگری ثبت شده است.")

    user.email = request_row.new_email
    request_row.used_at = now
    await db.commit()

    # Tell the address that just *lost* the account. WordPress sends two
    # messages for this flow and the second is the important one: if a stolen
    # session moves the address and confirms it, the previous owner is otherwise
    # the last person unaware. The `stale` check above does not help here — the
    # address it compares has not changed, so the request looks perfectly fresh.
    # No action link on purpose: this notice is evidence, not an undo button.
    if request_row.current_email and request_row.current_email != request_row.new_email:
        try:
            from app.modules.notifications.application.email_service import send_email

            # Same missing ``html_body`` as the confirmation mail — this notice
            # is the one that tells a hijacked account owner their address moved,
            # so it must not be the call that silently fails.
            await send_email(
                db,
                recipient=request_row.current_email,
                subject="ایمیل حساب شما تغییر کرد",
                html_body=(
                    '<div dir="rtl" style="font-family:Tahoma,sans-serif">'
                    "<p>ایمیل حساب شما از این پس "
                    f"{request_row.new_email} است.</p>"
                    "<p>اگر این کار را شما نکرده‌اید، همین حالا با پشتیبانی تماس بگیرید. "
                    "بازنشانی رمز کمکی نمی‌کند: لینک بازنشانی به آدرس جدید می‌رود، "
                    "نه به این آدرس.</p>"
                    "<p>این پیام فقط اطلاع‌رسانی است و پیوندی برای بازگرداندن ندارد.</p>"
                    "</div>"
                ),
                text_body=(
                    "ایمیل حساب شما از این پس "
                    f"{request_row.new_email} است.\n"
                    "اگر این کار را شما نکرده‌اید، همین حالا با پشتیبانی تماس بگیرید. "
                    "بازنشانی رمز کمکی نمی‌کند: لینک بازنشانی به آدرس جدید می‌رود، نه به این آدرس.\n\n"
                    "این پیام فقط اطلاع‌رسانی است و پیوندی برای بازگرداندن ندارد."
                ),
            )
        except Exception:  # noqa: BLE001 - the change itself already succeeded
            logger.exception("email_change_notice_failed", user_id=str(user.id))

    await logger.ainfo("email_changed", user_id=str(user.id))

    return {"status": "confirmed", "email": request_row.new_email}


async def get_pending_email_change(db: AsyncSession, *, user_id: uuid.UUID) -> dict[str, Any]:
    """The account's outstanding proposal, for the profile screen.

    Lets the UI say "we sent a link to x@y.com" without the client having to
    hold state it would otherwise lose on refresh.
    """
    now = datetime.now(UTC)
    result = await db.execute(
        select(EmailChangeRequest)
        .where(
            EmailChangeRequest.user_id == user_id,
            EmailChangeRequest.used_at.is_(None),
            EmailChangeRequest.invalidated_at.is_(None),
        )
        .order_by(EmailChangeRequest.created_at.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    if row is None or row.expires_at <= now:
        return {"pending": False}

    return {
        "pending": True,
        "new_email": row.new_email,
        "expires_at": row.expires_at.isoformat(),
    }
