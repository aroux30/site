"""SMTP email delivery service for the notifications module.

Real outbound email replacing the development mock, wired into the existing
channel abstraction:

- Transport is stdlib ``smtplib`` executed in a thread via
  ``asyncio.to_thread`` — the project deliberately ships **no** new
  dependency (aiosmtplib is not installed).
- TLS/SSL: port 465 uses implicit SSL (``SMTP_SSL``); other ports use
  STARTTLS when ``SMTP_USE_TLS`` is true.
- One retry on transient SMTP 4xx responses; permanent 5xx failures are
  not retried.
- Every dispatch writes an :class:`EmailDeliveryLog` row (queued →
  sent/failed) so ops can audit delivery without reading worker logs.
- Disabled-when-unconfigured: with a blank ``SMTP_HOST`` the service logs
  a warning and falls back to the previous mock behavior (records the log
  row as SENT with a simulated marker, never raises) so existing callers
  keep working in development.

Templates render with the module's existing ``{{variable}}`` substitution
(see ``NotificationService.send_from_template``); email variants render
both an RTL HTML body and a plain-text fallback, combined into a
``multipart/alternative`` message.
"""

from __future__ import annotations

import smtplib
import ssl
from dataclasses import dataclass, field
from email.message import EmailMessage
from email.utils import formataddr
from typing import TYPE_CHECKING, Any

import structlog
import asyncio

