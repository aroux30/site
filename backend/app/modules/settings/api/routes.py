"""Settings API routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, Query, Request, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.exceptions.handlers import NotFoundError, ValidationError
from app.core.security.dependencies import RequirePermissions
from app.core.security.rate_limiter import limiter
from app.modules.settings.application.settings_service import SettingsService
from app.modules.settings.schemas.settings import (
    MaintenanceSetRequest,
    MaintenanceStateResponse,
    PublicSettingResponse,
    SettingCreateRequest,
    SettingResponse,
    SettingUpdateRequest,
    SMSProviderItem,
    SMSProvidersResponse,
    SMSTestRequest,
    SMSTestResponse,
)

router = APIRouter()


@router.get(
    "/public",
    response_model=list[PublicSettingResponse],
    summary="List public site settings",
)
async def get_public_settings(
    group: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> list[PublicSettingResponse]:
    """Return publicly exposed site configuration (logos, title, footer, etc.)."""
    settings = await SettingsService.get_all(db, group=group, public_only=True)
    return [PublicSettingResponse(key=s.key, value=s.value) for s in settings]


@router.get(
    "/public/maintenance",
    response_model=MaintenanceStateResponse,
    summary="Whether the store is in maintenance mode",
)
async def get_maintenance_state(
    db: AsyncSession = Depends(get_db),
) -> MaintenanceStateResponse:
    """Public and unauthenticated, so the storefront can ask before it renders.

    Declared above ``/{key}`` so FastAPI does not match the catch-all first and
    answer 404 for a setting named "maintenance", which reads to a client as
    "the store is fine".
    """
    from app.modules.settings.application.maintenance_service import get_state

    return MaintenanceStateResponse(**(await get_state(db)).as_dict())


@router.post(
    "/admin/maintenance",
    response_model=MaintenanceStateResponse,
    dependencies=[Depends(RequirePermissions("settings:write"))],
    summary="Turn maintenance mode on or off",
)
async def set_maintenance_state(
    body: MaintenanceSetRequest,
    db: AsyncSession = Depends(get_db),
) -> MaintenanceStateResponse:
    """Put the store into maintenance, or bring it back.

    Always answers with the state that was actually written, including the
    clamped duration. An operator who asked for two minutes and got a 422 does
    not know whether the flag is on; an operator who asked for two minutes and
    is told it is on for ten knows exactly where they stand.
    """
    from app.modules.settings.application.maintenance_service import set_maintenance

    state = await set_maintenance(
        db,
        active=body.active,
        minutes=body.minutes,
        reason=body.reason,
    )
    await db.commit()
    return MaintenanceStateResponse(**state.as_dict())


@router.get(
    "",
    response_model=list[SettingResponse],
    summary="List all site settings (admin)",
    dependencies=[Depends(RequirePermissions("settings:read"))],
)
async def get_all_settings(
    group: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> list[SettingResponse]:
    """List all site settings with full metadata."""
    settings = await SettingsService.get_all(db, group=group, public_only=False)
    return [SettingResponse.model_validate(s) for s in settings]


@router.get(
    "/{key}",
    response_model=SettingResponse,
    summary="Get setting by key (admin)",
    dependencies=[Depends(RequirePermissions("settings:read"))],
)
async def get_setting(
    key: str,
    db: AsyncSession = Depends(get_db),
) -> SettingResponse:
    """Get a single setting."""
    setting = await SettingsService.get_by_key(db, key)
    return SettingResponse.model_validate(setting)


@router.post(
    "",
    response_model=SettingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create setting (admin)",
    dependencies=[Depends(RequirePermissions("settings:write"))],
)
async def create_setting(
    payload: SettingCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> SettingResponse:
    """Create a new setting key-value pair."""
    if payload.key in _URL_SHAPED_KEYS and isinstance(payload.value, str):
        _assert_valid_url_shape(payload.key, payload.value)
    setting = await SettingsService.create(db, payload)
    await db.commit()
    return SettingResponse.model_validate(setting)


#: Settings whose value is a URL shape the routing layer has to match, so a
#: bad value breaks every generated link rather than one page.
_URL_SHAPED_KEYS: frozenset[str] = frozenset(
    {"permalink_structure", "category_base", "tag_base"}
)


def _assert_valid_url_shape(key: str, value: str) -> None:
    """Reject a URL-shaped setting the resolver would not accept.

    Raises 422 rather than saving a value that would later be ignored, because
    the silent version of this bug is very hard to see: links simply stop
    following the configured structure.
    """
    from app.shared.permalinks import validate_structure

    problems = validate_structure(value) if key == "permalink_structure" else _base_problems(value)
    if problems:
        raise ValidationError(detail=f"{key}: {' '.join(problems)}")


def _base_problems(value: str) -> list[str]:
    """A taxonomy base must be one path segment, with no leading or trailing slash."""
    cleaned = (value or "").strip()
    if not cleaned:
        return []
    problems: list[str] = []
    if "/" in cleaned.strip("/"):
        problems.append("base باید یک بخش باشد، نه مسیر.")
    if not cleaned.isascii():
        problems.append("base باید حروف انگلیسی داشته باشد.")
    return problems


@router.patch(
    "/{key}",
    response_model=SettingResponse,
    summary="Update setting (admin)",
    dependencies=[Depends(RequirePermissions("settings:write"))],
)
async def update_setting(
    key: str,
    payload: SettingUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> SettingResponse:
    """Update an existing setting."""
    # A permalink structure is a routing contract, not free text. It was
    # validated nowhere on the write path — `validate_structure` had zero
    # callers — so an operator could save a structure the resolver then
    # refused to match, and every generated link silently reverted to
    # /blog/<slug> with no error. Reject at the door.
    if key in _URL_SHAPED_KEYS and isinstance(payload.value, str):
        _assert_valid_url_shape(key, payload.value)

    setting = await SettingsService.update(db, key, payload)
    await db.commit()
    return SettingResponse.model_validate(setting)


@router.delete(
    "/{key}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete setting (admin)",
    dependencies=[Depends(RequirePermissions("settings:write"))],
)
async def delete_setting(
    key: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete an existing setting."""
    await SettingsService.delete(db, key)
    await db.commit()


