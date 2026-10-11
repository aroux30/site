"""Local SEO — business info + LocalBusiness schema (Rank Math's Local SEO).

The store's own business profile: name, address, phone, hours, coordinates.
Stored as site options (a single business, not a multi-location directory —
the store is online-first; if locations multiply, a table replaces this and
the option keys migrate into it).

The LocalBusiness JSON-LD builder reads the same options the settings card
writes, so what the operator fills is exactly what Google reads. Empty fields
are omitted, never emitted as empty strings — an empty ``telephone`` is a
structured-data error Google reports against a node that looks filled.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

SCHEMA_CONTEXT = "https://schema.org"

#: Option key -> (form label, placeholder). The card renders from this list;
#: the builder reads the same keys. One vocabulary, two consumers.
BUSINESS_FIELDS: tuple[tuple[str, str, str], ...] = (
    ("local_seo_business_name", "نام کسب‌وکار", "فروشگاه من"),
    ("local_seo_business_type", "نوع کسب‌وکار", "Store"),
    ("local_seo_address", "نشانی", "تهران، خیابان ..."),
    ("local_seo_telephone", "تلفن", "021-12345678"),
    ("local_seo_opening_hours", "ساعات کاری", "Mo-Fr 09:00-18:00"),
    ("local_seo_price_range", "بازهٔ قیمت", "$$"),
    ("local_seo_latitude", "عرض جغرافیایی", "35.6892"),
    ("local_seo_longitude", "طول جغرافیایی", "51.3890"),
)

#: The LocalBusiness subtypes Rank Math offers, reduced to the ones an online
#: store plausibly uses. The full schema.org list has ~100; offering all of
#: them in a dropdown would bury the useful five.
BUSINESS_TYPES: tuple[str, ...] = (
    "Store",
    "OnlineStore",
    "LocalBusiness",
    "Organization",
    "ProfessionalService",
    "Restaurant",
)


async def get_business_info(db: AsyncSession) -> dict[str, str]:
    """Every configured field (empty string when unset)."""
    from app.modules.settings.application.site_options_service import SiteOptionsService

    out: dict[str, str] = {}
    for key, _label, _ph in BUSINESS_FIELDS:
        out[key] = await SiteOptionsService.get(db, key) or ""
    return out


async def save_business_info(db: AsyncSession, values: dict[str, str]) -> int:
    """Write the submitted fields; unknown keys are rejected loudly.

    A typo'd key stored silently would be a field the operator filled in that
    never reaches the schema — the same class of bug as a write-only setting.
    """
    from app.core.exceptions.handlers import ValidationError
    from app.modules.settings.application.site_options_service import SiteOptionsService

    allowed = {key for key, _l, _p in BUSINESS_FIELDS}
    unknown = set(values) - allowed
    if unknown:
        raise ValidationError(
            detail=f"فیلدهای ناشناخته: {sorted(unknown)}",
            error_code="UNKNOWN_FIELD",
        )

    written = 0
    for key, value in values.items():
        await SiteOptionsService.set(db, key, value or "")
        written += 1
    return written


async def build_local_business_jsonld(
    db: AsyncSession, *, base_url: str
) -> dict[str, Any] | None:
    """The LocalBusiness node, or None when no business name is configured.

    No name means no business profile — emitting a nameless LocalBusiness
    node would be a structured-data error, and the storefront's generic
    Organization node already covers the "this is a shop" signal.
    """
    info = await get_business_info(db)
    name = info.get("local_seo_business_name", "").strip()
    if not name:
        return None

    business_type = info.get("local_seo_business_type", "").strip() or "Store"
    node: dict[str, Any] = {
        "@context": SCHEMA_CONTEXT,
        "@type": business_type,
        "name": name,
        "url": base_url.rstrip("/"),
    }

    if info.get("local_seo_address"):
        node["address"] = {
            "@type": "PostalAddress",
            "streetAddress": info["local_seo_address"],
        }
    if info.get("local_seo_telephone"):
        node["telephone"] = info["local_seo_telephone"]
    if info.get("local_seo_opening_hours"):
        node["openingHours"] = info["local_seo_opening_hours"]
    if info.get("local_seo_price_range"):
        node["priceRange"] = info["local_seo_price_range"]

    lat = info.get("local_seo_latitude", "").strip()
    lng = info.get("local_seo_longitude", "").strip()
    if lat and lng:
        try:
            node["geo"] = {
                "@type": "GeoCoordinates",
                "latitude": float(lat),
                "longitude": float(lng),
            }
        except ValueError:
            logger.warning("local_seo_bad_coordinates", lat=lat, lng=lng)

    return node
