"""Admin-editable email templates.

The transactional emails were HTML literals in ``email_service``, so changing
the wording of an order confirmation meant a code change and a deploy. The
``notification_templates`` table already existed and was read on send, so the
gap was the writing half: no API, no screen, and therefore no way for an
operator to change anything.

The security problem this creates is the interesting part. A template is HTML
that the backend sends to a customer's inbox, authored from an admin screen
with a rich-text editor. It is not sanitised like *content*: the difference is
who writes it. Content is written by editors and read by the public, so it goes
through ``sanitize_html``. A template is written by an operator with store
access and read by customers, and an operator who can inject a script into
every order confirmation is a much smaller problem than a public one.

What is still refused, because it costs nothing to refuse and protects the
inbox rather than the store:

* ``<script>``, ``<iframe>``, ``<object>``, ``<embed>`` and friends. A mail
  client strips them, so allowing them only makes the template look like it
  works while silently doing nothing — or, worse, survives in one client.
* ``javascript:`` and ``data:`` URLs. These *do* execute in some clients, and a
  link in an order confirmation is the one place a customer is most likely to
  click it.

Inline CSS, tables and the rest of the styling an email needs stay allowed:
stripping them would make the editor useless, and none of it runs script.
"""

from __future__ import annotations

import re
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions.handlers import NotFoundError, ValidationError

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

MAX_SUBJECT_LENGTH = 300
MAX_BODY_LENGTH = 200_000
MAX_VARIABLES = 40
MAX_VARIABLE_NAME_LENGTH = 60

#: Elements that execute. Refused outright rather than stripped: a template
#: that silently loses its script is more confusing than one that is refused.
_FORBIDDEN_TAGS = re.compile(
    r"<\s*/?\s*(script|iframe|object|embed|applet|form|base|link|meta)\b",
    re.IGNORECASE,
)
#: URL schemes that can execute in at least one mail client.
_DANGEROUS_SCHEME = re.compile(
    r"(?:href|src|action|background|formaction)\s*=\s*[\"']?\s*"
    r"(?:javascript|data|vbscript|file)\s*:",
    re.IGNORECASE,
)
_VARIABLE_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
#: ``{{name}}`` with optional surrounding whitespace, as send_from_template
#: documents.
_VARIABLE_USE = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")


def sanitize_email_template(html: str) -> str:
    """Refuse template HTML that can execute, keeping everything else.

    Returns the value unchanged when it is safe. Raises
    :class:`ValidationError` when it is not, so the author is told which save
    was rejected rather than finding out later that their template lost its
    styling.
    """
    if not html or not html.strip():
        raise ValidationError("متن قالب نمی‌تواند خالی باشد")
    if len(html) > MAX_BODY_LENGTH:
        raise ValidationError(
            f"متن قالب بیش از حد طولانی است (حداکثر {MAX_BODY_LENGTH} کاراکتر)"
        )
    if _FORBIDDEN_TAGS.search(html):
        raise ValidationError(
            "قالب ایمیل نمی‌تواند شامل script، iframe، form، base یا link باشد"
        )
    if _DANGEROUS_SCHEME.search(html):
        raise ValidationError(
            "قالب ایمیل نمی‌تواند از لینک‌های javascript:، data:، vbscript یا file استفاده کند"
        )
    return html


def validate_variables(names: list[str] | None) -> list[str]:
    """Check the declared variable list, and de-duplicate it preserving order."""
    if not names:
        return []
    if len(names) > MAX_VARIABLES:
        raise ValidationError(f"حداکثر {MAX_VARIABLES} متغیر مجاز است")
    seen: set[str] = set()
    out: list[str] = []
    for raw in names:
        name = (str(raw or "")).strip()
        if not name:
            continue
        if not _VARIABLE_NAME.match(name):
            raise ValidationError(
                f"نام متغیر «{name}» معتبر نیست؛ فقط حروف انگلیسی، عدد و زیرخط"
            )
        if len(name) > MAX_VARIABLE_NAME_LENGTH:
            raise ValidationError(
                f"نام متغیر «{name}» بیش از {MAX_VARIABLE_NAME_LENGTH} کاراکتر است"
            )
        if name not in seen:
            seen.add(name)
            out.append(name)
    return out


