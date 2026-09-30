"""Telegram Bot API delivery service for the notifications module.

Real outbound Telegram messages replacing the development mock, wired into
the existing channel abstraction (mirror of ``email_service.py``):

- Transport is the Telegram Bot API ``sendMessage`` endpoint over HTTPS via
  ``httpx`` (already a project dependency — no new package).
- One retry on transient failures (HTTP 429 / 5xx and network errors);
  permanent 4xx failures (bad chat_id, blocked bot) are not retried.
- Every dispatch writes a :class:`TelegramDeliveryLog` row (queued →
  sent/failed) so ops can audit delivery without reading worker logs.
- Disabled-when-unconfigured: with a blank ``TELEGRAM_BOT_TOKEN`` the
  service logs a warning and falls back to the previous mock behavior
  (records the log row as SENT with a simulated marker, never raises) so
  existing callers keep working in development.

Per-user delivery target (chat_id) flow
---------------------------------------
Telegram bots cannot initiate a conversation — the user must message the
bot first, which is how the bot learns their chat_id. The link flow:

1. The user opens their account page (frontend: account dashboard,
   notifications tab) and requests a link code:
   ``POST /notifications/telegram/link-code``. The backend stores a
   single-use 8-character code on ``notification_preferences`` with a
   10-minute expiry and shows it to the user together with the bot's
   deep link ``https://t.me/<bot_username>``.
2. The user opens the bot and sends the code (e.g. ``/start <code>`` or a
   plain message containing it).
3. The bot side must call back into the platform to bind the code to the
   sender's chat_id. **Deferred (out of scope for v1):** a webhook/long-poll
   consumer for Telegram ``getUpdates``. The webhook endpoint would receive
   updates, extract ``message.chat.id`` + the code from ``message.text``,
   and call the same ``confirm_telegram_link`` service function below.
   Shipping that endpoint means exposing a publicly reachable URL with its
   own secret-token verification surface; instead v1 ships:
   - the account-side code generation (route + service), and
   - an admin manual-link endpoint (``POST /notifications/admin/telegram/link``)
     that binds a code to a chat_id an operator reads from the bot's
     messages — exactly the operation the future webhook will automate.
   ``confirm_telegram_link`` is the single entry point both paths use, so
   adding the webhook later is a thin HTTP adapter with no service changes.
4. Unlinking (``DELETE /notifications/telegram/link``) clears chat_id so no
   further Telegram messages are attempted for the user.
"""

from __future__ import annotations

import asyncio
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import httpx
import structlog
from sqlalchemy import select

from app.core.config.settings import get_settings

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.notifications.domain.models import TelegramDeliveryLog

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# Telegram Bot API: 429 (rate limited) and 5xx are transient — retry once.
# Other 4xx (400 bad chat_id, 403 bot blocked) are permanent.
_TRANSIENT_HTTP_STATUSES = frozenset({429, 500, 502, 503, 504})

_LINK_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I ambiguity
_LINK_CODE_LENGTH = 8
_LINK_CODE_TTL = timedelta(minutes=10)


class TelegramConfigurationError(Exception):
    """Raised when a real send is attempted without a bot token."""


@dataclass(frozen=True)
class TelegramConfig:
    """Resolved Telegram settings for one dispatch (env, runtime-overridable)."""

    bot_token: str = ""
    bot_username: str = ""
    api_base_url: str = "https://api.telegram.org"
    timeout_seconds: int = 15

    @property
    def is_configured(self) -> bool:
        """The bot token is the only hard requirement for a real dispatch."""
        return bool(self.bot_token.strip())


@dataclass(frozen=True)
class TelegramSendResult:
    """Outcome of one Telegram dispatch attempt chain."""

    success: bool
    response: str = ""
    attempts: int = 1
    transient_retry: bool = False
    error: str | None = None


def get_telegram_config(runtime_overrides: dict[str, Any] | None = None) -> TelegramConfig:
    """Build the effective Telegram configuration.

    Environment settings are the base; a ``telegram`` group row from the
    site-settings store may override individual fields (admin UI edits).
    Only non-empty override values win, and secrets are never logged here.
    """
    s = get_settings()
    base: dict[str, Any] = {
        "bot_token": s.TELEGRAM_BOT_TOKEN,
        "bot_username": s.TELEGRAM_BOT_USERNAME,
        "api_base_url": s.TELEGRAM_API_BASE_URL,
        "timeout_seconds": s.TELEGRAM_TIMEOUT_SECONDS,
    }
    if runtime_overrides:
        for key in base:
            value = runtime_overrides.get(key)
            if value is None:
                continue
            if isinstance(base[key], int):
                try:
                    base[key] = int(value)
                except (TypeError, ValueError):
                    continue
            elif str(value).strip() != "" or key == "bot_token":
                base[key] = str(value)
    return TelegramConfig(**base)


