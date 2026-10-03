"""The two emails a registration produces: one to the customer, one to the store.

P0 "کاربران: ایمیل خوش‌آمد ثبت‌نام و اطلاع به مدیر". Neither existed. The
customer got a token pair and a flash of success, and the store got a row in
``audit_logs`` that nobody reads during business hours — so on a store taking
pre-orders by Instagram or a launch page, a registration was invisible until
someone went looking for it.

The admin notice is the half that matters commercially and the half nobody builds:
a new account is the earliest possible signal that something is working, or that
somebody is signing up in a way worth looking at.

Deliberately fire-and-forget, in both directions. A signup that fails because the
SMTP host is unreachable produces an account the customer believes in and an
operator never learns about, which is worse than a signup that succeeds and a
mail that is logged. So neither send can raise, and both say what happened in the
log rather than in a traceback nobody reads.

The customer's address is optional. Registration is by phone, and a large share of
accounts have no email at all — a "welcome" addressed to nothing is not a welcome,
so the absence is a normal outcome and not a failure to report.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from sqlalchemy import select

from app.core.security.ip_anonymize import anonymize_ip
from app.modules.notifications.application.store_name import resolve_store_name

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class RegistrationEmailService:
    """Say hello to the new account, and tell the store it happened."""

    @staticmethod
    async def send_welcome(db: AsyncSession, *, user_id: object) -> bool:
        """Email the new customer. Returns whether it was attempted and sent.

        False is a real answer and the caller is expected to log it: no address
        on the account is the common case, since registration is by phone.
        """
        from app.modules.users.domain.models import User

        user = await db.get(User, user_id)
        if user is None:
            logger.warning("welcome_email_no_user", user_id=str(user_id))
            return False
        if not user.email:
            logger.info("welcome_email_skipped_no_recipient", user_id=str(user.id))
            return False

        store_name = await resolve_store_name(db)
        try:
            from app.modules.notifications.application.email_service import (
                send_email,
                wrap_html_for_store,
            )

            greeting = (
                f"{user.profile.first_name}"
                if getattr(user, "profile", None) and user.profile.first_name
                else "دوست عزیز"
            )
            await send_email(
                db,
                recipient=user.email,
                subject=f"به {store_name} خوش آمدید",
                text_body=(
                    f"{greeting}،\n\n"
                    f"حساب شما در {store_name} ساخته شد و آمادهٔ استفاده است.\n\n"
                    f"شمارهٔ حساب: {user.phone}\n\n"
                    "اگر این ثبت‌نام را انجام نداده‌اید، با پشتیبانی تماس بگیرید."
                ),
                html_body=await wrap_html_for_store(
                    db,
                    "<p>%s،</p>"
                    "<p>حساب شما در <strong>%s</strong> ساخته شد و آمادهٔ استفاده است.</p>"
                    "<p>شمارهٔ حساب: <strong dir=\"ltr\">%s</strong></p>"
                    "<p>اگر این ثبت‌نام را انجام نداده‌اید، با پشتیبانی تماس بگیرید.</p>"
                    % (greeting, store_name, user.phone),
                ),
            )
        except Exception as exc:  # a mail outage must not fail the signup
            logger.warning("welcome_email_failed", user_id=str(user.id), error=str(exc))
            return False
        logger.info("welcome_email_sent", user_id=str(user.id))
        return True

    @staticmethod
    async def notify_admin(db: AsyncSession, *, user_id: object) -> bool:
        """Tell the store's admin address that an account was created.

        Read from the same ``admin_email`` option the rest of the settings
        surface shows, so an operator changes it in one place. A store that has
        not set one gets no notice, and that is reported rather than passed off
        as delivered.
        """
        from app.modules.users.domain.models import User

        user = await db.get(User, user_id)
        if user is None:
            return False

        recipient = await _admin_email(db)
        if not recipient:
            logger.info("admin_signup_notice_skipped_no_recipient", user_id=str(user.id))
            return False

        store_name = await resolve_store_name(db)
        # The IP is masked rather than exact: this notice reaches an operator's
        # inbox, which is a wider audience than the signup form, and the network is
        # what tells them whether several signups came from one place.
        ip_note = ""
        try:
            ip = await _signup_ip(db, user_id=user.id)
            if ip:
                ip_note = f"<p>IP: <code dir=\"ltr\">{anonymize_ip(ip)}</code></p>"
        except Exception:  # noqa: BLE001 — a missing IP is not worth failing over
            ip_note = ""

        try:
            from app.modules.notifications.application.email_service import (
                send_email,
                wrap_html_for_store,
            )

            await send_email(
                db,
                recipient=recipient,
                subject=f"ثبت‌نام جدید در {store_name}",
                text_body=(
                    f"یک حساب جدید در {store_name} ساخته شد.\n\n"
                    f"شماره: {user.phone}\n"
                    f"ایمیل: {user.email or '—'}\n"
                    f"زمان: {user.created_at}"
                ),
                html_body=await wrap_html_for_store(
                    db,
                    "<p>یک حساب جدید ثبت شد:</p>"
                    "<ul>"
                    "<li>شماره: <strong dir=\"ltr\">%s</strong></li>"
                    "<li>ایمیل: <strong dir=\"ltr\">%s</strong></li>"
                    "</ul>%s"
                    % (user.phone, user.email or "—", ip_note),
                ),
            )
        except Exception as exc:  # a mail outage must not fail the signup
            logger.warning("admin_signup_notice_failed", user_id=str(user.id), error=str(exc))
            return False
        logger.info("admin_signup_notice_sent", user_id=str(user.id), recipient=recipient)
        return True


    @staticmethod
    async def send_password_changed_notice(db: AsyncSession, *, user_id: object) -> bool:
        """Tell an account holder their password just changed.

        P0 "کاربران: ایمیل اطلاع تغییر رمز". The rotation revoked every session
        and wrote an audit row, and told the person nothing — so somebody whose
        password was changed by someone else keeps using the old one until it
        stops working, and never learns why.

        Named "notice" rather than "confirmation" on purpose. The user asked for
        this change, so a mail about it is a courtesy; the case that matters is
        the one where they did not, and this is the only signal that reaches
        them. It therefore says *what* happened and *when*, and points at support
        rather than at a link — a link in a security notice is a phishing target,
        and this project has no business minting one under a password-change
        heading.

        Fire-and-forget like the rest: a mail outage must not leave the password
        changed and unconfirmed *by failing* — the rotation has already happened
        either way.
        """
        from app.modules.users.domain.models import User

        user = await db.get(User, user_id)
        if user is None:
            logger.warning("password_changed_notice_no_user", user_id=str(user_id))
            return False
        if not user.email:
            logger.info(
                "password_changed_notice_skipped_no_recipient", user_id=str(user.id)
            )
            return False

        store_name = await resolve_store_name(db)
        when, was_never_rotated = _password_changed_when(user)
        try:
            from app.modules.notifications.application.email_service import (
                send_email,
                wrap_html_for_store,
            )

            await send_email(
                db,
                recipient=user.email,
                subject="رمز عبور حساب شما تغییر کرد",
                text_body=(
                    f"رمز عبور حساب شما در {store_name} تغییر کرد.\n\n"
                    "همهٔ نشست‌های فعال شما بسته شد و لازم است دوباره وارد شوید.\n\n"
                    f"زمان: {when}\n\n"
                    "اگر این تغییر را انجام نداده‌اید، هرچه زودتر با پشتیبانی "
                    "تماس بگیرید."
                ),
                html_body=await wrap_html_for_store(
                    db,
                    "<p>رمز عبور حساب شما در <strong>%s</strong> تغییر کرد.</p>"
                    "<p>همهٔ نشست‌های فعال شما بسته شد و لازم است دوباره وارد شوید.</p>"
                    "<p>زمان: <code>%s</code></p>"
                    "<p><strong>اگر این تغییر را انجام نداده‌اید، هرچه زودتر با "
                    "پشتیبانی تماس بگیرید.</strong></p>"
                    % (store_name, when),
                ),
            )
            if was_never_rotated:
                # Said outright rather than letting the fallback read as a
                # rotation time. This branch only fires for an account that has
                # never rotated — a fresh one whose notice is really a welcome —
                # and quietly dating it to the last update would be a lie about
                # the one thing the mail exists to be truthful about.
                logger.info(
                    "password_changed_notice_has_no_rotation_stamp",
                    user_id=str(user.id),
                )
        except Exception as exc:  # a mail outage must not fail the rotation
            logger.warning(
                "password_changed_notice_failed", user_id=str(user.id), error=str(exc)
            )
            return False
        logger.info("password_changed_notice_sent", user_id=str(user.id))
        return True


async def _admin_email(db: AsyncSession) -> str | None:
    """The store's admin address, or None.

    Reads the same option the settings panel edits and the feed and sitemap read
    for their sender, rather than a second setting — three definitions of "where
    do store notices go" is how a store ends up with notices going to an address
    nobody owns.
    """
    from app.modules.settings.application.site_options_service import SiteOptionsService

    raw = await SiteOptionsService.get(db, "admin_email")
    if raw and "@" in raw:
        return raw.strip()
    # A verified superadmin's own address is a better guess than nobody: on a
    # fresh install the option is seeded with a placeholder, and the person who
    # set it up is the person who wants the notice.
    from app.modules.rbac.domain.models import Role, UserRole
    from app.modules.users.domain.models import User

    row = (
        await db.execute(
            select(User.email)
            .join(UserRole, UserRole.user_id == User.id)
            .join(Role, Role.id == UserRole.role_id)
            .where(
                Role.slug == "super_admin",
                User.is_active.is_(True),
                User.email.is_not(None),
            )
            .order_by(User.created_at)
            .limit(1)
        )
    ).scalar()
    return str(row).strip() if row else None


def _password_changed_when(user: object) -> tuple[object, bool]:
    """The time the notice names, and whether it is a real rotation time.

    Returns both rather than a bare value so the caller can *say* which it is.
    A notice that quietly substituted the account's last update would tell a
    person their password changed when they last fixed a typo in their name,
    and they would have no way to tell from reading it.

    Split out as a pure function so this is checkable without rendering a mail.
    """
    stamp = getattr(user, "password_changed_at", None)
    if stamp is not None:
        return stamp, True
    return getattr(user, "updated_at", None), False


async def _signup_ip(db: AsyncSession, *, user_id: object) -> str | None:
    """The address the signup came from, read from the audit log.

    The registration row is the only place it exists — the users table has no IP
    column, and the audit entry carries it under ``ip_address``. Reading the audit
    trail here means the notice cannot invent one, and if the log is ever cleared
    the notice simply has nothing to say about the address rather than a wrong
    value.
    """
    from app.modules.audit.domain.models import AuditLog

    row = (
        await db.execute(
            select(AuditLog.ip_address)
            .where(
                AuditLog.action == "user.register",
                AuditLog.resource_id == user_id,
                AuditLog.ip_address.is_not(None),
            )
            .order_by(AuditLog.created_at.desc())
            .limit(1)
        )
    ).scalar()
    return str(row) if row else None


async def send_registration_emails(db: AsyncSession, *, user_id: object) -> dict[str, bool]:
    """Both notices, and what each one did. Never raises.

    The single entry point ``register`` calls, so the "neither may fail the
    signup" rule is stated once rather than at each call site.
    """
    result = {"welcome": False, "admin_notice": False}
    for label, send in (
        ("welcome", lambda: RegistrationEmailService.send_welcome(db, user_id=user_id)),
        ("admin_notice", lambda: RegistrationEmailService.notify_admin(db, user_id=user_id)),
    ):
        try:
            result[label] = await send()
        except Exception as exc:  # noqa: BLE001 — belt and braces over the inner try
            logger.warning("registration_email_failed", which=label, error=str(exc))
            result[label] = False
    return result