"""Dynamic content-type builder service: type CRUD + validated entries.

Every entry write is validated against its type's field definitions —
required fields, primitive types, enum options, component sub-objects, and
relation targets (which must point at an existing content type).
"""

from __future__ import annotations

import re
import uuid
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import func, select

from app.core.exceptions.handlers import NotFoundError, ValidationError
from app.modules.content.domain.builder import FIELD_TYPES, ContentEntry, ContentType, ContentTypeKind
from app.modules.content.domain.models import PageStatus

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_FIELD_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{0,60}$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_TYPE_SLUG_RE = re.compile(r"^[a-z][a-z0-9-]{1,100}$")

# Type slugs surface as public routes (/content-types/<slug>/entries) and must
# never shadow storefront paths.
RESERVED_TYPE_SLUGS: frozenset[str] = frozenset(
    {"admin", "api", "pages", "menus", "faqs", "blocks", "single-types", "content-types", "entries"}
)


# ── Field definition validation (schema authoring) ──────────────────────────


def validate_field_definitions(fields: list[dict[str, Any]]) -> None:
    """Reject malformed type schemas before they can be stored."""
    if not fields:
        raise ValidationError("حداقل یک فیلد برای تایپ محتوا لازم است")
    names: set[str] = set()
    for field in fields:
        name = field.get("name", "")
        ftype = field.get("type", "")
        if not _FIELD_NAME_RE.match(name):
            raise ValidationError(f"نام فیلد «{name}» معتبر نیست (a-z, 0-9, _)")
        if name in names:
            raise ValidationError(f"فیلد تکراری: «{name}»")
        names.add(name)
        if ftype not in FIELD_TYPES:
            raise ValidationError(f"نوع فیلد «{ftype}» پشتیبانی نمی‌شود")
        if ftype == "enum" and not field.get("options"):
            raise ValidationError(f"فیلد enum «{name}» باید options داشته باشد")
        if ftype == "relation" and not field.get("target"):
            raise ValidationError(f"فیلد relation «{name}» باید target (slug تایپ مقصد) داشته باشد")
        if ftype == "component":
            sub = field.get("fields")
            if not isinstance(sub, list) or not sub:
                raise ValidationError(f"کامپوننت «{name}» باید fields داشته باشد")
            validate_field_definitions(sub)


def _validate_scalar(ftype: str, value: Any, *, path: str) -> None:
    if ftype in ("string", "text", "richtext"):
        if not isinstance(value, str):
            raise ValidationError(f"فیلد {path} باید رشته باشد")
    elif ftype == "slug":
        if not isinstance(value, str) or not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", value):
            raise ValidationError(f"فیلد {path} باید slug معتبر باشد (a-z, 0-9, -)")
    elif ftype == "email":
        if not isinstance(value, str) or not _EMAIL_RE.match(value):
            raise ValidationError(f"فیلد {path} باید ایمیل معتبر باشد")
    elif ftype == "url":
        if not isinstance(value, str) or not re.match(r"^(https?://|/)", value):
            raise ValidationError(f"فیلد {path} باید نشانی معتبر باشد")
    elif ftype == "integer":
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValidationError(f"فیلد {path} باید عدد صحیح باشد")
    elif ftype == "decimal":
        try:
            Decimal(str(value))
        except (InvalidOperation, ValueError) as exc:
            raise ValidationError(f"فیلد {path} باید عدد اعشاری باشد") from exc
    elif ftype == "boolean":
        if not isinstance(value, bool):
            raise ValidationError(f"فیلد {path} باید بولین باشد")
    elif ftype == "date":
        if isinstance(value, str):
            try:
                date.fromisoformat(value)
                return
            except ValueError:
                pass
        if not isinstance(value, date) or isinstance(value, datetime):
            raise ValidationError(f"فیلد {path} باید تاریخ (YYYY-MM-DD) باشد")
    elif ftype == "datetime":
        if isinstance(value, str):
            try:
                datetime.fromisoformat(value.replace("Z", "+00:00"))
                return
            except ValueError:
                pass
        if not isinstance(value, datetime):
            raise ValidationError(f"فیلد {path} باید تاریخ-ساعت معتبر باشد")
    elif ftype == "media":
        try:
            uuid.UUID(str(value))
        except ValueError as exc:
            raise ValidationError(f"فیلد {path} باید شناسه رسانه (UUID) باشد") from exc
    elif ftype == "relation":
        try:
            uuid.UUID(str(value))
        except ValueError as exc:
            raise ValidationError(f"فیلد {path} باید شناسه ورودی مقصد (UUID) باشد") from exc


def validate_entry_data(
    fields: list[dict[str, Any]], data: dict[str, Any], *, path: str = ""
) -> dict[str, Any]:
    """Validate an entry payload against field definitions; returns data with defaults applied."""
    if not isinstance(data, dict):
        raise ValidationError("بدنه ورودی باید آبجکت باشد")
    known = {f["name"] for f in fields}
    unknown = set(data) - known
    if unknown:
        raise ValidationError(f"فیلدهای خارج از طرح: {sorted(unknown)}")

    out = dict(data)
    for field in fields:
        name = field["name"]
        ftype = field["type"]
        value = out.get(name)
        label = f"{path}.{name}".lstrip(".")

        if value is None:
            if field.get("required"):
                raise ValidationError(f"فیلد {label} الزامی است")
            if "default" in field:
                out[name] = field["default"]
            continue

        if field.get("multiple"):
            if not isinstance(value, list):
                raise ValidationError(f"فیلد {label} باید آرایه باشد")
            for i, item in enumerate(value):
                _validate_one(field, item, path=f"{label}[{i}]")
        else:
            _validate_one(field, value, path=label)
    return out


