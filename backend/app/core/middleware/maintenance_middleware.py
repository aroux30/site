"""Maintenance mode: the gate every request passes through.

P0 "ابزارها: حالت نگهداری". WordPress checks a ``.maintenance`` file on every
request, before authentication, and answers 503 with a ``Retry-After``. Two
things about that are copied and one is deliberately not.

Copied: the check happens in one place that every request passes, not in the
handlers that happen to exist today. A gate on individual routes is a gate that
the route added next month does not have.

Copied: the response is 503 with ``Retry-After`` and ``Cache-Control: no-store``.
A 200 would be cached by every CDN in front of the store and served to shoppers
long after the migration finished; a 503 is what a load balancer understands as
"this instance is temporarily out", which is what it is.

Not copied: WordPress exempts only its own installer, so its ``wp_maintenance()``
runs before authentication and locks the operator out of their own panel for the
duration. This store has staff on shift, and being locked out to end your own
maintenance turns a ten-minute migration into an all-day outage.

The state is read from the database on every request rather than cached in a
module global. A cached flag is a flag that stays on after the operator turns it
off — on whichever worker read it last, and the store does not come back. The
read is one indexed lookup on a single-row table; that is the price of a flag
that can actually be turned off.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import Request
from fastapi.responses import HTMLResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.modules.settings.application.maintenance_service import (
    get_state,
    is_exempt_actor,
    is_exempt_path,
)

logger = logging.getLogger("site.maintenance")

#: Seconds a client should wait before retrying. WordPress sends 600 and so does
#: this: long enough that a browser does not hammer the store while it is down,
#: short enough that the store comes back on its own once the migration is over.
RETRY_AFTER_SECONDS = 600

_PAGE = """<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>در دست تعمیر — {store}</title>
<meta name="robots" content="noindex, nofollow">
<style>
  body {{ margin:0; min-height:100vh; display:grid; place-items:center;
         background:#f4f5f7; color:#111827;
         font-family:Tahoma,Arial,sans-serif; }}
  main {{ max-width:34rem; padding:2.5rem; text-align:center;
          background:#fff; border:1px solid #e5e7eb; border-radius:12px; }}
  h1 {{ font-size:1.25rem; margin:0 0 .75rem; }}
  p {{ margin:.5rem 0; line-height:2; color:#4b5563; font-size:.9rem; }}
  .when {{ color:#6b7280; font-size:.8rem; margin-top:1.25rem; }}
  .admin {{ margin-top:1.5rem; font-size:.8rem; }}
  .admin a {{ color:#2563eb; }}
</style>
</head>
<body>
<main>
  <h1>کمی بعد برمی‌گردیم</h1>
  <p>{reason}</p>
  <p class="when">این صفحه حدود {minutes} دقیقهٔ دیگر خودبه‌خود برداشته می‌شود.</p>
  <p class="admin"><a href="/admin">ورود به پنل مدیریت</a></p>
</main>
</body>
</html>"""


class MaintenanceMiddleware(BaseHTTPMiddleware):
    """Answers 503 for everyone except staff, while the flag is on."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Path check first and without touching the database. It runs on every
        # request of a normal day too, and a flag check that costs a query for
        # the health checks of every replica is a flag check that will eventually
        # be skipped.
        if is_exempt_path(path):
            return await call_next(request)

        from app.core.database.session import async_session_factory

        try:
            async with async_session_factory() as db:
                state = await get_state(db)
                if not state.active:
                    return await call_next(request)

                # An authenticated operator is let through. Reading the identity
                # here rather than trusting a header is the point: a header an
                # attacker controls would make the exemption a way *around*
                # maintenance.
                user_id = await _optional_user_id(request)
                if user_id is not None and await is_exempt_actor(db, user_id=user_id):
                    return await call_next(request)
        except Exception as exc:  # noqa: BLE001
            # A store that cannot read its own settings serves traffic. Failing
            # closed here would mean a database blip takes the storefront down
            # for every visitor, and the flag would be the least of it.
            logger.warning(
                "maintenance_check_failed_serving_traffic", exc_info=exc
            )
            return await call_next(request)

        logger.info("maintenance_serving_503", extra={"path": path})
        return HTMLResponse(
            content=_render(state.reason, state.minutes),
            status_code=503,
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate",
                "Retry-After": str(RETRY_AFTER_SECONDS),
            },
        )


def _render(reason: str, minutes: int) -> str:
    from app.modules.settings.application.default_options import DEFAULTS

    store = DEFAULTS.get("blogname", "فروشگاه")
    return _PAGE.format(
        store=_escape(store),
        reason=_escape(reason) if reason else "در حال انجام به‌روزرسانی هستیم.",
        minutes=minutes,
    )


def _escape(value: str) -> str:
    """Escape text interpolated into the page.

    The reason is operator-supplied and goes into a document with no
    client-side sanitiser, so a reason containing markup would execute. It is
    free text and belongs escaped.
    """
    import html

    return html.escape(str(value), quote=True)


async def _optional_user_id(request: Request):
    """The caller's id, or None. Never raises.

    A malformed or expired token during maintenance must not turn into a 500 —
    it means "not a staff member", which the path exemptions and this both
    handle by letting the 503 stand.
    """
    from app.core.security.jwt import decode_token

    header = request.headers.get("authorization") or ""
    if not header.lower().startswith("bearer "):
        return None
    token = header[7:].strip()
    if not token:
        return None
    try:
        payload = decode_token(token)
    except Exception:  # noqa: BLE001
        return None
    sub = payload.get("sub") if isinstance(payload, dict) else None
    try:
        return uuid.UUID(str(sub)) if sub else None
    except (ValueError, TypeError):
        return None
