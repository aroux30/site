"""Maintenance mode: a flag, a gate, and a way back out.

P0 "ابزارها: حالت نگهداری". Nothing existed — no flag, no page, no route. An
operator about to run a migration against a live storefront had two options, both
bad: take the site down at the load balancer and hope they remember to bring it
back, or deploy over a running shop and hope nothing half-applies while a
customer is mid-checkout.

WordPress's mechanism is a ``.maintenance`` file in the root, checked on every
request, with a ten-minute self-expiry so a crashed upgrade cannot leave a store
down forever. Both properties are kept here and neither is incidental:

  - the **self-expiry** is what makes the flag safe to set. A store left down
    by a flag nobody turned off loses its revenue silently, and the person who
    set it is the person who has gone home.
  - the **auto-expiry is a floor, not a ceiling**. An operator who needs the site
    down for two hours has to be able to say so; a flag that silently lifted
    itself at ten minutes would drop them back into a half-migrated database
    with no warning, which is the failure this exists to prevent.

Admins are exempt. WordPress is not — it exempts only its own installer, and
``wp_maintenance()`` runs before authentication — but WordPress has one operator
and a login screen; this project has a storefront that a staff member may be
mid-shift on, and being locked out of the panel to end your own maintenance is
how a ten-minute outage becomes an all-day one.

The gate lives in middleware rather than in a route decorator so that it covers
routes added later without anyone remembering to decorate them.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import select

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

#: The site option holding the flag. A boolean in ``site_options`` rather than a
#: file on disk: the flag is read on every request from another service, and a
#: file is not visible to a horizontally scaled deployment.
MAINTENANCE_OPTION = "maintenance.mode"

#: The floor on how long a flag lasts, matching WordPress's ten minutes. A flag
#: that expired sooner would drop the store back mid-migration; one with no floor
#: at all could stay on indefinitely if the operator lost the tab.
DEFAULT_MIN_MINUTES = 10

#: Upper bound on a single requested duration. Not a policy about how long a
#: migration takes — it is a guard against a typo ("3600" typed into a field
#: meant for minutes) becoming a store that disappears for a day.
MAX_HOURS = 72


@dataclass(frozen=True)
class MaintenanceState:
    """What the flag currently says, and what a reader should do about it."""

    active: bool
    reason: str = ""
    minutes: int = 0
    expires_at: datetime | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "active": self.active,
            "reason": self.reason,
            "minutes": self.minutes,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }


OFF = MaintenanceState(active=False)


def _parse(raw: str | None) -> MaintenanceState:
    """Read the stored value, treating anything unreadable as "not in maintenance".

    A corrupt flag must not lock a store out. The failure mode of *ignoring* a
    broken flag is a storefront that is up when it should be down, which an
    operator can see and fix. The failure mode of honouring one is a storefront
    nobody can reach, which nobody notices until the revenue stops.
    """
    import json

    if not raw:
        return OFF
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        logger.warning("maintenance_flag_unreadable_treated_as_off")
        return OFF
    if not isinstance(parsed, dict) or not parsed.get("active"):
        return OFF

    raw_expiry = parsed.get("expires_at")
    expires = None
    if raw_expiry:
        try:
            expires = datetime.fromisoformat(str(raw_expiry))
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=UTC)
        except ValueError:
            expires = None

    if expires is None or expires <= datetime.now(UTC):
        # Either it never had an end, or its end has passed. Both mean the flag
        # has lapsed and the store is serving again — which is the whole point of
        # putting an expiry on it.
        logger.info("maintenance_flag_expired_treated_as_off")
        return OFF

    return MaintenanceState(
        active=True,
        reason=str(parsed.get("reason") or ""),
        minutes=max(0, int(round((expires - datetime.now(UTC)).total_seconds() / 60))),
        expires_at=expires,
    )


async def get_state(db: AsyncSession) -> MaintenanceState:
    """The current state, reading the option each time.

    Not cached in a module global. A cached flag is a flag that stays on after
    the operator turns it off, on whichever worker happens to have read it last
    — and the store does not come back.
    """
    from app.modules.settings.application.site_options_service import SiteOptionsService

    return _parse(await SiteOptionsService.get(db, MAINTENANCE_OPTION))


async def set_maintenance(
    db: AsyncSession,
    *,
    active: bool,
    minutes: int = DEFAULT_MIN_MINUTES,
    reason: str = "",
) -> MaintenanceState:
    """Turn maintenance on or off, and return the state that was written.

    ``minutes`` is clamped rather than rejected: an operator asking for an hour
    and typing 1 should get a minute and a store that comes back, not an error
    that leaves them unsure whether the flag is on.
    """
    import json

    from app.modules.settings.application.site_options_service import SiteOptionsService

    if not active:
        await SiteOptionsService.set(db, MAINTENANCE_OPTION, "")
        logger.info("maintenance_disabled")
        return OFF

    safe_minutes = max(DEFAULT_MIN_MINUTES, min(int(minutes or 0), MAX_HOURS * 60))
    expires = datetime.now(UTC) + timedelta(minutes=safe_minutes)
    payload = json.dumps(
        {
            "active": True,
            "reason": reason[:500],
            "minutes": safe_minutes,
            "expires_at": expires.isoformat(),
        },
        ensure_ascii=False,
    )
    await SiteOptionsService.set(db, MAINTENANCE_OPTION, payload)
    logger.info(
        "maintenance_enabled", minutes=safe_minutes, until=expires.isoformat(), reason=reason[:200]
    )
    return MaintenanceState(
        active=True, reason=reason, minutes=safe_minutes, expires_at=expires
    )


def is_exempt_path(path: str) -> bool:
    """Whether a request path stays reachable while the store is down.

    Four kinds, and each exists for a reason rather than as a convenience:

      - the maintenance page itself, or a 503 loop turns a bad deploy into a
        browser full of failures
      - the API endpoint the storefront calls, so a client-rendered shell can
        render the message rather than showing a raw network error
      - health checks, or the load balancer pulls the instance out and the flag
        cannot be turned *off* — the outage keeps the store down by removing the
        only way to end it
      - the admin routes and the login page, or the operator who set the flag
        cannot get in to clear it
    """
    p = path.lower()
    return (
        "/maintenance"
        in p
        or p.startswith("/api/v1/settings/public/maintenance")
        or p.startswith("/api/v1/health")
        or p in ("/healthz", "/readyz", "/metrics")
        or p.startswith("/api/v1/auth/login")
        or p.startswith("/api/v1/auth/refresh")
        or p.startswith("/api/v1/users/admin")
        or p.startswith("/api/v1/settings/admin")
        or p.startswith("/api/v1/rbac/admin")
        or p.startswith("/admin")
        or p.startswith("/login")
        or p in ("/health", "/ready")
    )


async def is_exempt_actor(db: AsyncSession, *, user_id: uuid.UUID | None) -> bool:
    """Whether an authenticated caller is allowed through.

    Superusers and anyone holding an admin role. The path exemptions above get a
    staff member to the login screen; this is what lets them past it, so a store
    that is mid-migration can still be inspected and, more importantly, closed.
    """
    if user_id is None:
        return False
    from app.modules.rbac.domain.models import Role, UserRole
    from app.modules.users.application.last_admin_guard import ADMIN_ROLE_SLUGS
    from app.modules.users.domain.models import User

    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        return False
    if user.is_superuser:
        return True

    return bool(
        (
            await db.execute(
                select(UserRole.id)
                .join(Role, Role.id == UserRole.role_id)
                .where(
                    UserRole.user_id == user_id,
                    Role.slug.in_(ADMIN_ROLE_SLUGS),
                )
                .limit(1)
            )
        ).scalar()
    )
