"""The store name an email shows, resolved from one place.

P0 "ایمیل: نام فروشگاه در ایمیل‌ها". Four transactional templates read the
operator's name from the settings, and the three generic send paths read it from
``SMTP_FROM_NAME`` in the environment. Both fall back to the same literal, so
the same store showed two different names in the same customer's inbox: the
order confirmation said the operator's name and the shipping notification said
"فروشگاه اینترنتی". Both are the store's own name in its own header, on the same
domain, within the same minute.

The environment is the wrong source for this. It cannot be changed from the
panel, it survives in the deployment rather than in the store's settings, and
an operator who renames their shop in Settings has no reason to know a second
name exists in a container they do not edit. It stays as the *last* resort
because it is the one place an operator can set a name without a database — which
is exactly the case it is good for, and the only one.

Order of resolution:

  1. ``store.identity.store_name`` — what the operator types in Settings
  2. ``blogname`` — the same value the rest of the site reads for its title
  3. ``SMTP_FROM_NAME`` — the deployment's own default
  4. the literal

Step 2 is what makes this "one source" rather than "a second source": ``blogname``
is already what the feed, the sitemap and the site header read, so a store that
never fills in the new store-identity form still gets one name everywhere.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

#: Shown when the store has configured no name at all. Not a placeholder in the
#: UI sense — it is the only thing a brand-new deployment can honestly print.
DEFAULT_STORE_NAME = "فروشگاه اینترنتی"

#: The option holding the operator's name, as JSON (the same blob the settings
#: screen writes and the storefront reads).
STORE_IDENTITY_OPTION = "store.identity"
#: The site's own title. The rest of the storefront reads this, so it is the
#: second choice rather than a second definition.
BLOGNAME_OPTION = "blogname"


async def resolve_store_name(db: AsyncSession | None = None) -> str:
    """The name to print in an email header, from the store's own settings.

    ``db`` is optional so this is callable from the paths that have no session —
    a health check, a CLI, a template preview. Passing ``None`` skips the
    database and goes straight to the environment, which is a degraded answer
    and says so in the log rather than pretending the lookup succeeded.
    """
    if db is not None:
        try:
            from app.modules.settings.application.site_options_service import (
                SiteOptionsService,
            )

            raw = await SiteOptionsService.get(db, STORE_IDENTITY_OPTION)
            name = _name_from_identity(raw)
            if name:
                return name

            blogname = (await SiteOptionsService.get(db, BLOGNAME_OPTION) or "").strip()
            if blogname:
                return blogname
        except Exception:  # noqa: BLE001
            # A store name is never worth failing an email over. A settings table
            # that is momentarily unreadable must not stop a password reset from
            # going out; the fallback below still produces a deliverable message.
            logger.exception("store_name_resolution_failed")

    return _env_store_name()


def _name_from_identity(raw: str | None) -> str:
    """The store_name inside the ``store.identity`` JSON blob, or empty."""
    if not raw:
        return ""
    import json

    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        # An operator hand-editing the option into invalid JSON is not an error
        # worth surfacing to whoever is waiting on an email; fall through to
        # blogname.
        return ""
    if not isinstance(parsed, dict):
        return ""
    return str(parsed.get("store_name") or "").strip()


def _env_store_name() -> str:
    """The deployment's configured name, or the literal."""
    try:
        from app.core.config import get_settings

        return (get_settings().SMTP_FROM_NAME or "").strip() or DEFAULT_STORE_NAME
    except Exception:  # noqa: BLE001
        return DEFAULT_STORE_NAME
