"""Shop feature switches for storefront modules that have no dedicated panel.

The wallet owns its own settings surface (``/admin/wallet/settings``) because
it is a full domain with withdrawals, transfers and an admin ledger. Wishlist
and compare are simpler: each is a set of ``site_options`` toggles with no
admin workflow of its own, so they share one generic surface here instead of
each growing a route pair.

Why a shared module rather than two more key sets bolted onto the wallet: the
gate is the same for every storefront feature — an operator turning a feature
off wants the ENTRY POINTS GONE, not a page that renders and then errors. That
is exactly the defect class ``check_wallet_switch_hiding.py`` was written for
(the server refused every write while the menu entry stayed on screen), and it
repeats here for every feature. So each switch here has BOTH halves: the route
guard below, and the client hiding pinned by that same gate.

Compare has **no backend at all** — it is a localStorage-only storefront
feature. Only the read endpoint is server-backed (it returns the switch state so
the client can decide what to render); nothing is stored server-side.
"""

from __future__ import annotations

import structlog
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.exceptions.handlers import ValidationError

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# Same truthy set as the wallet switches; a switch row is plain text "1"/"0".
_TRUTHY = {"1", "true", "yes", "on", "فعال", "بله"}

# The feature switches this module owns. "master" keys are the ones that hide a
# whole module; the rest are sub-capabilities that may be turned off on their own.
#
# Each entry is (key, master) so callers do not have to remember which is which.
SHOP_FEATURE_SWITCHES: dict[str, bool] = {
    # ── Wishlist ──
    # Master: hides the account tab, the header entry, the product-page hearts
    # and the /favorites page.
    "wishlist_enabled": True,
    # ── Compare ──
    # Master: hides the header link, the floating bar, the per-product compare
    # toggle and the /compare page. No backend routes exist for compare, so
    # this only gates the storefront.
    "compare_enabled": True,
}


async def is_enabled(db: AsyncSession, key: str, *, default: bool = True) -> bool:
    """Return whether a shop feature switch is on, reading ``site_options`` live.

    Read per request and never cached, so an operator's change takes effect on
    the next request — the same contract the wallet switches keep.

    Unknown/absent keys fall back to ``default`` (on) so a database that
    predates the seed keeps the feature rather than silently disabling it.
    """
    from app.modules.settings.application.site_options_service import SiteOptionsService

    if key not in SHOP_FEATURE_SWITCHES:
        return default
    raw = await SiteOptionsService.get(db, key, "1" if default else "0")
    return str(raw or "").strip().lower() in _TRUTHY


async def require_enabled(db: AsyncSession, key: str) -> None:
    """Raise a Persian ValidationError when a feature switch is off.

    Call at the TOP of each route, before any lookup or write, so a disabled
    feature costs nothing and leaks nothing about whether the resource exists.
    """
    if await is_enabled(db, key):
        return
    label = _PERSIAN_LABELS.get(key, key)
    raise ValidationError(
        detail=f"این قابلیت ({label}) در حال حاضر غیرفعال است.",
        error_code="FEATURE_DISABLED",
    )


def require_feature(key: str):
    """Build a FastAPI dependency that enforces a feature switch.

    Used as ``dependencies=[Depends(require_feature("wishlist_enabled"))]`` on
    a router/route. Wrapping rather than calling ``require_enabled`` directly is
    what lets the guard live in ``dependencies=`` instead of being repeated as a
    first line in every handler — a guard that has to be remembered is a guard
    that gets dropped from the next route someone adds.
    """

    async def _dependency(db: AsyncSession = Depends(get_db)) -> None:
        await require_enabled(db, key)

    return _dependency


# Persian names for the message above. A user should never be shown a raw
# snake_case key.
_PERSIAN_LABELS = {
    "wishlist_enabled": "علاقه‌مندی‌ها",
    "compare_enabled": "مقایسه کالاها",
}


async def get_switches(db: AsyncSession) -> dict[str, bool]:
    """Return every shop feature switch state, for the admin panel."""
    return {key: await is_enabled(db, key) for key in sorted(SHOP_FEATURE_SWITCHES)}


async def set_switch(db: AsyncSession, *, key: str, enabled: bool) -> bool:
    """Set a shop feature switch. Raises if the key is not one of ours."""
    if key not in SHOP_FEATURE_SWITCHES:
        raise ValidationError(
            detail="کلید تنظیمات نامعتبر است.",
            error_code="UNKNOWN_FEATURE_SWITCH",
        )
    from app.modules.settings.application.site_options_service import SiteOptionsService

    await SiteOptionsService.set(db, key, "1" if enabled else "0")
    await logger.ainfo("shop_feature_switch_changed", feature_key=key, enabled=enabled)
    return enabled


async def feature_state(db: AsyncSession) -> dict[str, bool]:
    """The public read the storefront uses to decide what to render.

    Separate from ``get_switches`` (admin) so this shape can stay exactly what
    the client needs and can gain fields without breaking the admin page.
    """
    return {key: await is_enabled(db, key) for key in sorted(SHOP_FEATURE_SWITCHES)}