def build_message_text(title: str, body: str) -> str:
    """Compose the plain-text message: bold title line, then the body.

    Telegram's 4096-char message cap is enforced by truncation (a store
    notification body is short, but a template regression must not turn
    into a provider rejection).
    """
    text = f"{title}\n\n{body}" if title else body
    return text[:4096]


async def _attempt_send(
    *,
    config: TelegramConfig,
    chat_id: str,
    text: str,
) -> dict[str, Any]:
    """One Bot API ``sendMessage`` call.

    Returns the decoded ``result`` object on success; raises
    ``httpx.HTTPStatusError`` for non-2xx and ``httpx.TransportError`` for
    network failures so the caller can classify retryability.
    """
    url = f"{config.api_base_url.rstrip('/')}/bot{config.bot_token}/sendMessage"
    async with httpx.AsyncClient(timeout=config.timeout_seconds) as client:
        resp = await client.post(
            url,
            json={"chat_id": chat_id, "text": text},
        )
        resp.raise_for_status()
        payload = resp.json()
    if not payload.get("ok"):
        # Telegram returns 200 with ok=false only in edge cases; treat as
        # permanent failure with the description surfaced for the log.
        raise TelegramConfigurationError(
            f"Bot API returned ok=false: {payload.get('description', 'unknown')}"
        )
    return payload.get("result") or {}


async def send_telegram(
    *,
    config: TelegramConfig,
    chat_id: str,
    title: str,
    body: str,
) -> TelegramSendResult:
    """Send one Telegram message, retrying once on transient failures.

    Never raises for delivery problems — the outcome is reported in the
    returned :class:`TelegramSendResult` so the caller can persist it.
    """
    if not config.is_configured:
        raise TelegramConfigurationError("Telegram is not configured (bot token missing)")
    if not chat_id.strip():
        return TelegramSendResult(
            success=False, error="no chat_id: user has not linked Telegram"
        )

    text = build_message_text(title, body)
    attempts = 0
    retried = False
    while True:
        attempts += 1
        try:
            result = await _attempt_send(config=config, chat_id=chat_id, text=text)
            message_id = result.get("message_id", "?")
            return TelegramSendResult(
                success=True,
                response=f"ok: message_id={message_id}",
                attempts=attempts,
                transient_retry=retried,
            )
        except httpx.HTTPStatusError as exc:
            code = exc.response.status_code
            description = ""
            try:
                description = str(exc.response.json().get("description", ""))
            except Exception:  # noqa: BLE001 - description is best-effort
                description = exc.response.text[:200]
            if code in _TRANSIENT_HTTP_STATUSES and not retried:
                retried = True
                await logger.awarning(
                    "telegram_transient_retry",
                    chat_id=chat_id,
                    http_status=code,
                    attempt=attempts,
                )
                await asyncio.sleep(0.5)
                continue
            await logger.aerror(
                "telegram_api_rejected",
                chat_id=chat_id,
                http_status=code,
                attempts=attempts,
            )
            return TelegramSendResult(
                success=False,
                response=f"{code} {description}",
                attempts=attempts,
                transient_retry=retried,
                error=f"HTTP {code}: {description}",
            )
        except (httpx.TransportError, TelegramConfigurationError) as exc:
            await logger.aerror(
                "telegram_transport_failed",
                chat_id=chat_id,
                error=str(exc),
                attempts=attempts,
            )
            return TelegramSendResult(
                success=False,
                attempts=attempts,
                transient_retry=retried,
                error=f"{type(exc).__name__}: {exc}",
            )


# ── Persistence-aware dispatch ────────────────────────────────────────────