# ── SMS Provider Management (Admin) ──────────────────────────────────────────


@router.get(
    "/admin/sms-providers",
    response_model=SMSProvidersResponse,
    summary="Get SMS provider status and failover priority (admin)",
    dependencies=[Depends(RequirePermissions("settings:read"))],
)
@router.get(
    "/admin/sms-providers/test",
    response_model=SMSProvidersResponse,
    summary="Get SMS provider status and failover priority alias (admin)",
    dependencies=[Depends(RequirePermissions("settings:read"))],
    include_in_schema=False,
)
async def get_sms_providers() -> SMSProvidersResponse:
    """Return configured SMS providers, active status, and failover priority chain."""
    return SMSProvidersResponse(
        primary_provider="kavenegar",
        failover_order=["kavenegar", "ippanel", "smsir", "mock_fallback"],
        providers=[
            SMSProviderItem(
                id="kavenegar",
                name="Kavenegar (کاوه نگار)",
                priority=1,
                is_active=True,
                supports_patterns=True,
            ),
            SMSProviderItem(
                id="ippanel",
                name="IPPanel / FarazSMS (فراز اس‌ام‌اس)",
                priority=2,
                is_active=True,
                supports_patterns=True,
            ),
            SMSProviderItem(
                id="smsir",
                name="SMS.ir (سامانه پیامکی)",
                priority=3,
                is_active=True,
                supports_patterns=True,
            ),
            SMSProviderItem(
                id="mock_fallback",
                name="Internal Simulation Mock",
                priority=4,
                is_active=True,
                supports_patterns=False,
            ),
        ],
    )


