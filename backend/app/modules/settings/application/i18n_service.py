"""Backend i18n string catalogue service (gap 17c).

Manages the ``localization_strings`` table: admin CRUD + bulk upsert, the
public per-locale catalogue with the fallback chain

    locale  →  ``default_locale`` site option  →  the key itself

and the seed defaults sourced from ``frontend/lib/i18n.ts`` when that file
carries a parseable catalogue, else a sensible starter set (``common.*``,
``email.*``).

The TS parser is deliberately regex-based: the catalogue file is plain
``export const <locale>: MessageCatalogue = { "key": "value", ... };`` —
pulling a TypeScript toolchain into the backend to read three object
literals would be overkill. A parse failure (or an empty catalogue, which
is the current state of the file) simply falls back to the starter set.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import select

from app.core.exceptions.handlers import NotFoundError
from app.modules.settings.domain.models import LocalizationString

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

DEFAULT_LOCALE = "fa"
# Mirrors frontend/lib/i18n.ts LOCALE_REGISTRY.
KNOWN_LOCALES: tuple[str, ...] = ("fa", "en", "ar")

# The frontend catalogue lives next to the backend checkout directory.
I18N_TS_CANDIDATES: tuple[Path, ...] = (
    Path(__file__).resolve().parents[5] / "frontend" / "lib" / "i18n.ts",
)

_CATALOGUE_BLOCK_RE = re.compile(
    r"export\s+const\s+(\w+)\s*:\s*MessageCatalogue\s*=\s*\{(.*?)\}\s*;",
    re.DOTALL,
)
_ENTRY_RE = re.compile(r"[\"']([^\"']+)[\"']\s*:\s*[\"']((?:[^\"'\\]|\\.)*)[\"']")

# Starter set used when the TS catalogue is empty/unparseable. Persian is the
# default locale; en/ar provide the baseline for the second/third locales.
STARTER_STRINGS: dict[str, dict[str, str]] = {
    "common.save": {"fa": "ذخیره", "en": "Save", "ar": "حفظ"},
    "common.cancel": {"fa": "انصراف", "en": "Cancel", "ar": "إلغاء"},
    "common.delete": {"fa": "حذف", "en": "Delete", "ar": "حذف"},
    "common.edit": {"fa": "ویرایش", "en": "Edit", "ar": "تحرير"},
    "common.search": {"fa": "جستجو", "en": "Search", "ar": "بحث"},
    "common.loading": {"fa": "در حال بارگذاری…", "en": "Loading…", "ar": "جارٍ التحميل…"},
    "common.confirm": {"fa": "تایید", "en": "Confirm", "ar": "تأكيد"},
    "common.back": {"fa": "بازگشت", "en": "Back", "ar": "رجوع"},
    "common.error": {"fa": "خطایی رخ داد", "en": "Something went wrong", "ar": "حدث خطأ"},
    "common.currency_toman": {"fa": "تومان", "en": "Toman", "ar": "تومان"},
    "email.welcome_subject": {
        "fa": "به فروشگاه ما خوش آمدید",
        "en": "Welcome to our store",
        "ar": "مرحباً بك في متجرنا",
    },
    "email.order_confirmation_subject": {
        "fa": "تایید سفارش شما",
        "en": "Your order is confirmed",
        "ar": "تم تأكيد طلبك",
    },
    "email.order_shipped_subject": {
        "fa": "سفارش شما ارسال شد",
        "en": "Your order has been shipped",
        "ar": "تم شحن طلبك",
    },
    "email.refund_processed_subject": {
        "fa": "بازگشت وجه ثبت شد",
        "en": "Your refund has been processed",
        "ar": "تم معالجة استرداد المبلغ",
    },
}


def _starter_group(key: str) -> str:
    return key.split(".", 1)[0]


def parse_ts_catalogues(source: str) -> dict[str, dict[str, str]]:
    """Extract every ``MessageCatalogue`` literal from the TS source.

    Returns ``{locale: {key: value}}``; locales with an empty literal are
    omitted, and malformed entries are skipped rather than aborting the
    parse.
    """
    catalogues: dict[str, dict[str, str]] = {}
    for match in _CATALOGUE_BLOCK_RE.finditer(source or ""):
        locale, body = match.group(1), match.group(2)
        entries = dict(_ENTRY_RE.findall(body))
        if entries:
            catalogues[locale] = entries
    return catalogues


def load_frontend_catalogues() -> dict[str, dict[str, str]]:
    """Parse ``frontend/lib/i18n.ts``; unparseable/missing → ``{}``."""
    for path in I18N_TS_CANDIDATES:
        try:
            if path.is_file():
                return parse_ts_catalogues(path.read_text(encoding="utf-8"))
        except OSError as exc:
            logger.warning("i18n_ts_catalogue_unreadable", path=str(path), error=str(exc))
    return {}


def seed_payload() -> list[dict[str, Any]]:
    """The seed rows: TS catalogue when parseable, else the starter set."""
    from_ts = load_frontend_catalogues()
    rows: list[dict[str, Any]] = []
    if from_ts:
        for locale, entries in from_ts.items():
            for key, value in entries.items():
                rows.append(
                    {
                        "key": key,
                        "locale": locale,
                        "value": value,
                        "group": _starter_group(key),
                        "is_active": True,
                    }
                )
        return rows
    for key, translations in STARTER_STRINGS.items():
        for locale, value in translations.items():
            rows.append(
                {
                    "key": key,
                    "locale": locale,
                    "value": value,
                    "group": _starter_group(key),
                    "is_active": True,
                }
            )
    return rows


def merge_catalogue(
    locale_map: dict[str, str],
    default_map: dict[str, str],
) -> dict[str, str]:
    """Apply the public-catalogue fallback chain (pure, unit-testable).

    Per key: the requested locale wins, then the default locale, then the
    dotted key itself — mirroring the storefront ``translate`` contract that
    a missing translation must stay *visible*.
    """
    keys = set(locale_map) | set(default_map)
    return {key: locale_map.get(key) or default_map.get(key) or key for key in keys}


async def get_default_locale(db: AsyncSession) -> str:
    """The ``default_locale`` site option (falls back to ``fa``)."""
    from app.modules.settings.application.site_options_service import SiteOptionsService

    return (await SiteOptionsService.get(db, "default_locale")) or DEFAULT_LOCALE


async def get_catalog(db: AsyncSession, locale: str) -> dict[str, str]:
    """Public catalogue for *locale* with the full fallback chain."""
    locale = (locale or DEFAULT_LOCALE).strip().lower() or DEFAULT_LOCALE
    default_locale = await get_default_locale(db)

    stmt = select(LocalizationString).where(
        LocalizationString.is_active.is_(True),
        LocalizationString.locale.in_([locale, default_locale]),
    )
    rows = list((await db.execute(stmt)).scalars().all())

    locale_map: dict[str, str] = {}
    default_map: dict[str, str] = {}
    for row in rows:
        if row.locale == locale:
            locale_map[row.key] = row.value
        elif row.locale == default_locale:
            default_map[row.key] = row.value
    return merge_catalogue(locale_map, default_map)


async def list_strings(
    db: AsyncSession,
    *,
    locale: str | None = None,
    group: str | None = None,
    key_contains: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[LocalizationString], int]:
    """List catalogue rows with optional filters, key-ordered."""
    filters = []
    if locale is not None:
        filters.append(LocalizationString.locale == locale)
    if group is not None:
        filters.append(LocalizationString.group == group)
    if key_contains:
        filters.append(LocalizationString.key.ilike(f"%{key_contains}%"))

    from sqlalchemy import func

    count_stmt = select(func.count()).select_from(LocalizationString)
    if filters:
        count_stmt = count_stmt.where(*filters)
    total = (await db.execute(count_stmt)).scalar() or 0

    stmt = select(LocalizationString)
    if filters:
        stmt = stmt.where(*filters)
    stmt = (
        stmt.order_by(LocalizationString.key, LocalizationString.locale)
        .offset(offset)
        .limit(limit)
    )
    items = list((await db.execute(stmt)).scalars().all())
    return items, int(total)


async def upsert_string(
    db: AsyncSession,
    *,
    key: str,
    locale: str,
    value: str,
    group: str | None = None,
    is_active: bool = True,
) -> LocalizationString:
    """Create or update one (key, locale) row."""
    key = key.strip()
    locale = (locale or DEFAULT_LOCALE).strip().lower()
    if not key:
        from app.core.exceptions.handlers import ValidationError

        raise ValidationError(detail="کلید رشته الزامی است")

    stmt = select(LocalizationString).where(
        LocalizationString.key == key,
        LocalizationString.locale == locale,
    )
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        row = LocalizationString(key=key, locale=locale, value=value, group=group)
    row.value = value
    row.group = group
    row.is_active = is_active
    db.add(row)
    await db.flush()
    return row


async def bulk_upsert(
    db: AsyncSession,
    items: list[dict[str, Any]],
) -> dict[str, int]:
    """Upsert many rows at once; returns ``{created, updated, total}``."""
    created = updated = 0
    for item in items:
        key = str(item.get("key") or "").strip()
        locale = str(item.get("locale") or DEFAULT_LOCALE).strip().lower()
        value = str(item.get("value") or "")
        if not key:
            continue
        stmt = select(LocalizationString).where(
            LocalizationString.key == key,
            LocalizationString.locale == locale,
        )
        row = (await db.execute(stmt)).scalar_one_or_none()
        if row is None:
            row = LocalizationString(
                key=key,
                locale=locale,
                value=value,
                group=item.get("group"),
                is_active=bool(item.get("is_active", True)),
            )
            db.add(row)
            created += 1
        else:
            row.value = value
            row.group = item.get("group", row.group)
            row.is_active = bool(item.get("is_active", row.is_active))
            updated += 1
    await db.flush()
    return {"created": created, "updated": updated, "total": created + updated}


async def delete_string(db: AsyncSession, *, string_id: Any) -> None:
    row = await db.get(LocalizationString, string_id)
    if row is None:
        raise NotFoundError(resource="LocalizationString")
    await db.delete(row)
    await db.flush()


async def seed_defaults(db: AsyncSession) -> dict[str, int]:
    """Insert the default catalogue; existing (key, locale) rows stay untouched."""
    payload = seed_payload()
    existing_stmt = select(LocalizationString.key, LocalizationString.locale)
    existing = {(key, locale) for key, locale in (await db.execute(existing_stmt)).all()}

    created = 0
    for item in payload:
        if (item["key"], item["locale"]) in existing:
            continue
        db.add(
            LocalizationString(
                key=item["key"],
                locale=item["locale"],
                value=item["value"],
                group=item["group"],
                is_active=item["is_active"],
            )
        )
        created += 1
    await db.flush()

    await logger.ainfo("i18n_defaults_seeded", created=created, source="i18n.ts-or-starter")
    return {"created": created, "skipped": len(payload) - created}
