"""Settings API routes."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Body, Depends, Query, Request, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.exceptions.handlers import NotFoundError, ValidationError
from app.core.security.dependencies import RequirePermissions, get_current_user_id
from app.core.security.rate_limiter import limiter
from app.modules.settings.application.privacy_policy_service import PrivacyPolicyService
from app.modules.settings.application.settings_service import SettingsService
from app.modules.settings.schemas.i18n import (
    I18nCatalogResponse,
    I18nSeedResponse,
    I18nStringBulkRequest,
    I18nStringBulkResponse,
    I18nStringCreate,
    I18nStringListResponse,
    I18nStringResponse,
)
from app.modules.settings.schemas.settings import (
    EmailDeliveryLogItem,
    EmailDeliveryLogResponse,
    EmailTestRequest,
    EmailTestResponse,
    MaintenanceSetRequest,
    MaintenanceStateResponse,
    PublicSettingResponse,
    PrivacyPolicyResponse,
    SettingCreateRequest,
    SettingResponse,
    SettingUpdateRequest,
    SMSProviderItem,
    SMSProvidersResponse,
    SMSTestRequest,
    SMSTestResponse,
    SMTPEffectiveConfig,
    TelegramDeliveryLogItem,
    TelegramDeliveryLogResponse,
    TelegramEffectiveConfig,
    TelegramTestRequest,
    TelegramTestResponse,
)
from app.modules.settings.domain.models import PrivacyRequestStatus, PrivacyRequestType
from app.modules.settings.schemas.privacy import (
    PrivacyRequestActionResponse,
    PrivacyRequestAdminItem,
    PrivacyRequestAdminListResponse,
    PrivacyRequestCreate,
    PrivacyRequestConfirmRequest,
    PrivacyRequestItem,
    PrivacyRequestListResponse,
    PrivacyRequestReject,
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

    Declared above ``/{key}`` for the same reason the privacy-policy route is:
    below it, FastAPI matches the catch-all first and this answers 404 for a
    setting named "maintenance", which reads to a client as "the store is fine".
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
    "/public/privacy-policy",
    response_model=PrivacyPolicyResponse,
    summary="The published privacy policy page",
)
async def get_privacy_policy(
    db: AsyncSession = Depends(get_db),
) -> PrivacyPolicyResponse:
    """Return the privacy policy page, or empty fields when none is published.

    Public and unauthenticated on purpose: this is called from the registration,
    comment and checkout forms, before anyone has an account. It carries no
    personal data — a title and a URL — so there is nothing to protect here.

    Declared above ``/{key}`` deliberately. FastAPI matches in declaration order,
    so a route registered after it would be captured as a setting named
    "privacy-policy" and return 404 for every caller, which reads as "this store
    has no privacy policy" on a store that has one.
    """
    policy = await PrivacyPolicyService.get_policy(db)
    if policy is None:
        return PrivacyPolicyResponse()
    return PrivacyPolicyResponse(**policy)


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


# ── Email (SMTP) Provider Management (Admin) ─────────────────────────────────


async def _load_smtp_overrides(db: AsyncSession) -> dict[str, Any] | None:
    """Read the optional runtime ``smtp`` settings row (admin UI edits)."""
    from sqlalchemy import select

    from app.modules.settings.domain.models import SiteSetting

    stmt = select(SiteSetting).where(SiteSetting.key == "smtp")
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row and isinstance(row.value, dict):
        return row.value
    return None


@router.get(
    "/admin/email-providers",
    response_model=SMTPEffectiveConfig,
    summary="Get effective SMTP configuration (admin, secret-free)",
    dependencies=[Depends(RequirePermissions("settings:read"))],
)
async def get_email_provider_config(
    db: AsyncSession = Depends(get_db),
) -> SMTPEffectiveConfig:
    """Return the effective SMTP settings; the password is never exposed."""
    from app.core.config.settings import get_settings
    from app.modules.notifications.application.email_service import get_smtp_config

    overrides = await _load_smtp_overrides(db)
    config = get_smtp_config(overrides)
    env = get_settings()
    if overrides and env.SMTP_HOST:
        source = "mixed"
    elif overrides:
        source = "site_settings"
    else:
        source = "environment"
    return SMTPEffectiveConfig(
        host=config.host,
        port=config.port,
        username=config.username,
        use_tls=config.use_tls,
        from_address=config.from_address,
        from_name=config.from_name,
        timeout_seconds=config.timeout_seconds,
        has_password=bool(config.password),
        is_configured=config.is_configured,
        source=source,
    )


@router.post(
    "/admin/email-providers/test",
    response_model=EmailTestResponse,
    summary="Send a test email via SMTP (admin)",
    dependencies=[Depends(RequirePermissions("settings:write"))],
)
@limiter.limit("5/minute")
async def test_email_provider(
    request: Request,
    payload: EmailTestRequest,
    db: AsyncSession = Depends(get_db),
) -> EmailTestResponse:
    """Dispatch a real test email through the configured SMTP provider.

    When SMTP is not configured nothing is sent, and the response says so:
    success=false, attempts=0, and `error` naming the missing setting. It used
    to report success=true with provider=mock_fallback, which showed the
    operator a green result while no mail had left the platform. The attempt is
    still persisted to the delivery log either way.
    """
    from app.modules.notifications.application import email_service

    overrides = await _load_smtp_overrides(db)
    config = email_service.get_smtp_config(overrides)
    text = payload.message or "این یک ایمیل آزمایشی از پنل مدیریت است."
    # The shell's header is the store's name, the same one every real email
    # uses. The From header keeps `config.from_name` — that one is about the
    # envelope, and an operator who set it to something else there is testing
    # exactly that. The two are different fields that used to share one value.
    html = await email_service.wrap_html_for_store(db, f"<p>{text}</p>")

    success, log_row = await email_service.send_email(
        db,
        recipient=payload.recipient,
        subject="ایمیل آزمایشی — تنظیمات SMTP",
        html_body=html,
        text_body=text,
        template="admin_test",
        config=config,
    )
    await db.commit()
    return EmailTestResponse(
        success=success,
        to=payload.recipient,
        provider=log_row.provider if log_row else ("smtp" if config.is_configured else "mock_fallback"),
        attempts=log_row.attempts if log_row else 0,
        error=log_row.error if log_row else None,
    )


@router.get(
    "/admin/email-delivery-log",
    response_model=EmailDeliveryLogResponse,
    summary="List recent email delivery attempts (admin)",
    dependencies=[Depends(RequirePermissions("settings:read"))],
)
async def list_email_delivery_log(
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> EmailDeliveryLogResponse:
    """Return the most recent email delivery log rows, newest first."""
    from sqlalchemy import func, select

    from app.modules.notifications.domain.models import EmailDeliveryLog

    total = (await db.execute(select(func.count()).select_from(EmailDeliveryLog))).scalar_one()
    stmt = select(EmailDeliveryLog).order_by(EmailDeliveryLog.created_at.desc()).limit(limit)
    rows = list((await db.execute(stmt)).scalars().all())
    return EmailDeliveryLogResponse(
        items=[EmailDeliveryLogItem.model_validate(r) for r in rows],
        total=total,
    )


# ── Telegram Bot Provider Management (Admin) ───────────────────────────────


async def _load_telegram_overrides(db: AsyncSession) -> dict[str, Any] | None:
    """Read the optional runtime ``telegram`` settings row (admin UI edits)."""
    from sqlalchemy import select

    from app.modules.settings.domain.models import SiteSetting

    stmt = select(SiteSetting).where(SiteSetting.key == "telegram")
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row and isinstance(row.value, dict):
        return row.value
    return None


@router.get(
    "/admin/telegram-provider",
    response_model=TelegramEffectiveConfig,
    summary="Get effective Telegram bot configuration (admin, secret-free)",
    dependencies=[Depends(RequirePermissions("settings:read"))],
)
async def get_telegram_provider_config(
    db: AsyncSession = Depends(get_db),
) -> TelegramEffectiveConfig:
    """Return the effective Telegram settings; the bot token is never exposed."""
    from app.core.config.settings import get_settings
    from app.modules.notifications.application.telegram_service import get_telegram_config

    overrides = await _load_telegram_overrides(db)
    config = get_telegram_config(overrides)
    env = get_settings()
    if overrides and env.TELEGRAM_BOT_TOKEN:
        source = "mixed"
    elif overrides:
        source = "site_settings"
    else:
        source = "environment"
    token = config.bot_token.strip()
    return TelegramEffectiveConfig(
        bot_username=config.bot_username,
        api_base_url=config.api_base_url,
        timeout_seconds=config.timeout_seconds,
        has_token=bool(token),
        token_masked=f"••••{token[-4:]}" if token else None,
        is_configured=config.is_configured,
        source=source,
    )


@router.post(
    "/admin/telegram-provider/test",
    response_model=TelegramTestResponse,
    summary="Send a test Telegram message via the Bot API (admin)",
    dependencies=[Depends(RequirePermissions("settings:write"))],
)
@limiter.limit("5/minute")
async def test_telegram_provider(
    request: Request,
    payload: TelegramTestRequest,
    db: AsyncSession = Depends(get_db),
) -> TelegramTestResponse:
    """Dispatch a real test Telegram message to a chat_id.

    When the bot token is not configured this exercises the mock-fallback
    path and reports it (success=true, provider=mock_fallback) so admins can
    verify the wiring before credentials exist. The attempt is persisted to
    the telegram delivery log either way.
    """
    from app.modules.notifications.application import telegram_service

    overrides = await _load_telegram_overrides(db)
    config = telegram_service.get_telegram_config(overrides)
    text = payload.message or "این یک پیام آزمایشی از پنل مدیریت است."

    success, log_row = await telegram_service.send_telegram_message(
        db,
        chat_id=payload.chat_id,
        title="پیام آزمایشی — تنظیمات تلگرام",
        body=text,
        config=config,
    )
    await db.commit()
    return TelegramTestResponse(
        success=success,
        to=payload.chat_id,
        provider=(
            log_row.provider
            if log_row
            else ("telegram_bot" if config.is_configured else "mock_fallback")
        ),
        attempts=log_row.attempts if log_row else 0,
        error=log_row.error if log_row else None,
    )


@router.get(
    "/admin/telegram-delivery-log",
    response_model=TelegramDeliveryLogResponse,
    summary="List recent Telegram delivery attempts (admin)",
    dependencies=[Depends(RequirePermissions("settings:read"))],
)
async def list_telegram_delivery_log(
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> TelegramDeliveryLogResponse:
    """Return the most recent telegram delivery log rows, newest first."""
    from sqlalchemy import func, select

    from app.modules.notifications.domain.models import TelegramDeliveryLog

    total = (
        await db.execute(select(func.count()).select_from(TelegramDeliveryLog))
    ).scalar_one()
    stmt = (
        select(TelegramDeliveryLog).order_by(TelegramDeliveryLog.created_at.desc()).limit(limit)
    )
    rows = list((await db.execute(stmt)).scalars().all())
    return TelegramDeliveryLogResponse(
        items=[TelegramDeliveryLogItem.model_validate(r) for r in rows],
        total=total,
    )



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


# ── WordPress parity: Privacy / GDPR tools ───────────────────────────────────


@router.get(
    "/admin/privacy/export/{user_id}",
    summary="Export all data for a user (GDPR)",
    dependencies=[Depends(RequirePermissions("users:read"))],
)
async def export_user_data(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Export a user's personal data as JSON (GDPR right of access).

    Two parts, and both matter:

    * ``data`` — the account-level payload (profile, full addresses) plus the
      per-source archive from the registry, covering every user-owned table.
    * ``report`` — what each source contributed and which ones failed. The
      request's own ``status`` is set to ``partial`` when that report is
      incomplete, so the account page — which reads status, not report — cannot
      present a file that is missing a table as the subject's whole dataset.
      Consumers that read this payload directly should still check
      ``report["complete"]``.
    """
    from app.modules.settings.application.privacy_service import PrivacyService
    from app.modules.settings.application.privacy_sources import collect_export

    account = await PrivacyService.export_user_data(db, user_id)
    if isinstance(account, dict) and "error" in account:
        return account

    archive = await collect_export(db, user_id)
    return {
        **account,
        "sources": archive["data"],
        "report": archive["report"],
    }