def _validate_one(field: dict[str, Any], value: Any, *, path: str) -> None:
    ftype = field["type"]
    if ftype == "component":
        validate_entry_data(field["fields"], value, path=path)
    elif ftype == "enum":
        if value not in field.get("options", []):
            raise ValidationError(f"مقدار {path} باید یکی از {field.get('options')} باشد")
    else:
        _validate_scalar(ftype, value, path=path)


# ── Type CRUD ────────────────────────────────────────────────────────────────


async def create_content_type(
    db: AsyncSession,
    *,
    slug: str,
    name: str,
    fields: list[dict[str, Any]],
    kind: ContentTypeKind = ContentTypeKind.COLLECTION,
    description: str | None = None,
) -> ContentType:
    if not _TYPE_SLUG_RE.match(slug):
        raise ValidationError(f"نامک تایپ «{slug}» معتبر نیست")
    if slug in RESERVED_TYPE_SLUGS:
        raise ValidationError(f"نامک «{slug}» برای مسیرهای فروشگاه رزرو شده است")
    validate_field_definitions(fields)
    # Relation targets must exist.
    await _assert_relation_targets_exist(db, fields)

    existing = (
        await db.execute(select(ContentType).where(ContentType.slug == slug))
    ).scalar_one_or_none()
    if existing:
        raise ValidationError(f"تایپ محتوای «{slug}» از قبل وجود دارد")

    ct = ContentType(slug=slug, name=name.strip(), fields=fields, kind=kind, description=description)
    db.add(ct)
    await db.flush()
    logger.info("content_type_created", slug=slug, fields=len(fields))
    return ct


async def _assert_relation_targets_exist(db: AsyncSession, fields: list[dict[str, Any]]) -> None:
    for field in fields:
        if field["type"] == "relation":
            target = field.get("target")
            hit = (
                await db.execute(select(func.count(ContentType.id)).where(ContentType.slug == target))
            ).scalar_one()
            if not hit:
                raise ValidationError(f"مقصد relation «{target}» تعریف نشده است")
        if field["type"] == "component":
            await _assert_relation_targets_exist(db, field["fields"])


async def list_content_types(db: AsyncSession) -> list[ContentType]:
    stmt = select(ContentType).where(ContentType.is_active.is_(True)).order_by(ContentType.name)
    return list((await db.execute(stmt)).scalars().all())


async def get_content_type(db: AsyncSession, slug: str) -> ContentType:
    ct = (
        await db.execute(select(ContentType).where(ContentType.slug == slug))
    ).scalar_one_or_none()
    # is_active may still be None on a row created in this transaction (server
    # default applies at INSERT time) — treat None as active.
    if not ct or ct.is_active is False:
        raise NotFoundError("ContentType", f"Content type '{slug}' not found")
    return ct


# ── Entry CRUD ────────────────────────────────────────────────────────────────


async def create_entry(
    db: AsyncSession,
    type_slug: str,
    data: dict[str, Any],
    *,
    status: PageStatus = PageStatus.DRAFT,
    locale: str = "fa",
) -> ContentEntry:
    ct = await get_content_type(db, type_slug)
    if ct.kind == ContentTypeKind.SINGLE:
        existing = (
            await db.execute(
                select(func.count(ContentEntry.id)).where(ContentEntry.content_type_id == ct.id)
            )
        ).scalar_one()
        if existing:
            raise ValidationError("تایپ تکی فقط یک ورودی می‌گیرد — از به‌روزرسانی استفاده کنید")

    clean = validate_entry_data(ct.fields, data)
    entry = ContentEntry(
        content_type_id=ct.id, data=clean, status=status, locale=locale
    )
    db.add(entry)
    await db.flush()
    logger.info("content_entry_created", type=type_slug, entry_id=str(entry.id))
    return entry


async def list_entries(
    db: AsyncSession,
    type_slug: str,
    *,
    status: PageStatus | None = None,
    locale: str | None = None,
) -> list[ContentEntry]:
    ct = await get_content_type(db, type_slug)
    stmt = (
        select(ContentEntry)
        .where(ContentEntry.content_type_id == ct.id)
        .order_by(ContentEntry.position, ContentEntry.created_at.desc())
    )
    if status is not None:
        stmt = stmt.where(ContentEntry.status == status)
    stmt = stmt.where(ContentEntry.deleted_at.is_(None))
    if locale:
        stmt = stmt.where(ContentEntry.locale == locale)
    return list((await db.execute(stmt)).scalars().all())


async def update_entry(
    db: AsyncSession, entry_id: uuid.UUID, data: dict[str, Any], *, status: PageStatus | None = None
) -> ContentEntry:
    entry = await db.get(ContentEntry, entry_id)
    if not entry:
        raise NotFoundError("ContentEntry", f"Entry {entry_id} not found")
    ct = (
        await db.execute(select(ContentType).where(ContentType.id == entry.content_type_id))
    ).scalar_one()

    merged = {**entry.data, **data}
    entry.data = validate_entry_data(ct.fields, merged)
    if status is not None:
        entry.status = status
    await db.flush()
    logger.info("content_entry_updated", entry_id=str(entry_id))
    return entry


async def delete_entry(db: AsyncSession, entry_id: uuid.UUID) -> None:
    entry = await db.get(ContentEntry, entry_id)
    if not entry:
        raise NotFoundError("ContentEntry", f"Entry {entry_id} not found")
    await db.delete(entry)
    await db.flush()
    logger.info("content_entry_deleted", entry_id=str(entry_id))
