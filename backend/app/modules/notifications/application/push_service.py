"""Web Push (VAPID) delivery service shell for the notifications module.

**Dependency gap (deferred):** real Web Push encryption/transport needs the
``pywebpush`` package, which is NOT in ``pyproject.toml`` and was not added
(scope decision for v1). This module therefore ships everything except the
final HTTP dispatch:

- :class:`PushConfig` resolution from settings (+ admin runtime overrides),
- the :class:`PushSubscription` persistence path used by the browser
  subscribe/unsubscribe endpoints (see ``notifications/api/routes.py``),
- :func:`send_push_notification` with the exact same
  disabled-when-unconfigured semantics as email/telegram: when pywebpush is
  missing or VAPID keys are blank it logs a warning and reports the
  simulated fallback instead of raising, so dispatch callers never branch.

To go live: add ``pywebpush`` to the backend dependencies, set
``VAPID_PUBLIC_KEY`` / ``VAPID_PRIVATE_KEY`` (generate with
``pywebpush gen-vapid`` or ``npx web-push generate-vapid-keys``), and the
provider flips to real dispatch with no further code changes — the VAPID
payload, TTL and subscription lookup below are already production-shaped.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import delete, select

from app.core.config.settings import get_settings

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.notifications.domain.models import PushSubscription

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# pywebpush is deliberately optional (see module docstring): import it at
# dispatch time so the rest of the module (and its tests) import cleanly
# without the package installed.
try:  # pragma: no cover - exercised implicitly in environments with pywebpush
    import pywebpush as _pywebpush_mod
except ImportError:  # expected today
    _pywebpush_mod = None  # type: ignore[assignment]

PYWEBPUSH_AVAILABLE = _pywebpush_mod is not None


class PushConfigurationError(Exception):
    """Raised when a real push send is attempted without complete VAPID settings."""


@dataclass(frozen=True)
class PushConfig:
    """Resolved VAPID web-push settings for one dispatch."""

    vapid_public_key: str = ""
    vapid_private_key: str = ""
    vapid_subject: str = "mailto:support@site.com"
    timeout_seconds: int = 15

    @property
    def has_keys(self) -> bool:
        return bool(self.vapid_public_key.strip()) and bool(self.vapid_private_key.strip())

    @property
    def is_configured(self) -> bool:
        """Real dispatch needs keys AND the (currently missing) pywebpush package."""
        return self.has_keys and PYWEBPUSH_AVAILABLE


@dataclass(frozen=True)
class PushSendResult:
    """Outcome of one web-push dispatch to a single subscription."""

    success: bool
    endpoint: str = ""
    response: str = ""
    error: str | None = None
    # True when the push service reported the subscription as gone (HTTP 404/410)
    # — callers must delete the subscription row so it is never retried.
    subscription_expired: bool = False


def get_push_config(runtime_overrides: dict[str, Any] | None = None) -> PushConfig:
    """Build the effective web-push configuration.

    Environment settings are the base; a ``push`` group row from the
    site-settings store may override individual fields (admin UI edits).
    Only non-empty override values win, and secrets are never logged here.
    """
    s = get_settings()
    base: dict[str, Any] = {
        "vapid_public_key": s.VAPID_PUBLIC_KEY,
        "vapid_private_key": s.VAPID_PRIVATE_KEY,
        "vapid_subject": s.VAPID_SUBJECT,
        "timeout_seconds": s.PUSH_TIMEOUT_SECONDS,
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
            elif str(value).strip() != "" or key == "vapid_private_key":
                base[key] = str(value)
    return PushConfig(**base)


# ── Subscription persistence ──────────────────────────────────────────────


async def save_subscription(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    endpoint: str,
    keys: dict[str, Any],
    user_agent: str | None = None,
) -> "PushSubscription":
    """Upsert a browser push subscription (dedupe by endpoint).

    Re-subscribing the same browser refreshes the keys and owner instead of
    inserting a duplicate row.
    """
    from app.modules.notifications.domain.models import PushSubscription

    endpoint = endpoint.strip()
    sub = (
        await db.execute(
            select(PushSubscription).where(PushSubscription.endpoint == endpoint)
        )
    ).scalar_one_or_none()
    if sub is None:
        sub = PushSubscription(
            user_id=user_id, endpoint=endpoint, keys=keys, user_agent=user_agent
        )
        db.add(sub)
    else:
        sub.user_id = user_id
        sub.keys = keys
        if user_agent:
            sub.user_agent = user_agent
    await db.flush()
    await logger.ainfo("push_subscription_saved", user_id=str(user_id))
    return sub


async def delete_subscription(db: AsyncSession, *, user_id: uuid.UUID, endpoint: str) -> bool:
    """Remove a subscription owned by the user (browser unsubscribe)."""
    from app.modules.notifications.domain.models import PushSubscription

    result = await db.execute(
        delete(PushSubscription).where(
            PushSubscription.endpoint == endpoint.strip(),
            PushSubscription.user_id == user_id,
        )
    )
    await db.flush()
    removed = int(getattr(result, "rowcount", 0) or 0) > 0
    if removed:
        await logger.ainfo("push_subscription_deleted", user_id=str(user_id))
    return removed


async def get_user_subscriptions(
    db: AsyncSession, user_id: uuid.UUID
) -> list["PushSubscription"]:
    """All active subscriptions for a user (one per browser/device)."""
    from app.modules.notifications.domain.models import PushSubscription

    rows = await db.execute(
        select(PushSubscription).where(PushSubscription.user_id == user_id)
    )
    return list(rows.scalars().all())


# ── Dispatch ──────────────────────────────────────────────────────────────


def build_push_payload(title: str, body: str, data: dict[str, Any] | None = None) -> str:
    """JSON payload delivered to the service worker's ``push`` event."""
    return json.dumps({"title": title, "body": body, "data": data or {}}, ensure_ascii=False)


