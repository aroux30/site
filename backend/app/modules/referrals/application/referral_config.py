"""Referral & bonus configuration: one ``SiteSetting`` row holding the whole program.

Ported from the VPN project's per-reseller referral/bonus settings (the owner's
reference implementation), collapsed into a single JSONB row (key
``referrals.config``, group ``referrals``) following the same pattern as
``chat.widget``.

Money values are integer Rial (ADR-012). Percent values are percent-unit with
up to two decimals (1.25 = 1.25%, 0.01 = 0.01%) — stored in the config as
given, but all money math converts them to integer basis points (1% = 100 bp)
via :func:`percent_to_bp` and then stays in the integer domain. This mirrors
the cashback module's ``percentage_bp`` convention.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import select

from app.modules.settings.domain.models import SiteSetting

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger()

CONFIG_KEY = "referrals.config"
CONFIG_GROUP = "referrals"

#: Default program config. **Every payout amount defaults to 0** — the
#: program is installed but pays nothing until an operator sets the amounts
#: from the admin panel. This is deliberate: the store already holds pending
#: referrals from before the feature existed, and defaults above zero would
#: retroactively pay them the moment the first sweep runs.
DEFAULT_CONFIG: dict[str, Any] = {
    "enabled": True,
    # ── Per-module switches (independent of the master `enabled`) ──────
    # An operator may want commissions on but signup gifts off (or any
    # other combination); each module gates its own payout path. The
    # master switch above still kills everything at once.
    "gift_enabled": True,
    "commission_enabled": True,
    "recharge_bonus_enabled": True,
    # Fixed gift credited to the REFERRER's wallet when someone signs up
    # with their code (0 = off). Two levels, mirroring the reference.
    "signup_gift_l1": 0,
    "signup_gift_l2": 0,
    # Percentage commission on each COMPLETED order by a referred buyer.
    "commission_percent_l1": 0,
    "commission_percent_l2": 0,
    # Cap per single commission event in Rial (0 = no cap).
    "commission_max_per_event": 0,
    # Commissions only apply to orders with total >= this (0 = all orders).
    "min_order_total": 0,
    # Notifications to the earner.
    "notify_on_gift": True,
    "notify_on_commission": True,
    # ISO timestamp of the current activation: set the first time the
    # program turns on, and refreshed on every re-activation (off → on).
    # Only referrals/orders created at or after this moment earn rewards —
    # the live store holds pre-existing pending referrals and historical
    # completed orders, and paying those retroactively would be a surprise
    # payout. Refreshing on re-activation is what keeps the off period from
    # being paid when the program comes back on. None = never activated;
    # sweeps pay nothing.
    "program_started_at": None,
    # Recharge bonus: percent credited on wallet top-ups (0 = off).
    "recharge_bonus_percent": 0,
    "notify_on_recharge_bonus": True,
    # Notification templates ({amount} is pre-formatted in Toman).
    "gift_notif_text": (
        "🎁 یک کاربر با لینک دعوت شما عضو شد و مبلغ {amount} تومان "
        "به عنوان پاداش ثبت‌نام به کیف پول شما اضافه شد."
    ),
    "commission_notif_text": (
        "🎁 کاربری که با لینک شما عضو شده بود خریدی انجام داد و مبلغ "
        "{amount} تومان به عنوان پورسانت به کیف پول شما اضافه شد."
    ),
    "recharge_bonus_notif_text": (
        "🎁 بونوس شارژ کیف پول: مبلغ {amount} تومان به کیف پول شما اضافه شد."
    ),
}

#: Percent keys — stored with up to two decimals, clamped 0..100 on write.
_PERCENT_KEYS = ("commission_percent_l1", "commission_percent_l2", "recharge_bonus_percent")
#: Non-negative integer keys (Rial amounts).
_AMOUNT_KEYS = ("signup_gift_l1", "signup_gift_l2", "commission_max_per_event", "min_order_total")


def percent_to_bp(value: Any) -> int:
    """Percent (up to 2 decimals) → integer basis points (1% = 100 bp).

    The single conversion point from the human percent unit to the integer
    money domain; every payout computation calls this and then stays in
    integers. Two decimals max (0.001 rounds to 0 bp) — the UI offers the
    same precision.
    """
    try:
        # Parse via str so float noise ("1.25" → 1.2499999) cannot drop a bp.
        text = str(value).strip()
        return max(0, min(10_000, round(float(text) * 100)))
    except (TypeError, ValueError):
        return 0


def bp_to_percent(bp: int) -> float:
    """Integer basis points → percent float for display (125 bp → 1.25)."""
    return bp / 100


def _merged(stored: dict[str, Any] | None) -> dict[str, Any]:
    """Stored config on top of the defaults (missing keys keep their default)."""
    merged = dict(DEFAULT_CONFIG)
    if isinstance(stored, dict):
        merged.update(stored)
    return merged


def _coerce(config: dict[str, Any]) -> dict[str, Any]:
    """Normalise numeric fields: percents clamped 0..100 (2 decimals), amounts >= 0."""
    for key in _PERCENT_KEYS:
        try:
            value = round(float(str(config.get(key, 0)).strip()), 2)
        except (TypeError, ValueError):
            value = 0.0
        config[key] = max(0.0, min(100.0, value))
    for key in _AMOUNT_KEYS:
        try:
            value = int(config.get(key, 0))
        except (TypeError, ValueError):
            value = 0
        config[key] = max(0, value)
    return config


#: Template keys that end up in user-facing notifications (in-app and SMS).
_TEXT_KEYS = ("gift_notif_text", "commission_notif_text", "recharge_bonus_notif_text")

#: Anything that looks like an HTML tag. Templates are plain text — the
#: notification pipeline may deliver them through SMS, where markup shows up
#: literally, and storing tags is the first half of a stored-XSS chain if any
#: future renderer stops escaping. Strip at the API boundary; the UI input
#: stays a plain text field.
_TAG_RE = re.compile(r"<[^>]*>")


def _sanitize_templates(config: dict[str, Any]) -> None:
    """Strip HTML tags from the notification template fields, in place.

    Defense-in-depth at the write boundary: the current renderers escape
    (React text nodes; SMS is plain text), so this does not fix an exploitable
    hole today — it removes the payload from storage so no future renderer
    (email HTML, Telegram parse_mode, a raw innerHTML table) can resurrect it.
    """
    for key in _TEXT_KEYS:
        value = config.get(key)
        if isinstance(value, str) and "<" in value:
            config[key] = _TAG_RE.sub("", value)


def _reject_extra_decimals(incoming: dict[str, Any]) -> None:
    """Refuse percent values with more than two decimals.

    The UI already blocks a third decimal digit; this is the server-side
    gate for direct API calls — a value like 1.257 is a client bug or a
    manual call, and silently rounding it would make the stored number
    differ from what the caller sent. Fail loudly instead.

    The check uses ``Decimal``'s exponent (exact), not float arithmetic —
    ``1.26 * 100`` in binary floating point is not exactly 126 and a
    float-based check would wrongly reject valid two-decimal values.
    """
    from decimal import Decimal, InvalidOperation

    from app.core.exceptions.handlers import ValidationError

    for key in _PERCENT_KEYS:
        if key not in incoming:
            continue
        raw = incoming[key]
        try:
            value = Decimal(str(raw).strip())
        except (InvalidOperation, TypeError, ValueError):
            raise ValidationError(
                detail="مقدار درصد باید یک عدد باشد.",
                error_code="REFERRAL_PERCENT_INVALID",
            ) from None
        if not value.is_finite() or value.as_tuple().exponent < -2:
            raise ValidationError(
                detail="درصد حداکثر تا دو رقم اعشار قابل ثبت است (مثال: ۱.۲۵).",
                error_code="REFERRAL_PERCENT_PRECISION",
            )


async def get_config(db: AsyncSession) -> dict[str, Any]:
    """Return the full config (defaults + stored, coerced)."""
    row = (
        await db.execute(select(SiteSetting).where(SiteSetting.key == CONFIG_KEY))
    ).scalar_one_or_none()
    return _coerce(_merged(row.value if row else None))


def module_enabled(config: dict[str, Any], module: str) -> bool:
    """Whether one reward module is switched on (its own switch AND payouts).

    ``module`` is ``"gift"``, ``"commission"`` or ``"recharge_bonus"``. The
    master ``enabled`` is checked by the callers (they all gate on it first);
    this is the per-module gate that lets an operator run, say, commissions
    with signup gifts off.
    """
    switch_key = f"{module}_enabled"
    if not bool(config.get(switch_key, True)):
        return False
    if module == "gift":
        return any(int(config.get(k, 0)) > 0 for k in ("signup_gift_l1", "signup_gift_l2"))
    if module == "commission":
        return any(
            percent_to_bp(config.get(k, 0)) > 0
            for k in ("commission_percent_l1", "commission_percent_l2")
        )
    if module == "recharge_bonus":
        return percent_to_bp(config.get("recharge_bonus_percent", 0)) > 0
    return False


def _has_payouts(config: dict[str, Any]) -> bool:
    """Whether any payout channel is configured above zero AND switched on."""
    return any(
        module_enabled(config, m) for m in ("gift", "commission", "recharge_bonus")
    )


def _is_active_program(config: dict[str, Any]) -> bool:
    """Whether the program is currently active: switched on AND paying something."""
    return bool(config.get("enabled", True)) and _has_payouts(config)


def _next_started_at(
    current: dict[str, Any], merged: dict[str, Any], now_iso: str
) -> str | None:
    """Decide the stored ``program_started_at`` after an update.

    - Activating (off → on, or first activation): stamp *now* — a fresh
      cut-off. This is what keeps an off period from being paid when the
      program comes back on after several days.
    - Staying active: keep the stamp. Editing a percent must NOT move the
      cut-off, or every config tweak would strip eligibility from orders
      placed since the last save.
    - Inactive: keep whatever is there (the next activation replaces it).
    """
    if not _is_active_program(merged):
        return merged.get("program_started_at")
    if merged.get("program_started_at") is None or not _is_active_program(current):
        return now_iso
    return merged.get("program_started_at")


async def set_config(db: AsyncSession, incoming: dict[str, Any]) -> dict[str, Any]:
    """Upsert the config. Only known keys are accepted.

    ``program_started_at`` is the retroactive-payout cut-off. It is stamped
    on every activation (the first one, and every off → on re-activation) so
    the off period is never paid when the program comes back on. While the
    program stays active the stamp does not move — editing a percent must
    not strip eligibility from orders placed since the last save.
    """
    from datetime import UTC, datetime

    # Reject 3+-decimal percents before anything is merged or stored (the
    # UI blocks them too; this is the direct-API gate).
    _reject_extra_decimals(incoming)

    current = await get_config(db)
    merged = dict(current)
    for key, value in incoming.items():
        if key not in DEFAULT_CONFIG:
            continue
        merged[key] = value
    merged = _coerce(merged)

    # Strip HTML from template fields before anything is stored (stored-XSS
    # defense-in-depth — see _sanitize_templates).
    _sanitize_templates(merged)

    # The stamp is server-owned: force the stored value first (a client that
    # echoes a stale stamp cannot influence the decision), then let the
    # activation logic decide whether it moves.
    merged["program_started_at"] = current.get("program_started_at")
    merged["program_started_at"] = _next_started_at(
        current, merged, datetime.now(UTC).isoformat()
    )
    if merged["program_started_at"] != current.get("program_started_at"):
        logger.info(
            "referral_program_activated",
            at=merged["program_started_at"],
            previously=current.get("program_started_at"),
        )

    row = (
        await db.execute(select(SiteSetting).where(SiteSetting.key == CONFIG_KEY))
    ).scalar_one_or_none()
    if row is None:
        row = SiteSetting(key=CONFIG_KEY, group=CONFIG_GROUP, is_public=False, value=merged)
        db.add(row)
    else:
        row.value = merged
    await db.flush()
    logger.info("referral_config_saved")
    return merged


def _started_at(config: dict[str, Any]) -> str | None:
    """The ISO cut-off string, or None when the program was never started."""
    value = config.get("program_started_at")
    return str(value) if value else None


def format_toman(rial: int) -> str:
    """Rial → Toman display string (site convention: 1 Toman = 10 Rial)."""
    return f"{rial // 10:,}"


def render_template(template: str, *, amount_rial: int) -> str:
    """Fill the ``{amount}`` placeholder (Toman) in a notification template."""
    return str(template or "").replace("{amount}", format_toman(amount_rial))
