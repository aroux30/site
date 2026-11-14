"""USD-rate updater configuration: one ``SiteSetting`` row (``currency.usd_rate``).

Ported from the WordPress plugin's option set (``nobitex_*`` options: api
enabled, manual rate, update interval, rounding, log enabled) into a single
JSONB row, the project's config convention (``chat.widget``,
``referrals.config``). Money on the wire stays integer Rial (ADR-012) — the
plugin's rate lived in Toman; here it is ``manual_rate_rial`` and the admin UI
converts for display.

Deliberate differences from the plugin, and why:

* The manual rate defaults to **0** (the plugin defaulted to 50000). A
  forgotten 50000 in a 100000-Toman market would silently halve every USD
  price; 0 makes the fallback unusable until the operator sets it, and a run
  without a usable rate fails loudly instead.
* The plugin's ``log_enabled`` switch disabled the *whole* feature when off
  (``execute_price_update`` returned early). Here it only controls the history
  rows — turning logging off must not stop price updates.
* The plugin's "next run" was a WP-cron schedule with a minimum 1 minute.
  Here a Celery beat fires every minute and the task itself checks the
  configured interval, so the interval stays runtime-editable without a beat
  restart.

Server-owned runtime fields (``last_*``) are never accepted from a client
write — :func:`set_config` filters them, exactly like ``program_started_at``
in the referrals config.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import select

from app.modules.settings.domain.models import SiteSetting

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger()

CONFIG_KEY = "currency.usd_rate"
CONFIG_GROUP = "currency"

#: Default config. ``manual_rate_rial = 0`` means "not set": the fallback
#: rate is unusable until an operator enters one, and a run without any
#: usable rate fails with a recorded error instead of pricing at a guess.
DEFAULT_CONFIG: dict[str, Any] = {
    # Master switch: the scheduled sweep runs only while this is on. The
    # operator's manual "run now" button works regardless (explicit intent).
    "enabled": True,
    # Use the Nobitex USDT/IRT order book for the rate (plugin parity).
    # When off — or when the API call fails — the manual rate is used.
    "api_enabled": True,
    # Fallback rate, integer Rial (0 = unset). The admin UI edits it in Toman.
    "manual_rate_rial": 0,
    # Minimum minutes between automatic runs. A beat job ticks every minute
    # and skips until this much time has passed since the last attempt.
    "update_interval_minutes": 5,
    # Prices are rounded to the nearest multiple of this many Toman (plugin
    # ``nobitex_price_rounding``, default 100). 1 = round to whole Toman.
    "price_rounding_toman": 100,
    # Write a history row per run. Unlike the plugin, OFF does NOT stop the
    # price updates — it only stops the log rows.
    "log_enabled": True,
    # ── Server-owned runtime state (never accepted from a client write) ──
    "last_rate_rial": 0,
    "last_source": None,  # "api" | "manual"
    "last_update_at": None,  # ISO timestamp of the last SUCCESSFUL update
    "last_attempt_at": None,  # ISO timestamp of the last attempt (any outcome)
    "last_status": None,  # "success" | "failed"
    "last_error": None,
    "last_updated_count": 0,
}

#: Keys only the server writes. A client PUT that carries them is ignored
#: (the stored value is kept), so the status panel cannot be spoofed.
SERVER_OWNED_KEYS: frozenset[str] = frozenset(
    k for k in DEFAULT_CONFIG if k.startswith("last_")
)

#: Bounds: (min, max) per integer key.
_INT_BOUNDS: dict[str, tuple[int, int]] = {
    "manual_rate_rial": (0, 1_000_000_000),
    "update_interval_minutes": (1, 1440),
    "price_rounding_toman": (1, 1_000_000),
}


def _merged(stored: dict[str, Any] | None) -> dict[str, Any]:
    """Stored config on top of the defaults (missing keys keep their default)."""
    merged = dict(DEFAULT_CONFIG)
    if isinstance(stored, dict):
        merged.update(stored)
    return merged


def _coerce(config: dict[str, Any]) -> dict[str, Any]:
    """Clamp integer fields into their bounds; junk values fall back to 0/min."""
    for key, (lo, hi) in _INT_BOUNDS.items():
        try:
            value = int(config.get(key, 0))
        except (TypeError, ValueError):
            value = lo
        config[key] = max(lo, min(hi, value))
    for key in ("enabled", "api_enabled", "log_enabled"):
        config[key] = bool(config.get(key, True))
    return config


async def get_config(db: AsyncSession) -> dict[str, Any]:
    """Return the full config (defaults + stored, coerced)."""
    row = (
        await db.execute(select(SiteSetting).where(SiteSetting.key == CONFIG_KEY))
    ).scalar_one_or_none()
    return _coerce(_merged(row.value if row else None))


async def set_config(db: AsyncSession, incoming: dict[str, Any]) -> dict[str, Any]:
    """Upsert the config. Only known, non-server-owned keys are accepted."""
    current = await get_config(db)
    merged = dict(current)
    for key, value in incoming.items():
        if key not in DEFAULT_CONFIG or key in SERVER_OWNED_KEYS:
            continue
        merged[key] = value
    merged = _coerce(merged)
    return await _persist(db, merged)


async def update_runtime_state(db: AsyncSession, **fields: Any) -> dict[str, Any]:
    """Update server-owned runtime fields (``last_*``); unknown keys refused.

    Called by the sweep after every attempt. Kept separate from
    :func:`set_config` so a run can never round-trip operator settings.
    """
    unknown = set(fields) - SERVER_OWNED_KEYS
    if unknown:
        raise ValueError(f"not runtime state: {sorted(unknown)}")
    current = await get_config(db)
    current.update(fields)
    return await _persist(db, current)


async def _persist(db: AsyncSession, merged: dict[str, Any]) -> dict[str, Any]:
    row = (
        await db.execute(select(SiteSetting).where(SiteSetting.key == CONFIG_KEY))
    ).scalar_one_or_none()
    if row is None:
        row = SiteSetting(key=CONFIG_KEY, group=CONFIG_GROUP, is_public=False, value=merged)
        db.add(row)
    else:
        row.value = merged
    await db.flush()
    logger.info("currency_config_saved")
    return merged


def is_due(config: dict[str, Any], *, now: datetime | None = None) -> bool:
    """Whether the automatic sweep should run now.

    Due when the program is enabled and at least ``update_interval_minutes``
    have passed since the last *attempt* (success or failure — a failing API
    must not turn the beat into a every-minute retry loop).
    """
    if not config.get("enabled", True):
        return False
    last = config.get("last_attempt_at")
    if not last:
        return True
    try:
        last_dt = datetime.fromisoformat(str(last))
    except ValueError:
        return True
    if last_dt.tzinfo is None:
        last_dt = last_dt.replace(tzinfo=UTC)
    elapsed = (now or datetime.now(UTC)) - last_dt
    return elapsed.total_seconds() >= int(config.get("update_interval_minutes", 5)) * 60


def next_run_at(config: dict[str, Any]) -> str | None:
    """ISO timestamp of the next automatic run (None when disabled)."""
    if not config.get("enabled", True):
        return None
    last = config.get("last_attempt_at")
    if not last:
        return datetime.now(UTC).isoformat()
    try:
        last_dt = datetime.fromisoformat(str(last))
    except ValueError:
        return datetime.now(UTC).isoformat()
    if last_dt.tzinfo is None:
        last_dt = last_dt.replace(tzinfo=UTC)
    from datetime import timedelta

    return (
        last_dt + timedelta(minutes=int(config.get("update_interval_minutes", 5)))
    ).isoformat()


__all__ = [
    "CONFIG_KEY",
    "CONFIG_GROUP",
    "DEFAULT_CONFIG",
    "SERVER_OWNED_KEYS",
    "get_config",
    "is_due",
    "next_run_at",
    "set_config",
    "update_runtime_state",
]