def variables_used(html: str, subject: str | None = None) -> list[str]:
    """Every ``{{name}}`` the template actually references, in first-use order.

    Offered to the editor as a checklist: a declared variable the body never
    uses is a promise the render will not keep, and a used one that was not
    declared is a value the send cannot supply.
    """
    found: list[str] = []
    for source in (subject or "", html or ""):
        for m in _VARIABLE_USE.finditer(source):
            name = m.group(1)
            if name not in found:
                found.append(name)
    return found


async def _operator_store_name(db: AsyncSession) -> str:
    """The store name an operator set, or an empty string.

    A thin alias over ``resolve_store_name`` rather than its own reader. It used
    to open-code the same two-option walk, which meant a third definition of
    "the store's name" existed in the codebase — and when the resolution order
    changed in one place, the other two kept the old order and disagreed with
    it in the rendered email.

    Returns the resolved name (never empty), which is what both of its call sites
    need; the function keeps its name because "what the operator set" is the
    question, and the answer is now defined once.
    """
    from app.modules.notifications.application.store_name import resolve_store_name

    return await resolve_store_name(db)


class EmailTemplateAdminService:
    """List, read, create, update and delete email templates.

    The list is seeded from ``default_email_templates()`` rather than from the
    table, so a store with no rows still shows the four transactional emails
    its code already sends. That is also why updating one writes a row: the
    built-in is the fallback, a row is the override.
    """

    @staticmethod
    async def list_templates(
        db: AsyncSession, *, channel: str = "email"
    ) -> list[dict[str, Any]]:
        from app.modules.notifications.domain.models import NotificationTemplate

        rows = (
            await db.execute(
                select(NotificationTemplate).where(
                    NotificationTemplate.channel == channel
                )
            )
        ).scalars().all()
        overrides = {r.name: r for r in rows}

        items: list[dict[str, Any]] = []
        for name, content in default_email_templates().items():
            row = overrides.pop(name, None)
            items.append(
                {
                    "name": name,
                    "channel": channel,
                    "subject": (row.subject if row else content.subject),
                    "body_template": (row.body_template if row else content.html),
                    "text_template": (row.body_template if row else content.text),
                    "variables": (
                        row.variables if row and row.variables else content.variables
                    ),
                    "is_custom": row is not None,
                }
            )
        # Templates created outside the built-in set. They would otherwise be
        # invisible, and a store that added one would wonder where it went.
        for name, row in overrides.items():
            items.append(
                {
                    "name": name,
                    "channel": row.channel.value if hasattr(row.channel, "value") else str(row.channel),
                    "subject": row.subject,
                    "body_template": row.body_template,
                    "text_template": None,
                    "variables": row.variables or [],
                    "is_custom": True,
                }
            )
        items.sort(key=lambda t: t["name"])
        return items

    @staticmethod
    async def get_template(db: AsyncSession, name: str) -> dict[str, Any]:
        from app.modules.notifications.domain.models import NotificationTemplate

        row = (
            await db.execute(
                select(NotificationTemplate).where(NotificationTemplate.name == name)
            )
        ).scalar_one_or_none()
        if row is not None:
            return {
                "name": row.name,
                "channel": row.channel.value if hasattr(row.channel, "value") else str(row.channel),
                "subject": row.subject,
                "body_template": row.body_template,
                "text_template": None,
                "variables": row.variables or [],
                "is_custom": True,
            }
        built_in = default_email_templates(await _operator_store_name(db)).get(name)
        if built_in is None:
            raise NotFoundError("NotificationTemplate", f"Template {name} not found")
        return {
            "name": name,
            "channel": "email",
            "subject": built_in.subject,
            "body_template": built_in.html,
            "text_template": built_in.text,
            "variables": built_in.variables,
            "is_custom": False,
        }

    @staticmethod
    async def upsert_template(
        db: AsyncSession,
        name: str,
        *,
        subject: str | None,
        body_template: str,
        variables: list[str] | None = None,
    ) -> dict[str, Any]:
        from app.modules.notifications.domain.models import (
            NotificationChannel,
            NotificationTemplate,
        )

        clean_name = (name or "").strip()
        if not _VARIABLE_NAME.match(clean_name) or len(clean_name) > 100:
            raise ValidationError(
                "نام قالب باید حروف انگلیسی، عدد و زیرخط باشد و حداکثر ۱۰۰ کاراکتر"
            )
        if subject is not None and len(subject) > MAX_SUBJECT_LENGTH:
            raise ValidationError(
                f"موضوع حداکثر {MAX_SUBJECT_LENGTH} کاراکتر است"
            )
        body = sanitize_email_template(body_template)
        declared = validate_variables(variables)
        used = variables_used(body, subject)
        # A variable the body uses but nobody declared cannot be supplied, so
        # the render would silently produce an empty string in the customer's
        # inbox. Refusing the save is louder and cheaper.
        undeclared = [v for v in used if v not in declared]
        if undeclared:
            raise ValidationError(
                "این متغیرها در متن استفاده شده‌اند ولی اعلام نشده‌اند: "
                + "، ".join(undeclared),
                extra={"undeclared": undeclared},
            )

        row = (
            await db.execute(
                select(NotificationTemplate).where(NotificationTemplate.name == clean_name)
            )
        ).scalar_one_or_none()
        if row is None:
            row = NotificationTemplate(name=clean_name, channel=NotificationChannel.EMAIL)
            db.add(row)
        row.subject = subject
        row.body_template = body
        row.variables = declared
        await db.commit()
        await db.refresh(row)
        logger.info(
            "email_template_saved",
            name=clean_name,
            variables=len(declared),
        )
        return {
            "name": row.name,
            "channel": "email",
            "subject": row.subject,
            "body_template": row.body_template,
            "text_template": None,
            "variables": row.variables or [],
            "is_custom": True,
        }

    @staticmethod
    async def delete_template(db: AsyncSession, name: str) -> bool:
        """Drop the override, returning the template to the built-in.

        Not a delete of the ability to send it: the built-in in the code is the
        fallback, so removing the row restores the original wording rather than
        leaving the flow without a template.
        """
        from app.modules.notifications.domain.models import NotificationTemplate

        row = (
            await db.execute(
                select(NotificationTemplate).where(NotificationTemplate.name == name)
            )
        ).scalar_one_or_none()
        if row is None:
            return False
        await db.delete(row)
        await db.commit()
        logger.info("email_template_reset", name=name)
        return True

    async def preview(
        db: AsyncSession,
        name: str,
        *,
        subject: str | None,
        body_template: str,
        variables: list[str] | None,
    ) -> dict[str, str]:
        """Render a template with placeholder values, for the preview pane.

        The body is validated exactly as on save, so the preview cannot show
        something the save would refuse.

        ``db`` is used for exactly one thing: the header's store name. The preview
        used to fill ``store_name`` from a hardcoded sample ("فروشگاه نمونه"), so
        an operator editing a template saw a preview headed with a placeholder
        while the customer's copy said their own name — and a store that had
        named itself differently could not tell from the preview that the header
        was wired to anything at all.
        """
        from app.shared.content.text_filters import wp_staticize_emoji, wptexturize

        body = sanitize_email_template(body_template)
        declared = validate_variables(variables)
        samples = {
            # Not a literal. The preview's job is to show the operator what the
            # customer will see, and the header is the one part of the email that
            # is not a placeholder — it is the store's own name, resolved the
            # same way the send path resolves it.
            "store_name": await _operator_store_name(db),
            "order_number": "۱۴۰۴-۰۰۱۲۳",
            "order_id": "12345",
            "customer_name": "مشتری نمونه",
            "amount": "۱٬۲۵۰٬۰۰۰ تومان",
            "total": "۱٬۲۵۰٬۰۰۰ تومان",
            "tracking_code": "IR123456789",
            "tracking_url": "https://post.example.com/t/IR123456789",
            "refund_amount": "۲۵۰٬۰۰۰ تومان",
            "product_name": "نام محصول",
            "quantity": "۲",
            "link": "https://example.com",
            "code": "123456",
            "minutes": "۱۵",
        }
        values = {name: samples.get(name, f"{{{name}}}") for name in declared}

        def fill(text: str) -> str:
            out = text
            for key, value in values.items():
                out = out.replace("{{" + key + "}}", value)
            # A variable the author typed with spaces around the name is still
            # filled, because send_from_template accepts that spelling.
            for key, value in values.items():
                out = re.sub(r"\{\{\s*" + re.escape(key) + r"\s*\}\}", value, out)
            return out

        rendered_subject = fill(subject or "")
        # The header and every `{{store_name}}` in the body read one variable, so
        # they cannot disagree with each other. It is the resolved name, not a
        # sample — see `samples` above — which is what makes the preview a
        # preview rather than a mock-up.
        store_name = values.get("store_name") or await _operator_store_name(db)
        return {
            "subject": wptexturize(rendered_subject) if rendered_subject else "",
            "html": _wrap_html(store_name, fill(body)),
            "variables": ", ".join(declared) if declared else "—",
        }


