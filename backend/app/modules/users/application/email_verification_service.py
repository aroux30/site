"""Confirm ownership of a registration email address.

P1 "کاربران: تأیید ایمیل هنگام ثبت‌نام". ``users.is_verified`` existed but was
only ever set by the OTP flow, which proves the *phone*, not the email. An
address typed at sign-up was therefore never checked — and password resets and
order notices are delivered to it, so a typo (or an address someone else owns)
silently absorbs mail meant for the account holder.

Same shape and same reasoning as :mod:`email_change_service`:

* the token is stored hashed, so a database leak cannot be replayed;
* a request expires, and an expired one is refused rather than accepted;
* redeeming is idempotent in the useful direction — a spent token says "already
  used" rather than verifying twice;
* the address is captured at issue time, so a link clicked after the account
  moved to a different address does not mark the wrong one verified.
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
from app.modules.users.domain.models import EmailVerificationToken, User

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

settings = get_settings()

#: How long a verification link stays usable. A day, matching WordPress's
#: default for account confirmation: the cost of a short window is only a
#: second email, and a long-lived link is one more thing that can leak.
EMAIL_VERIFICATION_TTL_HOURS = 24


def hash_verification_token(token: str) -> str:
    """SHA-256 of the token. The plaintext only ever exists in the email."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def verification_link(token: str) -> str:
    # Deliberately outside /account: that route group is behind the auth guard,
    # and the link is clicked from an inbox — possibly on a device with no
    # session. The token is the credential, so the page must render for anyone.
    return f"{settings.STOREFRONT_BASE_URL.rstrip('/')}/verify-email?token={token}"


class EmailVerificationError(Exception):
    """Raised when a verification cannot be honoured.

    Carries a machine-readable ``code`` so the route can answer with a Persian
    message rather than leaking a raw exception string.
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


async def issue_verification(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    email: str | None,
    send: bool = True,
) -> dict[str, Any]:
    """Create a verification token for the account's email and (optionally) mail it.

    Returns what happened rather than raising on a mail failure: the token is
    already persisted, so the account is not left un-verifiable just because
    SMTP blipped — the caller can offer a resend.
    """
    target = (email or "").strip().lower()
    if not target or "@" not in target:
        return {"sent": False, "reason": "no_email"}

    now = datetime.now(UTC)

    # Only the newest link should work: a user who clicks "resend" and then the
    # older mail must not redeem a token that was superseded.
    await db.execute(
        update(EmailVerificationToken)
        .where(
            EmailVerificationToken.user_id == user_id,
            EmailVerificationToken.used_at.is_(None),
        )
        .values(used_at=now)
    )

    token = secrets.token_urlsafe(48)
    db.add(
        EmailVerificationToken(
            user_id=user_id,
            email=target,
            token_hash=hash_verification_token(token),
            expires_at=now + timedelta(hours=EMAIL_VERIFICATION_TTL_HOURS),
        )
    )
    await db.commit()

    if not send:
        return {"sent": False, "reason": "not_requested"}

    try:
        from app.modules.notifications.application.email_service import send_email

        link = verification_link(token)
        sent, _log = await send_email(
            db,
            recipient=target,
            subject="تأیید ایمیل حساب",
            html_body=(
                '<div dir="rtl" style="font-family:Tahoma,sans-serif">'
                "<p>برای تأیید ایمیل حساب خود روی پیوند زیر کلیک کنید:</p>"
                f'<p><a href="{link}">{link}</a></p>'
                f"<p>این پیوند تا {EMAIL_VERIFICATION_TTL_HOURS} ساعت معتبر است. "
                "تا پیش از تأیید، اطلاع‌رسانی‌های مهم حساب به این نشانی فرستاده می‌شود "
                "ولی هنوز تأیید نشده است.</p>"
                "</div>"
            ),
            text_body=(
                "برای تأیید ایمیل حساب خود روی پیوند زیر کلیک کنید:\n\n"
                f"{link}\n\n"
                f"این پیوند تا {EMAIL_VERIFICATION_TTL_HOURS} ساعت معتبر است."
            ),
        )
        sent = bool(sent)
    except Exception:  # noqa: BLE001 — a mail outage must not lose the token
        logger.exception("email_verification_send_failed", user_id=str(user_id))
        sent = False

    logger.info("email_verification_issued", user_id=str(user_id), sent=sent)
    return {
        "sent": sent,
        "reason": None if sent else "send_failed",
        "expires_in_hours": EMAIL_VERIFICATION_TTL_HOURS,
    }


async def confirm_verification(db: AsyncSession, *, token: str) -> dict[str, Any]:
    """Redeem a verification token and mark the matching address verified."""
    now = datetime.now(UTC)
    digest = hash_verification_token(token)

    row = (
        await db.execute(
            select(EmailVerificationToken).where(
                EmailVerificationToken.token_hash == digest
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise EmailVerificationError("invalid_token", "لینک تأیید معتبر نیست.")

    if row.used_at is not None:
        raise EmailVerificationError("already_used", "این لینک قبلاً استفاده شده است.")

    if row.expires_at <= now:
        raise EmailVerificationError("expired", "مهلت این لینک به پایان رسیده است.")

    user = await db.get(User, row.user_id)
    if user is None:
        raise EmailVerificationError("not_found", "کاربر یافت نشد.")

    row.used_at = now
    # Verify only if the account still holds the address the link was sent to.
    # If it moved, the link proved nothing about the current address, and
    # setting the flag would mark an unverified address verified.
    if (user.email or "").strip().lower() == row.email:
        user.is_verified = True
    else:
        await db.commit()
        raise EmailVerificationError(
            "stale",
            "ایمیل حساب از زمان ارسال این لینک تغییر کرده است. لطفاً دوباره درخواست تأیید کنید.",
        )

    await db.commit()
    logger.info("email_verified", user_id=str(user.id))
    return {"verified": True, "email": row.email}


async def get_pending_verification(
    db: AsyncSession, *, user_id: uuid.UUID
) -> dict[str, Any]:
    """Whether the account has an unexpired, unredeemed verification link."""
    now = datetime.now(UTC)
    row = (
        await db.execute(
            select(EmailVerificationToken)
            .where(
                EmailVerificationToken.user_id == user_id,
                EmailVerificationToken.used_at.is_(None),
            )
            .order_by(EmailVerificationToken.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if row is None or row.expires_at <= now:
        return {"pending": False}
    return {
        "pending": True,
        "email": row.email,
        "expires_at": row.expires_at.isoformat(),
    }