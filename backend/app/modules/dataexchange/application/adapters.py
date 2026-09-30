"""Entity adapter registry for the generic import/export framework.

An adapter describes, for one importable/exportable entity:

- ``columns``: ordered list of :class:`ColumnSpec` (key, Persian label,
  required, type, validator) used to render the mapping UI and to validate
  each row.
- ``upsert_row``: map one validated row dict to an upsert against the DB
  session; must be idempotent (match by a stable business key such as SKU).
- ``export_rows``: an async iterator of row dicts for export, honouring
  filters.

Adding a new entity means writing one adapter module and registering it in
``_REGISTRY`` below — no framework changes needed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Value type coercers
# ---------------------------------------------------------------------------

def normalise_digits(text: str) -> str:
    """Convert Persian/Arabic numerals to ASCII digits."""
    if not text:
        return ""
    persian = "۰۱۲۳۴۵۶۷۸۹"
    arabic = "٠١٢٣٤٥٦٧٨٩"
    trans = str.maketrans(
        {
            **{p: str(i) for i, p in enumerate(persian)},
            **{a: str(i) for i, a in enumerate(arabic)},
        }
    )
    return text.translate(trans)


_SLUG_RE = re.compile(r"^[a-z0-9؀-ۿ]+(?:-[a-z0-9؀-ۿ]+)*$")


def is_valid_slug(value: str) -> bool:
    return bool(_SLUG_RE.match(value.strip().lower()))


def coerce_int(raw: Any) -> int:
    """Coerce a cell to a non-negative integer (Persian digits accepted)."""
    text = normalise_digits(str(raw)).strip().replace(",", "").replace("٬", "")
    if text in ("", "-"):
        raise ValueError("مقدار عددی خالی است")
    if not re.fullmatch(r"-?\d+", text):
        raise ValueError(f"مقدار «{raw}» عدد صحیح نیست")
    return int(text)


_TRUE_TOKENS = {"1", "true", "yes", "فعال", "بله", "✓"}
_FALSE_TOKENS = {"0", "false", "no", "غیرفعال", "خیر", ""}


def coerce_bool(raw: Any) -> bool:
    text = str(raw).strip().lower()
    if text in _TRUE_TOKENS:
        return True
    if text in _FALSE_TOKENS:
        return False
    raise ValueError(f"مقدار «{raw}» برای فیلد فعال/غیرفعال معتبر نیست")


# ---------------------------------------------------------------------------
# Column / adapter contracts
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ColumnSpec:
    """One importable/exportable column of an entity."""

    key: str  # canonical key used in mapping + row dicts
    label: str  # Persian label shown in the mapping UI
    required: bool = False
    type: str = "string"  # string | integer | boolean
    aliases: tuple[str, ...] = ()  # extra header names used for auto-guess
    # Optional extra validator: receives the coerced value, returns an error
    # message (Persian) or None when valid.
    extra_validator: Any = None


@dataclass
class RowError:
    row_number: int
    column: str  # column key or "*" for row-level
    message: str
    raw_value: Any = None


@dataclass
class AdapterResult:
    """Outcome of validating the full row set of one import job."""

    rows: list[dict[str, Any]] = field(default_factory=list)  # validated rows
    errors: list[RowError] = field(default_factory=list)

    @property
    def valid_count(self) -> int:
        return len(self.rows)

    @property
    def invalid_count(self) -> int:
        return len({e.row_number for e in self.errors})


@dataclass(frozen=True)
class EntityAdapter:
    entity_type: str
    label: str  # Persian entity label for UI
    columns: tuple[ColumnSpec, ...]
    # upsert_row(db, row) -> "created" | "updated"
    upsert_row: Any  # Callable[[AsyncSession, dict[str, Any]], Awaitable[str]]
    # export_rows(db, filters) -> AsyncIterator[dict[str, Any]]
    export_rows: Any  # Callable[[AsyncSession, dict[str, Any]], AsyncIterator[dict[str, Any]]]
    # Optional adapter-specific row coercion/validation; when omitted the
    # generic ColumnSpec-driven implementations below are used.
    coerce_row: Any = None  # Callable[[dict[str, Any]], dict[str, Any]]
    validate_row: Any = None  # Callable[[dict[str, Any]], list[tuple[str, str]]]
    # The stable business key upsert matches on (in-file duplicate detection).
    # Defaults to the first required column (the product adapter's SKU).
    business_key: str | None = None
    # When True the pipeline passes the importing user (job.created_by) to
    # upsert_row as a ``created_by`` keyword — adapters whose model demands an
    # author (blog_posts.author_id is NOT NULL) use it instead of guessing.
    upsert_accepts_created_by: bool = False

    @property
    def column_keys(self) -> list[str]:
        return [c.key for c in self.columns]

    @property
    def required_keys(self) -> list[str]:
        return [c.key for c in self.columns if c.required]

    def header_alias_map(self) -> dict[str, str]:
        """Map every known header alias (lower-cased) to its column key."""
        out: dict[str, str] = {}
        for col in self.columns:
            out[col.key.lower()] = col.key
            out[col.label.strip().lower()] = col.key
            for alias in col.aliases:
                out[alias.strip().lower()] = col.key
        return out


# ---------------------------------------------------------------------------
# Generic row coercion / validation (ColumnSpec-driven)
# ---------------------------------------------------------------------------


def coerce_row_generic(
    raw: dict[str, Any], columns: tuple[ColumnSpec, ...]
) -> dict[str, Any]:
    """Type-coerce one mapped row to its column types.

    ``raw`` is keyed by column *key* (mapping already applied). Missing
    optional values are dropped; missing/blank required values are left for
    the validator to report so a single pass surfaces every problem.
    Raises nothing — callers use :func:`validate_row_generic` for messages.
    """
    out: dict[str, Any] = {}
    for col in columns:
        value = raw.get(col.key)
        if value is None or (isinstance(value, str) and not value.strip()):
            continue
        if col.type == "integer":
            try:
                out[col.key] = coerce_int(value)
            except ValueError:
                out[col.key] = value  # keep raw; validator reports it
        elif col.type == "boolean":
            try:
                out[col.key] = coerce_bool(value)
            except ValueError:
                out[col.key] = value
        else:
            out[col.key] = str(value).strip()
    return out


def validate_row_generic(
    raw: dict[str, Any], columns: tuple[ColumnSpec, ...]
) -> list[tuple[str, str]]:
    """Validate one coerced-attempt row; returns ``(column_key, message)`` pairs."""
    problems: list[tuple[str, str]] = []
    for col in columns:
        value = raw.get(col.key)
        missing = value is None or (isinstance(value, str) and not value.strip())
        if missing:
            if col.required:
                problems.append((col.key, f"ستون «{col.label}» الزامی است"))
            continue
        if col.type == "integer" and not isinstance(value, int):
            problems.append((col.key, f"ستون «{col.label}» باید عدد صحیح باشد"))
            continue
        if col.type == "boolean" and not isinstance(value, bool):
            problems.append((col.key, f"ستون «{col.label}» باید فعال/غیرفعال باشد"))
            continue
        if col.extra_validator is not None and isinstance(value, (int, str, bool)):
            message = col.extra_validator(value)
            if message:
                problems.append((col.key, message))
    return problems


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_REGISTRY: dict[str, EntityAdapter] = {}


def register_adapter(adapter: EntityAdapter) -> EntityAdapter:
    _REGISTRY[adapter.entity_type] = adapter
    return adapter


def get_adapter(entity_type: str) -> EntityAdapter:
    try:
        return _REGISTRY[entity_type]
    except KeyError:
        from app.core.exceptions.handlers import ValidationError

        raise ValidationError(f"نوع موجودیت «{entity_type}» پشتیبانی نمی‌شود") from None


def list_entity_types() -> list[dict[str, Any]]:
    """Summary of registered adapters for the mapping UI / export form."""
    return [
        {
            "entity_type": a.entity_type,
            "label": a.label,
            "columns": [
                {
                    "key": c.key,
                    "label": c.label,
                    "required": c.required,
                    "type": c.type,
                    "aliases": list(c.aliases),
                }
                for c in a.columns
            ],
        }
        for a in _REGISTRY.values()
    ]


# Importing the adapter modules registers them (side-effect of decorator).
from app.modules.dataexchange.application import (  # noqa: E402
    blog_post_adapter,  # noqa: F401
    cms_page_adapter,  # noqa: F401
    product_adapter,  # noqa: F401
)
