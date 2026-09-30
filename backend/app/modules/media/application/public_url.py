"""Public URL builder for media assets (CDN base prefixing).

Asset rows always store the origin-relative URL (``/uploads/media/<name>``);
the CDN base is a site option (``media_cdn_base_url``) applied at
serialisation time so operators can flip the delivery domain without
rewriting a single DB row. The on-the-fly ``/media/{id}/variant`` endpoint
keeps serving bytes from the origin and is deliberately not prefixed here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.modules.settings.application.site_options_service import SiteOptionsService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

#: Site option holding the CDN base, e.g. ``https://cdn.example.com``.
CDN_BASE_URL_OPTION = "media_cdn_base_url"


async def resolve_cdn_base_url(db: AsyncSession) -> str:
    """Read the configured CDN base (default empty = serve from origin).

    The option is operator-editable text, so trailing slashes/spaces are
    trimmed instead of trusted.
    """
    raw = await SiteOptionsService.get(db, CDN_BASE_URL_OPTION)
    return (raw or "").strip().rstrip("/")


def build_asset_url(file_url: str, cdn_base: str) -> str:
    """Prefix ``file_url`` with the CDN base when one is configured.

    Only origin-relative URLs (``/uploads/...``) are prefixed — an absolute
    URL is returned untouched so an already-external asset is never mangled.
    """
    base = (cdn_base or "").strip().rstrip("/")
    if not base or not file_url.startswith("/"):
        return file_url
    return f"{base}{file_url}"