async def send_telegram_message(
    db: AsyncSession | None,
    *,
    chat_id: str,
    title: str,
    body: str,
    notification_id: Any | None = None,
    config: TelegramConfig | None = None,
) -> tuple[bool, "TelegramDeliveryLog | None"]:
    """Dispatch one Telegram message and persist its delivery log row.

    Returns ``(success, log_row)``. The log row is best-effort: when no
    session is available (or persistence itself fails) the message is still
    attempted and ``log_row`` is ``None``.
    """
    from app.modules.notifications.domain.models import (
        TelegramDeliveryLog,
        TelegramDeliveryStatus,
    )

    effective = config or get_telegram_config()

    log_row: TelegramDeliveryLog | None = None
    if db is not None:
        try:
            log_row = TelegramDeliveryLog(
                notification_id=notification_id,
                recipient=chat_id or "",
                title=title[:500],
                status=TelegramDeliveryStatus.QUEUED,
                provider="telegram_bot" if effective.is_configured else "mock_fallback",
            )
            db.add(log_row)
            await db.flush()
        except Exception:
            await logger.awarning("telegram_delivery_log_persist_failed", chat_id=chat_id)
            log_row = None

    if not effective.is_configured:
        # Disabled-when-unconfigured: preserve the old mock behavior — log
        # loudly and report success so callers (outbox, order flows) are
        # unaffected, but leave an auditable trail that nothing was sent.
        await logger.awarning(
            "telegram_not_configured_mock_fallback",
            chat_id=chat_id,
            title=title,
        )
        if log_row is not None:
            log_row.status = TelegramDeliveryStatus.SENT
            log_row.attempts = 0
            log_row.provider_response = "SIMULATED: Telegram bot token not configured (mock fallback)"
            await db.flush()  # type: ignore[union-attr]
        return True, log_row

    result = await send_telegram(config=effective, chat_id=chat_id, title=title, body=body)

    if log_row is not None:
        log_row.attempts = result.attempts
        log_row.provider_response = result.response or None
        if result.success:
            log_row.status = TelegramDeliveryStatus.SENT
            log_row.sent_at = datetime.now(UTC)
        else:
            log_row.status = TelegramDeliveryStatus.FAILED
            log_row.error = (result.error or "unknown Telegram error")[:2000]
        await db.flush()  # type: ignore[union-attr]

    if result.success:
        await logger.ainfo("telegram_sent", chat_id=chat_id, title=title, attempts=result.attempts)
    return result.success, log_row


# ── Account linking (verification-code flow) ──────────────────────────────


async def generate_link_code(db: AsyncSession, user_id: uuid.UUID) -> tuple[str, datetime]:
    """Create (or rotate) the single active Telegram link code for a user.

    Returns ``(code, expires_at)``. Generating a new code invalidates the
    previous one by overwrite — only one outstanding link attempt per user.
    """
    from app.modules.notifications.domain.models import NotificationPreference

    pref = (
        await db.execute(
            select(NotificationPreference).where(NotificationPreference.user_id == user_id)
        )
    ).scalar_one_or_none()
    if pref is None:
        pref = NotificationPreference(user_id=user_id)
        db.add(pref)

    code = "".join(secrets.choice(_LINK_CODE_ALPHABET) for _ in range(_LINK_CODE_LENGTH))
    expires_at = datetime.now(UTC) + _LINK_CODE_TTL
    pref.telegram_link_code = code
    pref.telegram_link_code_expires_at = expires_at
    await db.flush()
    await logger.ainfo("telegram_link_code_generated", user_id=str(user_id))
    return code, expires_at


async def confirm_telegram_link(
    db: AsyncSession, *, code: str, chat_id: str
) -> tuple[bool, uuid.UUID | None]:
    """Bind a chat_id to the user holding ``code``.

    Returns ``(linked, user_id)``. The code is consumed (cleared) on any
    outcome other than "no such code", so a leaked/guessed code cannot be
    replayed. This is THE binding entry point — the deferred bot webhook
    and the admin manual-link endpoint both call this function.
    """
    from app.modules.notifications.domain.models import NotificationPreference

    normalized = (code or "").strip().upper()
    if not normalized:
        return False, None
    pref = (
        await db.execute(
            select(NotificationPreference).where(
                NotificationPreference.telegram_link_code == normalized
            )
        )
    ).scalar_one_or_none()
    if pref is None:
        return False, None

    expires_at = pref.telegram_link_code_expires_at
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    expired = expires_at is None or datetime.now(UTC) > expires_at

    # Consume the code regardless of expiry so it can never be replayed.
    pref.telegram_link_code = None
    pref.telegram_link_code_expires_at = None
    if expired:
        await db.flush()
        await logger.awarning("telegram_link_code_expired", user_id=str(pref.user_id))
        return False, None

    pref.telegram_chat_id = str(chat_id).strip()
    await db.flush()
    await logger.ainfo(
        "telegram_account_linked", user_id=str(pref.user_id), chat_id=pref.telegram_chat_id
    )
    return True, pref.user_id


async def unlink_telegram(db: AsyncSession, user_id: uuid.UUID) -> bool:
    """Clear the stored chat_id so no further Telegram sends are attempted."""
    from app.modules.notifications.domain.models import NotificationPreference

    pref = (
        await db.execute(
            select(NotificationPreference).where(NotificationPreference.user_id == user_id)
        )
    ).scalar_one_or_none()
    if pref is None or not pref.telegram_chat_id:
        return False
    pref.telegram_chat_id = None
    await db.flush()
    await logger.ainfo("telegram_account_unlinked", user_id=str(user_id))
    return True