async def resolve_template(
    db: AsyncSession, name: str
) -> "EmailTemplateContent":
    """The template to actually send: the stored override, or the built-in.

    Every transactional caller needs this and none of them had it: they called
    ``default_email_templates()`` directly, which reads the literals in the code
    and can never see a row in ``notification_templates``. So the admin editor
    saved a change that no real email would ever have used — the CRUD was real,
    the effect was not.

    This is the whole point of the table existing. DB first, code as the
    fallback, and a missing row is not an error: a store that never edited a
    template sends the built-in one.
    """
    from sqlalchemy import select

    from app.modules.notifications.domain.models import NotificationTemplate

    row = (
        await db.execute(
            select(NotificationTemplate).where(NotificationTemplate.name == name)
        )
    ).scalar_one_or_none()
    built_in = default_email_templates(await _operator_store_name(db)).get(name)
    if row is None:
        if built_in is None:
            raise NotFoundError("EmailTemplate", f"No email template named {name!r}")
        return built_in
    # A row stores one body. When the editor also saved a plain-text part it is
    # kept alongside; otherwise the built-in text is used if there is one for
    # this name, and the subject falls back the same way.
    return EmailTemplateContent(
        subject=row.subject or (built_in.subject if built_in else name),
        html=row.body_template,
        text=(built_in.text if built_in else _strip_tags(row.body_template)),
        variables=list(row.variables or []),
    )


def _strip_tags(html: str) -> str:
    """A plain-text body from an HTML one, for clients that render neither.

    Deliberately crude and deliberately not a parser: the alternative is
    shipping an empty text part, which reads as a broken email to a text-only
    client rather than as a slightly ugly one.
    """
    import re

    text = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    text = re.sub(r"</(p|div|tr|h[1-6])>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


# Imported at the end so the module docstring can describe them without a
# circular import through the notifications package.
from app.modules.notifications.application.email_service import (  # noqa: E402
    EmailTemplateContent,
    _wrap_html,
    default_email_templates,
)

__all__ = [
    "EmailTemplateAdminService",
    "resolve_template",
    "sanitize_email_template",
    "validate_variables",
    "variables_used",
]