@router.post(
    "/admin/sms-providers/test",
    response_model=SMSTestResponse,
    summary="Send test SMS via failover hub (admin)",
    dependencies=[Depends(RequirePermissions("settings:write"))],
)
@limiter.limit("5/minute")
async def test_sms_provider(
    request: Request,
    payload: SMSTestRequest,
) -> SMSTestResponse:
    """Dispatch a test SMS message using the multi-provider failover hub."""
    from app.modules.messaging.application.sms_hub_service import send_sms_with_failover

    target_phone = payload.phone or payload.mobile or ""
    target_text = payload.message or payload.text or ""

    res = await send_sms_with_failover(
        mobile=target_phone,
        text=target_text,
        pattern=payload.pattern,
    )
    return SMSTestResponse(
        success=res.get("success", False),
        provider=res.get("provider"),
        to=res.get("to", target_phone),
        error=res.get("error"),
    )


# ── Email (SMTP) Provider Management — removed 2026-10-07 ────────────────────
# The /admin/email-providers, /admin/email-providers/test and
# /admin/email-delivery-log routes were removed with the rest of the email
# feature. See `_archived/email-removal-2026-10-07/`.


# ── WordPress parity: Site Options (global key-value settings) ───────────────


@router.get(
    "/admin/site-options",
    summary="List all site options (admin)",
    dependencies=[Depends(RequirePermissions("settings:read"))],
)
async def list_site_options(
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Return all global site options (WordPress wp_options parity)."""
    from app.modules.settings.application.site_options_service import SiteOptionsService

    return await SiteOptionsService.get_all(db)


@router.put(
    "/admin/site-options/{key}",
    summary="Set a site option (admin)",
    dependencies=[Depends(RequirePermissions("settings:write"))],
)
async def set_site_option(
    key: str,
    body: dict[str, Any],
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Upsert a global site option by key."""
    from app.modules.settings.application.site_options_service import SiteOptionsService

    await SiteOptionsService.set(db, key, body.get("value"), autoload=body.get("autoload", True))
    return {"key": key, "value": body.get("value")}


@router.delete(
    "/admin/site-options/{key}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a site option (admin)",
    dependencies=[Depends(RequirePermissions("settings:write"))],
)
async def delete_site_option(
    key: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a global site option."""
    from app.modules.settings.application.site_options_service import SiteOptionsService

    await SiteOptionsService.delete(db, key)


@router.post(
    "/admin/site-options/seed-defaults",
    summary="Seed default site options (admin)",
    dependencies=[Depends(RequirePermissions("settings:write"))],
)
async def seed_site_options(
    db: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    """Seed WordPress-parity default options; existing keys are left alone."""
    from app.modules.settings.application.default_options import seed_defaults

    return {"seeded": await seed_defaults(db)}


# ── WordPress parity: Site Health ────────────────────────────────────────────


@router.get(
    "/admin/site-health",
    summary="Run site health diagnostics (admin)",
    dependencies=[Depends(RequirePermissions("settings:read"))],
)
async def get_site_health(
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Run database, Redis, media, and migration health checks."""
    from app.modules.settings.application.site_health_service import SiteHealthService

    return await SiteHealthService.run_checks(db)


@router.get(
    "/admin/site-health/info",
    summary="Site health info tab: versions, database, storage (admin)",
    dependencies=[Depends(RequirePermissions("settings:read"))],
)
async def get_site_health_info(
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """The facts a support ticket needs, as WordPress's "Site Health → Info".

    Allow-listed inside the service: a name that is not explicitly listed is
    never included, so adding a new secret setting cannot leak it here by
    default. Read-only — no lock, no migration, no write.
    """
    from app.modules.settings.application.site_health_service import SiteHealthService

    return await SiteHealthService.debug_info(db)


@router.post(
    "/admin/site-health/run",
    summary="Run the health checks now and record the result (admin)",
    dependencies=[Depends(RequirePermissions("settings:write"))],
)
async def run_site_health_now(
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Press the button, and keep the result.

    WordPress's Site Health screen does both: it runs on demand and it keeps a
    page of what ran. Before this, the button equivalent was a live check that
    vanished on reload, so a problem that had already been fixed left no trace
    and the next visit could not tell "healthy" from "was broken an hour ago".
    """
    from app.modules.settings.application.site_health_service import SiteHealthService

    return await SiteHealthService.record_run(db, trigger="manual")


@router.get(
    "/admin/site-health/runs",
    summary="Recent site health runs, newest first (admin)",
    dependencies=[Depends(RequirePermissions("settings:read"))],
)
async def list_site_health_runs(
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """The history behind the current reading."""
    from app.modules.settings.application.site_health_service import SiteHealthService

    items = await SiteHealthService.list_runs(db, limit=limit)
    return {"items": items}


@router.get(
    "/admin/site-health/runs/{run_id}",
    summary="One site health run with its full report (admin)",
    dependencies=[Depends(RequirePermissions("settings:read"))],
)
async def get_site_health_run(
    run_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    from app.core.exceptions.handlers import NotFoundError
    from app.modules.settings.application.site_health_service import SiteHealthService

    found = await SiteHealthService.get_run(db, run_id)
    if found is None:
        raise NotFoundError("SiteHealthRun", f"Run {run_id} not found")
    return found


@router.post(
    "/admin/site-health/optimize-database",
    summary="Run database ANALYZE (admin)",
    dependencies=[Depends(RequirePermissions("settings:write"))],
)
async def optimize_database(
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Update database statistics (WordPress database optimize parity)."""
    from app.modules.settings.application.site_health_service import SiteHealthService

    return await SiteHealthService.optimize_database(db)


# ── WordPress parity: Widget areas ───────────────────────────────────────────


@router.get(
    "/admin/widgets",
    summary="List widget areas (admin)",
    dependencies=[Depends(RequirePermissions("settings:read"))],
)
async def list_widget_areas(
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Return all widget areas with their configured widgets."""
    from app.shared.content.widgets import (
        WIDGET_CONFIG_SCHEMA,
        WIDGET_TYPES,
        WidgetService,
    )

    return {
        "areas": await WidgetService.get_all_areas(db),
        "widget_types": WIDGET_TYPES,
        # Per-type config fields, so the admin form renders a control for each
        # instead of only title/content.
        "config_schema": WIDGET_CONFIG_SCHEMA,
    }


@router.put(
    "/admin/widgets/{area_id}",
    summary="Update a widget area (admin)",
    dependencies=[Depends(RequirePermissions("settings:write"))],
)
async def update_widget_area(
    area_id: str,
    body: dict[str, Any],
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Replace the widgets in a widget area."""
    from app.shared.content.widgets import WidgetService

    return await WidgetService.update_area(db, area_id, body.get("widgets", []))


@router.post(
    "/admin/widgets",
    summary="Create a widget area (admin)",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RequirePermissions("settings:write"))],
)
async def create_widget_area(
    body: dict[str, Any],
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Register a new widget area. The layout must render ``area=<id>`` for it
    to appear in the storefront, but the id and its widgets are operator-owned."""
    from app.shared.content.widgets import WidgetService

    area_id = str(body.get("id", "")).strip()
    if not area_id:
        raise ValidationError("شناسهٔ ناحیه لازم است")
    try:
        area = await WidgetService.create_area(
            db,
            area_id,
            name=str(body.get("name", "")),
            description=str(body.get("description", "")),
        )
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc
    return {"id": area_id, **area}


@router.delete(
    "/admin/widgets/{area_id}",
    summary="Delete a widget area (admin)",
    dependencies=[Depends(RequirePermissions("settings:write"))],
)
async def delete_widget_area(
    area_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Remove an operator-created widget area. Built-in areas are refused."""
    from app.shared.content.widgets import WidgetService

    try:
        removed = await WidgetService.delete_area(db, area_id)
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc
    if not removed:
        raise NotFoundError("WidgetArea", f"ناحیهٔ ویجت یافت نشد: {area_id}")
    return {"deleted": True, "id": area_id}


# ── WordPress parity: Gravatar — removed 2026-10-07 ─────────────────────────
# The /public/gravatar and /public/avatar-options routes were removed with
# the rest of the email feature: Gravatar is keyed on an email address, which
# the platform no longer stores for users or commenters. Uploaded avatars
# still render; guests fall back to initials.


# ── WordPress parity: Widget areas (public read) ─────────────────────────────
# Two segments keep the path unambiguous: a bare /widgets
# would need three, but /public/widgets keeps every public path behind one
# unambiguous segment that the `/{key}` route cannot capture.


@router.get(
    "/public/widgets",
    summary="Public widget areas for the storefront",
)
async def get_public_widgets(
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Return widget areas for rendering, with widget types for the frontend.

    Only areas that actually contain widgets are returned, so an untouched
    install does not ship five empty containers to every page render.
    """
    from app.shared.content.widgets import WIDGET_TYPES, WidgetService

    areas = await WidgetService.get_all_areas(db)
    populated = {
        area_id: area
        for area_id, area in areas.items()
        if area.get("widgets")
    }
    return {"areas": populated, "widget_types": WIDGET_TYPES}


# ── WordPress parity: Public routing options (permalink structure) ──────────
# Consumed by the Next.js middleware (permalink resolution)
# and storefront link builders. Public by nature: it only exposes URL shape
# settings that are already visible in every generated link.


@router.get(
    "/public/routing",
    summary="Public URL-shape options (permalink structure)",
)
async def get_public_routing(
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Return the options that drive public URL generation and resolution.

    Mirrors WordPress's implicit rewrite rules: ``permalink_structure`` and
    ``category_base``/``tag_base`` for archive URLs.

    Also carries the public origin and the store name. Structured data needs
    both as absolute values — a JSON-LD ``logo`` or breadcrumb node is
    meaningless to a crawler without them — and they were being written as
    ``https://example.com/...`` literals in the storefront because no public
    endpoint exposed the real ones.
    """
    from app.modules.settings.application.site_options_service import (
        SiteOptionsService,
        public_base_url,
    )

    keys = (
        "permalink_structure",
        "category_base",
        "tag_base",
    )
    values = {key: (await SiteOptionsService.get(db, key)) for key in keys}
    return {
        "permalink_structure": values["permalink_structure"] or "/blog/%postname%/",
        "category_base": values["category_base"] or "category",
        "tag_base": values["tag_base"] or "tag",
        "site_url": await public_base_url(db),
        "blogname": (await SiteOptionsService.get(db, "blogname")) or "فروشگاه",
    }


# ── WordPress parity: Public branding options (site icon) ────────────────────
# The storefront's generateMetadata reads this to render the operator-chosen
# Site Icon as the favicon. Public by nature — a favicon is served to every
# anonymous visitor, so the option contains no secret. Like /public/widgets,
# the two-segment path keeps it out of the sibling GET /{key} route.


@router.get(
    "/public/branding",
    summary="Public branding options (site icon URL)",
)
async def get_public_branding(
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Return the operator-set Site Icon URL ("" when unset)."""
    from app.modules.settings.application.site_options_service import SiteOptionsService

    icon = await SiteOptionsService.get(db, "site_icon")
    # `contact_email` was removed on 2026-10-07 with the rest of the email
    # feature (the contact_email / admin_email options are gone with it).
    return {
        "site_icon": (icon or "").strip(),
        "store_name": await _public_store_name(db),
    }


async def _public_store_name(db: AsyncSession) -> str:
    """The store's name for public surfaces.

    ``store.identity`` is written by the settings screen as a JSON blob
    (``{"store_name": ...}``) and was read by nothing at all, so the header,
    the footer and the SEO metadata carried a
    hardcoded string that no operator could change. The store name is public —
    it is printed on the shop's own pages — so it belongs on the public
    branding endpoint beside the site icon.

    Resolution order: the settings screen's value, then ``blogname`` (which the
    feed and sitemap already use, and which P0-10 gave the admin a field for),
    then empty. A caller that gets "" shows its own fallback rather than
    publishing a placeholder that looks real.
    """
    import json

    from app.modules.settings.application.site_options_service import SiteOptionsService

    raw = (await SiteOptionsService.get(db, "store.identity")) or ""
    if raw:
        try:
            parsed = json.loads(raw)
        except (TypeError, ValueError):
            parsed = None
        if isinstance(parsed, dict):
            name = str(parsed.get("store_name") or "").strip()
            if name:
                return name
    return (await SiteOptionsService.get(db, "blogname") or "").strip()


# ── WordPress parity: Public discussion options ─────────────────────────────
# The comment form asks here before rendering, so a guest sees "sign in to
# comment" (with a link) instead of filling the form and getting a 422 from
# the server's comment_registration gate. Like the other /public/* routes,
# the path has two segments so the sibling GET /{key} cannot capture it.


@router.get(
    "/public/discussion",
    summary="Public discussion options (comment registration gate, site visibility)",
)
async def get_public_discussion(
    db: AsyncSession = Depends(get_db),
) -> dict[str, bool]:
    """Public-facing switches the storefront needs before it can render.

    ``comment_registration`` gates the comment composer. ``search_visible`` is
    the inverse of WordPress's ``blog_public`` ("Search engine visibility:
    discourage crawlers"), which was seeded and editable but read by nothing —
    a site set to private still served indexable pages to crawlers.
    """
    from app.modules.settings.application.site_options_service import SiteOptionsService

    raw = await SiteOptionsService.get(db, "comment_registration", "0")
    enabled = str(raw if raw is not None else "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    blog_public = str(
        await SiteOptionsService.get(db, "blog_public", "1") or "1"
    ).strip().lower() in {"1", "true", "yes", "on"}
    return {"comment_registration": enabled, "search_visible": blog_public}


@router.get(
    "/public/tax-rate",
    summary="Configured VAT rate percent (public)",
)
async def get_public_tax_rate(
    db: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    """The single configured VAT rate (whole percent).

    Public by nature: the rate is printed on the cart and checkout labels —
    every shopper sees it. Two segments, like the sibling /public/* routes,
    so the earlier GET ``/{key}`` cannot capture it.
    """
    from app.modules.checkout.application import tax_rate_service

    return {"tax_rate_percent": await tax_rate_service.get_tax_rate_percent(db)}


@router.get(
    "/public/robots-extra",
    summary="Operator-added robots.txt lines (public)",
)
async def get_public_robots_extra(
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Return the operator's extra robots.txt rules (verbatim).

    The storefront's /robots.txt route appends these after the generated rules.
    Public by nature: robots.txt is served to every crawler, so the value
    contains no secret. Two segments, like the sibling /public/* routes, so the
    earlier GET ``/{key}`` cannot capture it.
    """
    from app.modules.settings.application.site_options_service import SiteOptionsService

    extra = await SiteOptionsService.get(db, "robots_extra_rules", "") or ""
    return {"extra": extra}


@router.get(
    "/public/breadcrumbs",
    summary="Breadcrumb display settings (public)",
)
async def get_public_breadcrumbs(
    db: AsyncSession = Depends(get_db),
) -> dict[str, str | bool]:
    """Home label, separator, and the blog-crumb toggle.

    The storefront renders trails from these — one source for the visible
    trail and the BreadcrumbList JSON-LD, so they cannot disagree. Public by
    nature: the values appear on every page anyway.
    """
    from app.modules.settings.application.site_options_service import SiteOptionsService

    home = await SiteOptionsService.get(db, "seo_breadcrumb_home_label") or "خانه"
    separator = await SiteOptionsService.get(db, "seo_breadcrumb_separator") or "/"
    show_blog_raw = await SiteOptionsService.get(db, "seo_breadcrumb_show_blog", "1") or "1"
    return {
        "home_label": home,
        "separator": separator,
        "show_blog": show_blog_raw not in ("0", "false", "False", "no"),
    }


# ── WordPress parity: Static front page resolution ───────────────────────────
# show_on_front == "page" + a page_on_front slug publishes a CMS page at "/"
# instead of the built-in home. The storefront asks here before rendering.


@router.get(
    "/public/front-page",
    summary="Resolved static front page (slug), or null for the default home",
)
async def get_public_front_page(
    db: AsyncSession = Depends(get_db),
) -> dict[str, str | None]:
    """Return the slug of the CMS page acting as the front page.

    ``None`` means the storefront renders its built-in default home: either
    ``show_on_front`` is not "page", no page is selected, or the selected
    page is no longer published. A stale ``page_on_front`` must degrade to
    the default home, never to a 404 or a blank storefront.
    """
    from app.modules.settings.application.site_options_service import SiteOptionsService

    mode = (await SiteOptionsService.get(db, "show_on_front")) or "posts"
    if mode.strip().lower() != "page":
        return {"slug": None}
    slug = (await SiteOptionsService.get(db, "page_on_front") or "").strip()
    if not slug:
        return {"slug": None}

    from app.core.exceptions.handlers import NotFoundError

    from app.modules.content.application import cms_page_service

    try:
        await cms_page_service.get_page_by_slug(db, slug, only_published=True)
    except NotFoundError:
        return {"slug": None}
    return {"slug": slug}


# ── WordPress parity: Admin help (inline documentation) ──────────────────────


@router.get(
    "/admin/help",
    summary="List admin help sections",
    dependencies=[Depends(RequirePermissions("settings:read"))],
)
async def list_help_sections() -> dict[str, Any]:
    """Return all registered admin help content."""
    from app.shared.admin.help_system import HelpSystem

    return {"sections": HelpSystem.get_all_help()}


@router.get(
    "/admin/help/{section}",
    summary="Get help for one admin section",
    dependencies=[Depends(RequirePermissions("settings:read"))],
)
async def get_help_section(section: str) -> dict[str, Any]:
    """Return help tabs for a single admin section."""
    from app.shared.admin.help_system import HelpSystem

    return {"section": section, "tabs": HelpSystem.get_help(section)}


# ── Recovery mode (WordPress recovery_mode.php parity) ──────────────────────
# Reachable while the site is paused: the middleware exempts this prefix, so an
# operator can clear the pause without a shell.


@router.get(
    "/admin/recovery-mode",
    dependencies=[Depends(RequirePermissions("settings:write"))],
    summary="Recovery mode status (admin)",
)
async def get_recovery_mode() -> dict[str, Any]:
    from app.core.exceptions.recovery_mode import RecoveryMode

    return {"paused": RecoveryMode.is_paused(), "state": RecoveryMode.state()}


@router.post(
    "/admin/recovery-mode/resume",
    dependencies=[Depends(RequirePermissions("settings:write"))],
    summary="Resume the site from recovery mode (admin)",
)
async def resume_recovery_mode() -> dict[str, Any]:
    from app.core.exceptions.recovery_mode import RecoveryMode

    resumed = RecoveryMode.resume()
    return {
        "resumed": resumed,
        "paused": RecoveryMode.is_paused(),
        "detail": "سایت دوباره فعال شد" if resumed else "سایت در حالت بازیابی نبود",
    }


@router.post(
    "/admin/recovery-mode/send-invitation",
    dependencies=[Depends(RequirePermissions("settings:write"))],
    summary="Mint a one-time recovery key (admin)",
)
async def send_recovery_invitation(
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Mint a recovery key and return it to the caller.

    The email delivery half was removed on 2026-10-07 with the rest of the
    email feature; the key is now returned in the response instead of being
    mailed. That is a deliberate trade: the route is behind
    ``settings:write`` (an authenticated admin session is the caller), the
    key is hashed at rest, and it expires with its own short window — the
    same authority that can already resume the site directly can hold the
    key. ``issued`` says whether a key was minted; ``reason`` explains a
    refusal (the site is not in recovery mode).
    """
    from app.core.exceptions.recovery_mode import RecoveryMode

    issued = RecoveryMode.issue_invitation()
    if not issued.get("issued"):
        return {"issued": False, "reason": issued.get("reason", "not in recovery mode")}
    return {
        "issued": True,
        "key": issued["key"],
        "expires_at": issued.get("expires_at"),
        "reference": issued.get("reference"),
    }


@router.post(
    "/admin/recovery-mode/verify-invitation",
    dependencies=[Depends(RequirePermissions("settings:write"))],
    summary="Verify a recovery key and resume the site (admin)",
)
async def verify_recovery_invitation(
    body: dict[str, Any] = Body(...),
) -> dict[str, Any]:
    """Resume the site if the supplied recovery key is the current, unexpired one."""
    from app.core.exceptions.recovery_mode import RecoveryMode

    key = str((body or {}).get("key", ""))
    if not RecoveryMode.verify_invitation(key):
        return {"resumed": False, "reason": "کلید نامعتبر یا منقضی است"}
    resumed = RecoveryMode.resume()
    return {"resumed": resumed}