@router.post(
    "/admin/privacy/erase/{user_id}",
    summary="Erase/anonymize a user's data (GDPR)",
    dependencies=[Depends(RequirePermissions("users:write"))],
)
async def erase_user_data(
    user_id: uuid.UUID,
    anonymize: bool = Query(True, description="Anonymize (true) or hard-delete (false)"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Erase a user's personal data (GDPR right to erasure)."""
    from app.modules.settings.application.privacy_service import PrivacyService

    return await PrivacyService.erase_user_data(db, user_id, anonymize=anonymize)


# ── GDPR data-subject request queue ──────────────────────────────────────────
# The two routes above are the operator's manual path and stay exactly as
# they were. Everything below is the subject-facing queue: the customer raises
# the request, an operator works the queue, and the customer collects the
# result. No handler on the customer side accepts a user id — the subject is
# ``Depends(get_current_user_id)``, so there is no parameter to aim one
# account's request at another.


@router.post(
    "/privacy/requests",
    response_model=PrivacyRequestItem,
    status_code=status.HTTP_201_CREATED,
    summary="Raise a GDPR data-subject request for your own account",
)
@limiter.limit("5/hour")
async def create_privacy_request(
    body: PrivacyRequestCreate,
    request: Request,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> PrivacyRequestItem:
    """Request an export or erasure of your own personal data.

    Rate-limited harder than any other authenticated write: a runaway client
    should not be able to fill the operator queue faster than it can be
    triaged, and the erase branch is destructive.
    """
    from app.modules.settings.application.privacy_request_service import (
        PrivacyRequestService,
    )

    row = await PrivacyRequestService.submit(
        db,
        user_id=user_id,
        request_type=body.type,
        reason=body.reason,
        password=body.password,
    )
    return _to_item(row)


@router.get(
    "/privacy/requests",
    response_model=PrivacyRequestListResponse,
    summary="List your own GDPR data-subject requests",
)
async def list_privacy_requests(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> PrivacyRequestListResponse:
    """Every request this account has raised, newest first."""
    from app.modules.settings.application.privacy_request_service import (
        PrivacyRequestService,
    )

    rows = await PrivacyRequestService.list_for_user(db, user_id=user_id)
    return PrivacyRequestListResponse(items=[_to_item(r) for r in rows])


@router.get(
    "/privacy/requests/{request_id}",
    response_model=PrivacyRequestItem,
    summary="Read the status of one of your own requests",
)
async def get_privacy_request(
    request_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> PrivacyRequestItem:
    """Status of one request, scoped to the caller.

    Another account's request id answers 404, not 403: a 403 would confirm
    the id is real, which leaks the existence of somebody else's request.
    """
    from app.modules.settings.application.privacy_request_service import (
        PrivacyRequestService,
    )

    return _to_item(
        await PrivacyRequestService.get_for_user(db, user_id=user_id, request_id=request_id)
    )


@router.post(
    "/privacy/requests/{request_id}/confirm",
    summary="Confirm a GDPR erase request with the emailed code",
)
async def confirm_privacy_request(
    request_id: uuid.UUID,
    body: PrivacyRequestConfirmRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Second-factor confirmation for an irreversible erase request.

    ``PrivacyRequestService.confirm`` existed and worked, but no route ever
    called it, so the OTP the submit handler issued could not be redeemed: a
    user could raise an erase request and never get past the second step. The
    code is checked against *this request* rather than against a session, so a
    stolen password is not enough.
    """
    from app.modules.settings.application.privacy_request_service import (
        PrivacyRequestService,
    )

    request = await PrivacyRequestService.confirm(
        db,
        request_id=request_id,
        user_id=user_id,
        code=body.code,
    )
    await db.commit()
    return _to_item(request)


@router.get(
    "/privacy/requests/{request_id}/result",
    summary="Collect the export document for one of your own requests",
)
async def get_privacy_request_result(
    request_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Return the produced export payload, once.

    Served inline to the authenticated owner rather than from a download URL.
    A file would need a second credential (a token in the path or a public
    static URL), and a public one is a guessable address holding a full copy
    of somebody's personal data. This response is the subject's own copy, over
    the same authenticated session as the account page it was requested from.

    The payload is deleted as it is read: see
    ``PrivacyRequestService.get_result`` for why a GDPR-mandated copy is not
    kept in the database.
    """
    from app.modules.settings.application.privacy_request_service import (
        PrivacyRequestService,
    )

    return await PrivacyRequestService.get_result(db, user_id=user_id, request_id=request_id)


@router.get(
    "/privacy/requests/{request_id}/result.zip",
    summary="Collect the export as a structured ZIP (index.html + per-source JSON)",
)
async def get_privacy_request_result_zip(
    request_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """The same export as the JSON route, packaged as a ZIP.

    The raw JSON was a wall of nested objects: a subject who asked for their
    data got one file with no way to tell which table was which. This lays it
    out like every other data-export tool — an ``index.html`` that lists what
    is inside and links each source, one JSON file per source, and a
    ``_report.json`` naming what failed.

    Same one-shot rule as the JSON route: reading the payload clears it, so
    the subject collects their copy once and the database does not keep a
    second one.
    """
    import io
    import zipfile

    from app.modules.settings.application.privacy_request_service import (
        PrivacyRequestService,
    )
    from app.modules.settings.application.privacy_sources import build_export_zip

    payload = await PrivacyRequestService.get_result(
        db, user_id=user_id, request_id=request_id
    )
    # `get_result` returns the stored archive: the per-source data and the
    # report. Older rows may hold the bare payload shape; wrap it so the
    # builder always sees the same two keys.
    if "data" in payload and "report" in payload:
        archive = payload
    else:
        archive = {"data": payload, "report": {"complete": True, "failed_sources": []}}

    blob = build_export_zip(archive, subject_label="شما")
    return Response(
        content=blob,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="data-export-{request_id}.zip"',
        },
    )


@router.get(
    "/admin/privacy/requests",
    response_model=PrivacyRequestAdminListResponse,
    summary="List GDPR data-subject requests (admin)",
    dependencies=[Depends(RequirePermissions("users:read"))],
)
async def list_privacy_requests_admin(
    status_filter: PrivacyRequestStatus | None = Query(None, alias="status"),
    type_filter: PrivacyRequestType | None = Query(None, alias="type"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> PrivacyRequestAdminListResponse:
    """The operator queue, oldest unhandled first."""
    from app.modules.settings.application.privacy_request_service import (
        PrivacyRequestService,
    )

    rows, total = await PrivacyRequestService.list_all(
        db,
        status_filter=status_filter,
        type_filter=type_filter,
        skip=skip,
        limit=limit,
    )
    return PrivacyRequestAdminListResponse(
        items=[
            PrivacyRequestAdminItem(
                **_admin_fields(r),
                user_id=r.user_id,
                resolved_by=r.resolved_by,
                result_expires_at=r.result_expires_at,
            )
            for r in rows
        ],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.post(
    "/admin/privacy/requests/{request_id}/export",
    response_model=PrivacyRequestActionResponse,
    summary="Run the export for a queued GDPR request (admin)",
    dependencies=[Depends(RequirePermissions("users:read"))],
)
async def run_privacy_request_export(
    request_id: uuid.UUID,
    admin_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> PrivacyRequestActionResponse:
    """Execute the subject's Article 15 request and store the payload."""
    from app.modules.settings.application.privacy_request_service import (
        PrivacyRequestService,
    )

    row = await PrivacyRequestService.run_export(
        db, request_id=request_id, admin_id=admin_id
    )
    return PrivacyRequestActionResponse(
        id=row.id,
        user_id=row.user_id,
        type=row.type,
        status=row.status,
        admin_note=row.admin_note,
        resolved_at=row.resolved_at,
        has_result=True,
    )


@router.post(
    "/admin/privacy/requests/{request_id}/erase",
    response_model=PrivacyRequestActionResponse,
    summary="Run the erasure for a queued GDPR request (admin)",
    dependencies=[Depends(RequirePermissions("users:write"))],
)
async def run_privacy_request_erase(
    request_id: uuid.UUID,
    admin_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> PrivacyRequestActionResponse:
    """Execute the subject's Article 17 request.

    Anonymization only. ``anonymize=False`` (hard delete) stays on the manual
    operator route above, which is for a support escalation and not for a
    request a customer can file against themselves.
    """
    from app.modules.settings.application.privacy_request_service import (
        PrivacyRequestService,
    )

    row = await PrivacyRequestService.run_erase(db, request_id=request_id, admin_id=admin_id)
    return PrivacyRequestActionResponse(
        id=row.id,
        user_id=row.user_id,
        type=row.type,
        status=row.status,
        admin_note=row.admin_note,
        resolved_at=row.resolved_at,
    )


@router.post(
    "/admin/privacy/requests/{request_id}/reject",
    response_model=PrivacyRequestActionResponse,
    summary="Reject a queued GDPR request with a reason (admin)",
    dependencies=[Depends(RequirePermissions("users:write"))],
)
async def reject_privacy_request(
    request_id: uuid.UUID,
    body: PrivacyRequestReject,
    admin_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> PrivacyRequestActionResponse:
    """Decline a request. The reason is mandatory, not optional."""
    from app.modules.settings.application.privacy_request_service import (
        PrivacyRequestService,
    )

    row = await PrivacyRequestService.reject(
        db, request_id=request_id, admin_id=admin_id, note=body.note
    )
    return PrivacyRequestActionResponse(
        id=row.id,
        user_id=row.user_id,
        type=row.type,
        status=row.status,
        admin_note=row.admin_note,
        resolved_at=row.resolved_at,
    )


@router.post(
    "/admin/privacy/requests/purge-expired",
    summary="Delete stored exports past their expiry (admin)",
    dependencies=[Depends(RequirePermissions("settings:write"))],
)
async def purge_expired_privacy_results(
    db: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    """Drop export payloads whose retention window has closed."""
    from app.modules.settings.application.privacy_request_service import (
        PrivacyRequestService,
    )

    return {"purged": await PrivacyRequestService.purge_expired(db)}


def _has_result(row: Any) -> bool:
    """Whether a collectable payload exists, as of *now*.

    The stored expiry is compared here rather than trusted to the client: a
    button that offers a download for an expired payload turns into a 404
    the customer cannot act on.
    """
    from datetime import UTC, datetime

    if row.result_payload is None:
        return False
    if row.result_expires_at is None:
        return True
    return row.result_expires_at > datetime.now(UTC)


def _to_item(row: Any) -> PrivacyRequestItem:
    return PrivacyRequestItem(
        id=row.id,
        type=row.type,
        status=row.status,
        reason=row.reason,
        verified_at=row.verified_at,
        confirmed_at=row.confirmed_at,
        admin_note=row.admin_note,
        resolved_at=row.resolved_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
        has_result=_has_result(row),
    )


def _admin_fields(row: Any) -> dict[str, Any]:
    return {
        "id": row.id,
        "type": row.type,
        "status": row.status,
        "reason": row.reason,
        "verified_at": row.verified_at,
        "confirmed_at": row.confirmed_at,
        "admin_note": row.admin_note,
        "resolved_at": row.resolved_at,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        "has_result": _has_result(row),
    }


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


# ── WordPress parity: Gravatar (public) ──────────────────────────────────────
# NOTE: this must NOT be mounted on ``router`` directly — the sibling GET
# ``/{key}`` route (setting-by-key) matches any single segment and is declared
# earlier, so a bare ``/gravatar`` would be served by it and demand auth.
# Declaring the path with two segments keeps the two unambiguous.


@router.get(
    "/public/gravatar",
    summary="Resolve a Gravatar URL for an email",
)
async def get_gravatar_url(
    email: str = Query(..., description="Email address to hash"),
    size: int = Query(80, ge=1, le=2048),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str | None]:
    """Return the Gravatar image URL for the given email.

    Honours the site-wide avatar options: ``show_avatars`` off returns a null
    url (the caller renders initials), and ``avatar_default``/``avatar_rating``
    drive the gravatar ``d=``/``r=`` params instead of the old hardcoded
    ``mp``/``g``. The route used to ignore all three, so an operator who turned
    avatars off or picked an identicon default saw no effect on this path.
    """
    from app.shared.content.gravatar import avatar_options, gravatar_url

    options = await avatar_options(db)
    if not options.show:
        return {"url": None}
    return {
        "url": gravatar_url(
            email, size=size, default=options.default, rating=options.rating
        )
    }


@router.get(
    "/public/avatar-options",
    summary="Public avatar options (show toggle, default, rating)",
)
async def get_public_avatar_options(
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """The site-wide avatar settings, for storefront-side avatar rendering.

    Two segments, like the sibling /public/* routes, so the earlier GET
    ``/{key}`` (setting-by-key) cannot capture it and demand auth.
    """
    from app.shared.content.gravatar import (
        VALID_AVATAR_DEFAULTS,
        VALID_AVATAR_RATINGS,
        avatar_options,
    )

    options = await avatar_options(db)
    return {
        "show_avatars": options.show,
        "avatar_default": options.default,
        "avatar_rating": options.rating,
        "defaults": sorted(VALID_AVATAR_DEFAULTS),
        "ratings": sorted(VALID_AVATAR_RATINGS),
    }


# ── WordPress parity: Widget areas (public read) ─────────────────────────────
# Two segments for the same reason as /public/gravatar above: a bare /widgets
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


# ── WordPress parity: Public routing options (permalink + locales) ───────────
# Consumed by the Next.js middleware (permalink resolution, locale prefixes)
# and storefront link builders. Public by nature: it only exposes URL shape
# settings that are already visible in every generated link.


@router.get(
    "/public/routing",
    summary="Public URL-shape options (permalink structure, locale config)",
)
async def get_public_routing(
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Return the options that drive public URL generation and resolution.

    Mirrors WordPress's implicit rewrite rules: ``permalink_structure``,
    ``category_base``/``tag_base`` for archive URLs, and the i18n locale
    registry (``enabled_locales``, ``default_locale``).

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
        "enabled_locales",
        "default_locale",
    )
    values = {key: (await SiteOptionsService.get(db, key)) for key in keys}
    return {
        "permalink_structure": values["permalink_structure"] or "/blog/%postname%/",
        "category_base": values["category_base"] or "category",
        "tag_base": values["tag_base"] or "tag",
        "enabled_locales": values["enabled_locales"] or "fa",
        "default_locale": values["default_locale"] or "fa",
        "site_url": await public_base_url(db),
        "blogname": (await SiteOptionsService.get(db, "blogname")) or "فروشگاه",
    }


# ── WordPress parity: Public branding options (site icon) ────────────────────
# The storefront's generateMetadata reads this to render the operator-chosen
# Site Icon as the favicon. Public by nature — a favicon is served to every
# anonymous visitor, so the option contains no secret. Like /public/gravatar,
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
    contact_email = (await SiteOptionsService.get(db, "contact_email") or "").strip()
    if not contact_email:
        contact_email = (await SiteOptionsService.get(db, "admin_email") or "").strip()
    # The seed value is a placeholder, so falling back to it would publish
    # "admin@example.com" on the storefront. Better to show nothing than a
    # placeholder that looks real to a visitor.
    if contact_email.endswith("@example.com"):
        contact_email = ""
    return {
        "site_icon": (icon or "").strip(),
        "contact_email": contact_email,
        "store_name": await _public_store_name(db),
    }


async def _public_store_name(db: AsyncSession) -> str:
    """The store's name for public surfaces.

    ``store.identity`` is written by the settings screen as a JSON blob
    (``{"store_name": ...}``) and was read by nothing at all, so the header,
    the footer, the SEO metadata and every transactional email carried a
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


# ── WordPress parity: Switchable themes (appearance) ─────────────────────────
# A theme is a named token set; activation copies it into the ``theme``
# single type that the storefront already consumes, so switching is live
# without a deploy. Builtin presets are provisioned on first list.


@router.get(
    "/admin/themes",
    summary="Admin — List switchable themes",
    dependencies=[Depends(RequirePermissions("settings:read"))],
)
async def list_themes(
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    from app.modules.settings.application import theme_service

    themes = await theme_service.list_themes(db)
    return {
        "items": [
            {
                "id": str(theme.id),
                "slug": theme.slug,
                "name": theme.name,
                "tokens": theme.tokens,
                "is_builtin": theme.is_builtin,
                "is_active": theme.is_active,
            }
            for theme in themes
        ]
    }


@router.post(
    "/admin/themes",
    status_code=status.HTTP_201_CREATED,
    summary="Admin — Save current tokens as a new theme",
    dependencies=[Depends(RequirePermissions("settings:write"))],
)
async def create_theme(
    body: dict[str, Any] = Body(...),
    actor_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    from app.modules.settings.application import theme_service

    name = str(body.get("name") or "").strip()
    if not name:
        raise ValidationError(detail="نام پوسته الزامی است.")
    theme = await theme_service.create_theme(
        db, name=name, tokens=body.get("tokens") or {}, actor_id=actor_id
    )
    return {
        "id": str(theme.id),
        "slug": theme.slug,
        "name": theme.name,
        "tokens": theme.tokens,
        "is_builtin": theme.is_builtin,
        "is_active": theme.is_active,
    }


@router.post(
    "/admin/themes/{theme_id}/activate",
    summary="Admin — Activate a theme (live, no deploy)",
    dependencies=[Depends(RequirePermissions("settings:write"))],
)
async def activate_theme(
    theme_id: uuid.UUID,
    actor_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    from app.modules.settings.application import theme_service

    theme = await theme_service.activate_theme(db, theme_id=theme_id, actor_id=actor_id)
    return {
        "id": str(theme.id),
        "slug": theme.slug,
        "name": theme.name,
        "is_active": theme.is_active,
        "message": f"پوسته «{theme.name}» فعال شد.",
    }


@router.delete(
    "/admin/themes/{theme_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Admin — Delete an operator-created theme",
    dependencies=[Depends(RequirePermissions("settings:write"))],
)
async def delete_theme(
    theme_id: uuid.UUID,
    actor_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> None:
    from app.modules.settings.application import theme_service

    await theme_service.delete_theme(db, theme_id=theme_id, actor_id=actor_id)


# ── Backend i18n string catalogue (gap 17c) ──────────────────────────────────


@router.get(
    "/public/i18n",
    response_model=I18nCatalogResponse,
    summary="Public UI-string catalogue for a locale",
)
async def get_public_i18n_catalog(
    locale: str = Query("fa", min_length=2, max_length=10),
    db: AsyncSession = Depends(get_db),
) -> I18nCatalogResponse:
    """Return ``{key: value}`` for active strings with the fallback chain
    ``locale → default_locale site option → key`` (missing keys resolve to
    the dotted key itself, matching the storefront ``translate`` contract).
    """
    from app.modules.settings.application import i18n_service

    strings = await i18n_service.get_catalog(db, locale)
    return I18nCatalogResponse(
        locale=locale,
        default_locale=await i18n_service.get_default_locale(db),
        strings=strings,
    )


@router.get(
    "/admin/i18n/strings",
    response_model=I18nStringListResponse,
    summary="List localization strings (admin)",
    dependencies=[Depends(RequirePermissions("settings:read"))],
)
async def list_i18n_strings(
    locale: str | None = Query(None, max_length=10),
    group: str | None = Query(None, max_length=100),
    key: str | None = Query(None, max_length=200, description="Substring key filter"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> I18nStringListResponse:
    from app.modules.settings.application import i18n_service

    items, total = await i18n_service.list_strings(
        db, locale=locale, group=group, key_contains=key, limit=limit, offset=offset
    )
    return I18nStringListResponse(
        items=[I18nStringResponse.model_validate(r) for r in items],
        total=total,
    )


@router.post(
    "/admin/i18n/strings",
    response_model=I18nStringResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upsert one localization string (admin)",
    dependencies=[Depends(RequirePermissions("settings:write"))],
)
async def upsert_i18n_string(
    payload: I18nStringCreate,
    db: AsyncSession = Depends(get_db),
) -> I18nStringResponse:
    from app.modules.settings.application import i18n_service

    row = await i18n_service.upsert_string(
        db,
        key=payload.key,
        locale=payload.locale,
        value=payload.value,
        group=payload.group,
        is_active=payload.is_active,
    )
    return I18nStringResponse.model_validate(row)


@router.put(
    "/admin/i18n/strings/bulk",
    response_model=I18nStringBulkResponse,
    summary="Bulk upsert localization strings (admin)",
    dependencies=[Depends(RequirePermissions("settings:write"))],
)
async def bulk_upsert_i18n_strings(
    payload: I18nStringBulkRequest,
    db: AsyncSession = Depends(get_db),
) -> I18nStringBulkResponse:
    from app.modules.settings.application import i18n_service

    counts = await i18n_service.bulk_upsert(db, [item.model_dump() for item in payload.items])
    return I18nStringBulkResponse(**counts)


@router.post(
    "/admin/i18n/seed-defaults",
    response_model=I18nSeedResponse,
    summary="Seed default UI strings from the frontend catalogue (admin)",
    dependencies=[Depends(RequirePermissions("settings:write"))],
)
async def seed_i18n_defaults(
    db: AsyncSession = Depends(get_db),
) -> I18nSeedResponse:
    """Insert defaults from ``frontend/lib/i18n.ts`` (or the starter set);
    existing (key, locale) rows are left alone."""
    from app.modules.settings.application import i18n_service

    return I18nSeedResponse(**await i18n_service.seed_defaults(db))


@router.delete(
    "/admin/i18n/strings/{string_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a localization string (admin)",
    dependencies=[Depends(RequirePermissions("settings:write"))],
)
async def delete_i18n_string(
    string_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    from app.modules.settings.application import i18n_service

    await i18n_service.delete_string(db, string_id=string_id)


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
    summary="Email a one-time recovery key to the admin (admin)",
)
async def send_recovery_invitation(
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Mint a recovery key and email it to the site admin.

    WordPress's "recovery mode" email: when a fatal error pauses the site, the
    admin is locked out of the very panel they would use to fix it. This sends
    them a one-time key — hashed at rest, short-lived — they can present to
    resume without a shell.

    The key is *not* returned here: it goes to the admin's mailbox, and putting
    it in an HTTP response would let anyone who can reach this route read it
    out of the body. The response says only whether the mail left.
    """
    from app.core.exceptions.recovery_mode import RecoveryMode
    from app.modules.notifications.application.email_service import send_email
    from app.modules.settings.application.site_options_service import SiteOptionsService

    issued = RecoveryMode.issue_invitation()
    if not issued.get("issued"):
        return {"sent": False, "reason": issued.get("reason", "not in recovery mode")}

    recipient = (await SiteOptionsService.get(db, "admin_email") or "").strip()
    if not recipient:
        return {"sent": False, "reason": "no admin_email is configured"}

    reference = issued.get("reference", "")
    html = (
        '<div dir="rtl" style="font-family:Tahoma,sans-serif">'
        "<p>سایت شما در حالت بازیابی است و برای بازگرداندن آن به یک کلید "
        "موقت نیاز است.</p>"
        f"<p>کد بازیابی: <code>{issued['key']}</code></p>"
        f"<p>شناسهٔ رخداد: <code>{reference}</code></p>"
        "<p>این کلید کوتاه‌عمر است. پس از رفع مشکل، سایت را از پنل مدیریت "
        "دوباره فعال کنید.</p>"
        "</div>"
    )
    text = (
        "سایت شما در حالت بازیابی است.\n"
        f"کد بازیابی: {issued['key']}\n"
        f"شناسهٔ رخداد: {reference}\n"
        "این کلید کوتاه‌عمر است.\n"
    )
    success, _log = await send_email(
        db,
        recipient=recipient,
        subject="کلید بازیابی سایت",
        html_body=html,
        text_body=text,
        template="recovery_mode",
    )
    await db.commit()
    return {
        "sent": success,
        "recipient": recipient,
        "reason": None if success else "ارسال ایمیل ناموفق بود (تنظیمات SMTP را بررسی کنید).",
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