from app.core.config.settings import get_settings
from app.modules.notifications.application.store_name import (
    DEFAULT_STORE_NAME,
    resolve_store_name,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.notifications.domain.models import EmailDeliveryLog

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# SMTP response-code classes (RFC 5321 §4.2): 4xx = transient, retry once;
# 5xx = permanent, fail immediately.
_TRANSIENT_SMTP_CODES = range(400, 500)


class EmailConfigurationError(Exception):
    """Raised when a real send is attempted without complete SMTP settings."""


class EmailDeliveryError(Exception):
    """Raised when the SMTP provider rejects or fails a delivery."""


@dataclass(frozen=True)
class SmtpConfig:
    """Resolved SMTP settings for one dispatch (env, runtime-overridable)."""

    host: str
    port: int = 587
    username: str = ""
    password: str = ""
    use_tls: bool = True
    from_address: str = ""
    from_name: str = ""
    timeout_seconds: int = 15

    @property
    def is_configured(self) -> bool:
        """Host + sender are the minimum a real dispatch needs."""
        return bool(self.host.strip()) and bool(self.from_address.strip())


@dataclass(frozen=True)
class SmtpSendResult:
    """Outcome of one SMTP dispatch attempt chain."""

    success: bool
    response: str = ""
    attempts: int = 1
    transient_retry: bool = False
    error: str | None = None


def get_smtp_config(runtime_overrides: dict[str, Any] | None = None) -> SmtpConfig:
    """Build the effective SMTP configuration.

    Environment settings are the base; a ``smtp`` group row from the
    site-settings store may override individual fields (admin UI edits).
    Only non-empty override values win, and secrets are never logged here.
    """
    s = get_settings()
    base: dict[str, Any] = {
        "host": s.SMTP_HOST,
        "port": s.SMTP_PORT,
        "username": s.SMTP_USERNAME,
        "password": s.SMTP_PASSWORD,
        "use_tls": s.SMTP_USE_TLS,
        "from_address": s.SMTP_FROM_ADDRESS,
        "from_name": s.SMTP_FROM_NAME,
        "timeout_seconds": s.SMTP_TIMEOUT_SECONDS,
    }
    if runtime_overrides:
        for key in base:
            value = runtime_overrides.get(key)
            if value is None:
                continue
            if isinstance(base[key], bool):
                base[key] = bool(value)
            elif isinstance(base[key], int):
                try:
                    base[key] = int(value)
                except (TypeError, ValueError):
                    continue
            elif str(value).strip() != "" or key == "password":
                base[key] = str(value)
    return SmtpConfig(**base)


#: Largest attachment accepted, in bytes. 20 MB is the ceiling most SMTP
#: relays enforce; a larger file would be rejected by the server after being
#: read into memory here, so refusing it early is the honest answer.
MAX_ATTACHMENT_BYTES = 20 * 1024 * 1024
MAX_ATTACHMENTS = 5


def build_mime_message(
    *,
    config: SmtpConfig,
    recipient: str,
    subject: str,
    html_body: str,
    text_body: str,
    attachments: list[dict[str, Any]] | None = None,
    reply_to: str | None = None,
) -> EmailMessage:
    """Assemble a multipart/mixed message (plain + RTL HTML, plus files).

    ``attachments`` is a list of ``{"filename": str, "content": bytes,
    "content_type": str | None}``. It is applied *after* the alternative part,
    which is what makes the message multipart/mixed — the alternative pair has
    to stay intact as the body, and adding files before it would break the
    structure some clients rely on to pick a rendering.
    """
    if not config.from_address.strip():
        raise EmailConfigurationError("SMTP from_address is empty")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = formataddr((config.from_name or "", config.from_address))
    msg["To"] = recipient
    if reply_to:
        # Validated before it reaches a header. An unvalidated value here is a
        # header-injection primitive: a newline would let a commenter-supplied
        # address append headers of their own to an email the store sends.
        candidate = reply_to.strip()
        if any(ch in candidate for ch in (chr(10), chr(13))):
            raise EmailConfigurationError(
                f"reply_to contains a line break: {candidate[:64]!r}"
            )
        try:
            msg["Reply-To"] = formataddr(("", candidate))
        except (ValueError, UnicodeEncodeError) as exc:
            raise EmailConfigurationError(
                f"reply_to is not a usable address: {candidate[:64]!r}"
            ) from exc
    # Plain text first; HTML second so capable clients render the RTL body.
    msg.set_content(text_body or subject, charset="utf-8")
    msg.add_alternative(html_body or f"<p>{text_body}</p>", subtype="html", charset="utf-8")

    for item in attachments or []:
        filename = str(item.get("filename") or "").strip()
        content = item.get("content")
        if not filename or not isinstance(content, (bytes, bytearray)):
            logger.warning("email_attachment_skipped", reason="missing name or content")
            continue
        if len(content) > MAX_ATTACHMENT_BYTES:
            raise EmailDeliveryError(
                f"Attachment {filename} is "
                f"{len(content) // (1024 * 1024)}MB, over the "
                f"{MAX_ATTACHMENT_BYTES // (1024 * 1024)}MB limit"
            )
        # maintype is taken from the declared type so the client picks an icon;
        # a wrong or absent one falls back to application/octet-stream, which
        # is how every client treats an unknown file anyway.
        ctype = str(item.get("content_type") or "application/octet-stream")
        maintype, _, subtype = ctype.partition("/")
        maintype = maintype or "application"
        subtype = subtype or "octet-stream"
        msg.add_attachment(
            bytes(content),
            maintype=maintype,
            subtype=subtype,
            filename=filename,
        )
    return msg


def _smtp_send_sync(
    *,
    config: SmtpConfig,
    message: EmailMessage,
    recipient: str,
) -> str:
    """Blocking SMTP round-trip (runs in a worker thread).

    Returns the provider's response line for the delivery log.
    """
    implicit_ssl = config.port == 465
    timeout = config.timeout_seconds

    if implicit_ssl:
        context = ssl.create_default_context()
        client: smtplib.SMTP = smtplib.SMTP_SSL(
            config.host, config.port, timeout=timeout, context=context
        )
    else:
        client = smtplib.SMTP(config.host, config.port, timeout=timeout)

    try:
        client.ehlo()
        if config.use_tls and not implicit_ssl:
            context = ssl.create_default_context()
            client.starttls(context=context)
            client.ehlo()
        if config.username:
            client.login(config.username, config.password)
        refused = client.send_message(
            message,
            from_addr=config.from_address,
            to_addrs=[recipient],
        )
        if refused:
            # send_message returns {recipient: (code, resp)} only for refused
            # recipients; treat any refusal as a delivery failure.
            code, resp = next(iter(refused.values()))
            text = resp.decode(errors="replace") if isinstance(resp, bytes) else str(resp)
            raise smtplib.SMTPRecipientsRefused({recipient: (code, text)})
        return "250 OK: message accepted for delivery"
    finally:
        try:
            client.quit()
        except smtplib.SMTPException:
            client.close()


async def _attempt_send(
    *,
    config: SmtpConfig,
    message: EmailMessage,
    recipient: str,
) -> str:
    """Run the blocking SMTP round-trip off the event loop."""
    return await asyncio.to_thread(
        _smtp_send_sync, config=config, message=message, recipient=recipient
    )


async def send_smtp(
    *,
    config: SmtpConfig,
    recipient: str,
    subject: str,
    html_body: str,
    text_body: str,
    attachments: list[dict[str, Any]] | None = None,
    reply_to: str | None = None,
) -> SmtpSendResult:
    """Send one email via SMTP, retrying once on transient (4xx) failures.

    Never raises for delivery problems — the outcome is reported in the
    returned :class:`SmtpSendResult` so the caller can persist it.
    """
    if not config.is_configured:
        raise EmailConfigurationError("SMTP is not configured (host/from_address missing)")

    message = build_mime_message(
        config=config,
        recipient=recipient,
        subject=subject,
        html_body=html_body,
        text_body=text_body,
        attachments=attachments,
        reply_to=reply_to,
    )

    attempts = 0
    retried = False
    while True:
        attempts += 1
        try:
            response = await _attempt_send(config=config, message=message, recipient=recipient)
            return SmtpSendResult(
                success=True,
                response=response,
                attempts=attempts,
                transient_retry=retried,
            )
        except smtplib.SMTPResponseException as exc:
            code = exc.smtp_code
            text = (
                exc.smtp_error.decode(errors="replace")
                if isinstance(exc.smtp_error, bytes)
                else str(exc.smtp_error)
            )
            if code in _TRANSIENT_SMTP_CODES and not retried:
                retried = True
                await logger.awarning(
                    "email_transient_smtp_retry",
                    recipient=recipient,
                    smtp_code=code,
                    attempt=attempts,
                )
                await asyncio.sleep(0.5)
                continue
            await logger.aerror(
                "email_smtp_rejected",
                recipient=recipient,
                smtp_code=code,
                attempts=attempts,
            )
            return SmtpSendResult(
                success=False,
                response=f"{code} {text}",
                attempts=attempts,
                transient_retry=retried,
                error=f"SMTP {code}: {text}",
            )
        except (smtplib.SMTPException, OSError, ssl.SSLError) as exc:
            await logger.aerror(
                "email_smtp_transport_failed",
                recipient=recipient,
                error=str(exc),
                attempts=attempts,
            )
            return SmtpSendResult(
                success=False,
                attempts=attempts,
                transient_retry=retried,
                error=f"{type(exc).__name__}: {exc}",
            )


# ── Persistence-aware dispatch ────────────────────────────────────────────


async def send_email(
    db: AsyncSession | None,
    *,
    recipient: str,
    subject: str,
    html_body: str,
    text_body: str,
    template: str | None = None,
    notification_id: Any | None = None,
    config: SmtpConfig | None = None,
    attachments: list[dict[str, Any]] | None = None,
    reply_to: str | None = None,
) -> tuple[bool, "EmailDeliveryLog | None"]:
    """Dispatch one email and persist its delivery log row.

    ``attachments`` is a list of ``{"filename", "content", "content_type"}``
    dicts, the shape :func:`build_mime_message` takes. Bytes only: an
    attachment is read once, here, rather than being read again by a task queue
    that may run minutes later against a file that has since moved.

    Returns ``(success, log_row)``. The log row is best-effort: when no
    session is available (or persistence itself fails) the email is still
    attempted and ``log_row`` is ``None``.
    """
    from app.modules.notifications.domain.models import (
        EmailDeliveryLog,
        EmailDeliveryStatus,
    )

    effective = config or get_smtp_config()

    log_row: EmailDeliveryLog | None = None
    if db is not None:
        try:
            log_row = EmailDeliveryLog(
                notification_id=notification_id,
                recipient=recipient,
                subject=subject[:500],
                template=template,
                status=EmailDeliveryStatus.QUEUED,
                provider="smtp" if effective.is_configured else "mock_fallback",
            )
            db.add(log_row)
            await db.flush()
        except Exception:
            await logger.awarning("email_delivery_log_persist_failed", recipient=recipient)
            log_row = None

    if not effective.is_configured:
        # Unconfigured SMTP is NOT a success. Reporting SENT here made the
        # outbox, order flows and the newsletter sender believe a message went
        # out, so an operator could not tell a failed dispatch from a real
        # delivery. We keep the send non-fatal (a missing SMTP host must not
        # roll back an order), but the outcome is now honest: SKIPPED, with
        # attempts=0 so the delivery log shows nothing left the platform.
        await logger.awarning(
            "email_not_configured_skipped",
            recipient=recipient,
            subject=subject,
            template=template,
        )
        if log_row is not None:
            log_row.status = EmailDeliveryStatus.SKIPPED
            log_row.attempts = 0
            reason = "NOT SENT: SMTP is not configured (host or from_address missing)"
            log_row.provider_response = reason
            # `error` was left null here, and the admin test-email response
            # reads that field — so an operator saw success: false with no
            # reason. Set both, the same way the failure path does.
            log_row.error = reason
            await db.flush()  # type: ignore[union-attr]
        # Return False, not True. The row above is already recorded as SKIPPED
        # and the comment two lines up says this is not a success — returning
        # True contradicted both, and 11 call sites branch on this value
        # (outbox_worker.py:508,610; rules_engine.py:138;
        # settings/api/routes.py:314; notification_service.py:81; tasks.py:62;
        # saved_report_service.py:375; campaign_service.py:318,486;
        # newsletter_service.py:135; email_change_service.py:147). The
        # "send test email" button in the admin panel was showing the operator
        # success while nothing had left the platform, and retry logic decided
        # there was nothing to retry.
        return False, log_row

    result = await send_smtp(
        config=effective,
        recipient=recipient,
        subject=subject,
        html_body=html_body,
        text_body=text_body,
        attachments=attachments,
        reply_to=reply_to,
    )

    if log_row is not None:
        from datetime import UTC, datetime

        log_row.attempts = result.attempts
        log_row.provider_response = result.response or None
        if result.success:
            log_row.status = EmailDeliveryStatus.SENT
            log_row.sent_at = datetime.now(UTC)
        else:
            log_row.status = EmailDeliveryStatus.FAILED
            log_row.error = (result.error or "unknown SMTP error")[:2000]
        await db.flush()  # type: ignore[union-attr]

    if result.success:
        await logger.ainfo(
            "email_sent",
            recipient=recipient,
            subject=subject,
            template=template,
            attempts=result.attempts,
        )
    return result.success, log_row


# ── Default Persian RTL templates ─────────────────────────────────────────


@dataclass(frozen=True)
class EmailTemplateContent:
    """Rendered subject + bodies for one named email template."""

    subject: str
    html: str
    text: str
    variables: list[str] = field(default_factory=list)


_RTL_HTML_SHELL = """<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"></head>
<body style="margin:0;padding:0;background-color:#f4f5f7;font-family:Tahoma,Arial,sans-serif;">
  <div dir="rtl" style="max-width:600px;margin:24px auto;background:#ffffff;border-radius:12px;overflow:hidden;border:1px solid #e5e7eb;">
    <div style="background:#1f2937;padding:20px 24px;">
      <span style="color:#ffffff;font-size:16px;font-weight:bold;">{{store_name}}</span>
    </div>
    <div style="padding:24px;color:#111827;font-size:14px;line-height:2;">
      __BODY__
    </div>
    <div style="padding:16px 24px;background:#f9fafb;color:#6b7280;font-size:11px;text-align:center;">
      این ایمیل به‌صورت خودکار ارسال شده است؛ لطفاً به آن پاسخ ندهید.
    </div>
  </div>
</body>
</html>"""


def _wrap_html(store_name: str, body_html: str) -> str:
    return _RTL_HTML_SHELL.replace("{{store_name}}", store_name).replace(
        "__BODY__", body_html
    )


async def wrap_html_for_store(db: AsyncSession, body_html: str) -> str:
    """Render a body into the store's own email shell.

    The async counterpart to ``_wrap_html``, for callers that have a session and
    therefore can be told the operator's actual name. Three generic send paths
    used to read ``SMTP_FROM_NAME`` here instead, so the same store printed its
    operator name on an order confirmation and "فروشگاه اینترنتی" on the
    shipping notification — two names, same customer, same inbox.
    """
    return _wrap_html(await resolve_store_name(db), body_html)


def default_email_templates(store_name: str | None = None) -> dict[str, EmailTemplateContent]:
    """Built-in Persian RTL templates for the core transactional flows.

    Used when no matching row exists in ``notification_templates`` (the DB
    store stays authoritative once an admin creates one). Variable syntax
    matches ``NotificationService.send_from_template``: ``{{name}}``.

    ``store_name`` is the operator's store name, resolved by the caller from the
    settings — ``resolve_store_name(db)`` is the one place that decides, so the
    transactional templates and the generic send paths cannot disagree. It was
    hardcoded to "فروشگاه اینترنتی" in all four templates, so every order
    confirmation and password reset said the wrong thing for a store with any
    other name. Defaulting keeps this function callable from anywhere that has
    no settings session, which is the common case.
    """
    name = (store_name or "").strip() or DEFAULT_STORE_NAME
    return {
        "order_confirmation": EmailTemplateContent(
            subject="سفارش شما با موفقیت ثبت شد — {{order_number}}",
            html=_wrap_html(
                name,
                """
      <h2 style="margin:0 0 12px;font-size:16px;">سفارش شما ثبت شد</h2>
      <p>مشتری گرامی {{customer_name}}،</p>
      <p>سفارش شما با شماره <strong>{{order_number}}</strong> با موفقیت ثبت شد.</p>
      <p>مبلغ سفارش: <strong>{{total_toman}} تومان</strong></p>
      <p>می‌توانید وضعیت سفارش خود را از بخش «سفارش‌های من» در پنل کاربری پیگیری کنید.</p>""",
            ),
            text=(
                "سفارش شما ثبت شد\n\n"
                "مشتری گرامی {{customer_name}}،\n"
                "سفارش شما با شماره {{order_number}} با موفقیت ثبت شد.\n"
                "مبلغ سفارش: {{total_toman}} تومان\n"
                "وضعیت سفارش را از پنل کاربری پیگیری کنید."
            ),
            variables=["customer_name", "order_number", "total_toman"],
        ),
        "order_shipped": EmailTemplateContent(
            subject="سفارش شما ارسال شد — {{order_number}}",
            html=_wrap_html(
                name,
                """
      <h2 style="margin:0 0 12px;font-size:16px;">سفارش شما ارسال شد</h2>
      <p>مشتری گرامی {{customer_name}}،</p>
      <p>سفارش <strong>{{order_number}}</strong> تحویل شرکت حمل‌ونقل شد.</p>
      <p>کد رهگیری مرسوله: <strong>{{tracking_code}}</strong></p>""",
            ),
            text=(
                "سفارش شما ارسال شد\n\n"
                "مشتری گرامی {{customer_name}}،\n"
                "سفارش {{order_number}} تحویل شرکت حمل‌ونقل شد.\n"
                "کد رهگیری مرسوله: {{tracking_code}}"
            ),
            variables=["customer_name", "order_number", "tracking_code"],
        ),
        "refund_processed": EmailTemplateContent(
            subject="بازگشت وجه سفارش {{order_number}} انجام شد",
            html=_wrap_html(
                name,
                """
      <h2 style="margin:0 0 12px;font-size:16px;">بازگشت وجه انجام شد</h2>
      <p>مشتری گرامی {{customer_name}}،</p>
      <p>مبلغ <strong>{{amount_toman}} تومان</strong> بابت سفارش <strong>{{order_number}}</strong> بازگردانده شد.</p>
      <p>وجه حداکثر تا ۷۲ ساعت آینده به حساب یا کیف پول شما واریز می‌شود.</p>""",
            ),
            text=(
                "بازگشت وجه انجام شد\n\n"
                "مشتری گرامی {{customer_name}}،\n"
                "مبلغ {{amount_toman}} تومان بابت سفارش {{order_number}} بازگردانده شد.\n"
                "وجه حداکثر تا ۷۲ ساعت آینده به حساب یا کیف پول شما واریز می‌شود."
            ),
            variables=["customer_name", "order_number", "amount_toman"],
        ),
        "password_reset": EmailTemplateContent(
            subject="بازیابی رمز عبور حساب کاربری",
            html=_wrap_html(
                name,
                """
      <h2 style="margin:0 0 12px;font-size:16px;">بازیابی رمز عبور</h2>
      <p>{{customer_name}} عزیز،</p>
      <p>برای تعیین رمز عبور جدید روی پیوند زیر بزنید:</p>
      <p style="text-align:center;margin:20px 0;">
        <a href="{{reset_url}}" style="background:#1f2937;color:#ffffff;text-decoration:none;padding:10px 28px;border-radius:8px;display:inline-block;">تغییر رمز عبور</a>
      </p>
      <p style="color:#6b7280;font-size:12px;">اعتبار این پیوند {{expiry_minutes}} دقیقه است. اگر شما این درخواست را نداده‌اید، این ایمیل را نادیده بگیرید.</p>""",
            ),
            text=(
                "بازیابی رمز عبور\n\n"
                "{{customer_name}} عزیز،\n"
                "برای تعیین رمز عبور جدید از این پیوند استفاده کنید:\n{{reset_url}}\n"
                "اعتبار پیوند {{expiry_minutes}} دقیقه است."
            ),
            variables=["customer_name", "reset_url", "expiry_minutes"],
        ),
        # WordPress's wp_notify_postauthor and wp_notify_comment: a new comment
        # reaches the post author by email with Reply-To set to the commenter,
        # so "reply" in the mail client answers them directly. The in-app
        # notification that already existed reaches the same people, but only
        # while they are logged in — a store that answers comments by email
        # lost that path entirely.
        "comment_new": EmailTemplateContent(
            subject="دیدگاه تازه روی «{{post_title}}»",
            html=_wrap_html(
                name,
                """
      <h2 style="margin:0 0 12px;font-size:16px;">دیدگاه تازه</h2>
      <p><strong>{{commenter_name}}</strong> روی «{{post_title}}» نوشته:</p>
      <blockquote style="margin:16px 0;padding:12px;border-right:3px solid #d1d5db;background:#f9fafb;">{{comment_content}}</blockquote>
      <p style="text-align:center;margin:20px 0;">
        <a href="{{manage_url}}" style="background:#1f2937;color:#ffffff;text-decoration:none;padding:10px 28px;border-radius:8px;display:inline-block;">دیدن و پاسخ در پنل</a>
      </p>
      <p style="text-align:center;margin:16px 0;font-size:13px;">
        <a href="{{approve_url}}" style="background:#0f766e;color:#ffffff;text-decoration:none;padding:8px 18px;border-radius:6px;display:inline-block;margin:0 4px;">تأیید</a>
        <a href="{{spam_url}}" style="background:#b45309;color:#ffffff;text-decoration:none;padding:8px 18px;border-radius:6px;display:inline-block;margin:0 4px;">اسپم</a>
        <a href="{{trash_url}}" style="background:#6b7280;color:#ffffff;text-decoration:none;padding:8px 18px;border-radius:6px;display:inline-block;margin:0 4px;">زباله‌دان</a>
      </p>
      <p style="color:#9ca3af;font-size:11px;">
        این پیوندها یک‌بارمصرف‌اند و پس از استفاده از کار می‌افتند.
      </p>
      <p style="color:#6b7280;font-size:12px;">
        وضعیت این دیدگاه: {{comment_status}}. می‌توانید مستقیم به فرستنده پاسخ دهید —
        پاسخ شما از نشانی همین ایمیل ارسال می‌شود.
      </p>""",
            ),
            text=(
                "دیدگاه تازه روی «{{post_title}}»"
                + "\n\n"
                + "{{commenter_name}}:"
                + "\n"
                + "{{comment_content}}"
                + "\n\n"
                + "{{manage_url}}"
                + "\n\n"
                + "تأیید: {{approve_url}}"
                + "\n"
                + "اسپم:  {{spam_url}}"
                + "\n"
                + "زباله‌دان: {{trash_url}}"
            ),
            variables=[
                "post_title", "commenter_name", "comment_content",
                "comment_status", "manage_url",
                "approve_url", "spam_url", "trash_url",
            ],
        ),
        # The other half of wp_notify_comment: the commenter is told their
        # comment went live. Only ever sent to an address the commenter gave —
        # never guessed from a username or an account id.
        "comment_approved": EmailTemplateContent(
            subject="دیدگاه شما منتشر شد",
            html=_wrap_html(
                name,
                """
      <h2 style="margin:0 0 12px;font-size:16px;">دیدگاه شما منتشر شد</h2>
      <p>{{commenter_name}} عزیز،</p>
      <p>دیدگاه شما روی «{{post_title}}» بررسی و منتشر شد.</p>
      <blockquote style="margin:16px 0;padding:12px;border-right:3px solid #d1d5db;background:#f9fafb;">{{comment_content}}</blockquote>
      <p style="text-align:center;margin:20px 0;">
        <a href="{{post_url}}" style="background:#1f2937;color:#ffffff;text-decoration:none;padding:10px 28px;border-radius:8px;display:inline-block;">دیدن دیدگاه</a>
      </p>""",
            ),
            text=(
                "دیدگاه شما منتشر شد"
                + "\n\n"
                + "دیدگاه شما روی «{{post_title}}» منتشر شد."
                + "\n"
                + "{{post_url}}"
            ),
            variables=["commenter_name", "post_title", "comment_content", "post_url"],
        ),
    }


def render_template(content: EmailTemplateContent, variables: dict[str, str]) -> EmailTemplateContent:
    """Apply the module's ``{{var}}`` substitution to a template triple."""
    subject, html, text = content.subject, content.html, content.text
    for key, value in variables.items():
        token = f"{{{{{key}}}}}"
        subject = subject.replace(token, value)
        html = html.replace(token, value)
        text = text.replace(token, value)
    return EmailTemplateContent(
        subject=subject, html=html, text=text, variables=content.variables
    )