async def _send_one(
    *, config: PushConfig, endpoint: str, keys: dict[str, Any], payload: str
) -> PushSendResult:
    """Real dispatch of one payload to one subscription via pywebpush."""
    import asyncio

    def _send_sync() -> Any:
        return _pywebpush_mod.webpush(  # type: ignore[union-attr]
            subscription_info={"endpoint": endpoint, "keys": keys},
            data=payload,
            vapid_private_key=config.vapid_private_key,
            vapid_claims={"sub": config.vapid_subject},
            timeout=config.timeout_seconds,
        )

    try:
        resp = await asyncio.to_thread(_send_sync)
        return PushSendResult(
            success=True,
            endpoint=endpoint,
            response=f"{getattr(resp, 'status_code', 201)} accepted",
        )
    except Exception as exc:  # pywebpush raises WebPushException
        status_code = getattr(getattr(exc, "response", None), "status_code", None)
        expired = status_code in (404, 410)
        await logger.aerror(
            "webpush_send_failed", endpoint=endpoint[:80], status_code=status_code, error=str(exc)
        )
        return PushSendResult(
            success=False,
            endpoint=endpoint,
            response=f"{status_code or 'error'}",
            error=f"{type(exc).__name__}: {exc}",
            subscription_expired=expired,
        )


async def send_push_notification(
    db: AsyncSession | None,
    *,
    user_id: uuid.UUID,
    title: str,
    body: str,
    data: dict[str, Any] | None = None,
    config: PushConfig | None = None,
) -> tuple[bool, int]:
    """Send a web push to every subscription of the user.

    Returns ``(any_success, delivered_count)``. Disabled-when-unconfigured:
    with missing keys or missing pywebpush the function logs a warning and
    returns ``(True, 0)`` — the simulated-fallback semantics email and
    telegram share — so dispatch callers keep working in development and
    the capability registry can report the channel as MOCK.
    """
    effective = config or get_push_config()

    if not effective.is_configured:
        reason = (
            "VAPID keys missing"
            if not effective.has_keys
            else "pywebpush package not installed (dependency gap)"
        )
        await logger.awarning(
            "webpush_not_configured_mock_fallback",
            user_id=str(user_id),
            title=title,
            reason=reason,
        )
        return True, 0

    if db is None:
        return False, 0

    subscriptions = await get_user_subscriptions(db, user_id)
    if not subscriptions:
        await logger.ainfo("webpush_skipped_no_subscriptions", user_id=str(user_id))
        return False, 0

    payload = build_push_payload(title, body, data)
    delivered = 0
    for sub in subscriptions:
        result = await _send_one(
            config=effective, endpoint=sub.endpoint, keys=sub.keys or {}, payload=payload
        )
        if result.success:
            delivered += 1
        elif result.subscription_expired:
            # The push service says this subscription is dead; drop it so we
            # never pay for (or log) the same failure twice.
            from app.modules.notifications.domain.models import PushSubscription

            await db.execute(
                delete(PushSubscription).where(PushSubscription.id == sub.id)
            )
            await db.flush()
    return delivered > 0, delivered
