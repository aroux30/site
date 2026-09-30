"""Import/export pipeline: validate (dry-run), execute, error reports, export.

Framework-level flow shared by every entity adapter:

1. ``parse_job_file``      — headers + rows from the stored upload
2. ``auto_guess_mapping``  — source header -> column key, by label/alias match
3. ``validate_rows``       — full pass collecting *all* row errors (dry run)
4. ``execute_import``      — per-row savepoint upsert, per-row error capture
5. ``build_error_csv``     — downloadable row-level error report
6. ``run_export``          — stream adapter rows to a CSV file

Validation collects every error before reporting (never fails fast on row 1)
so operators fix one CSV round-trip, not twenty.
"""

from __future__ import annotations

import csv
import io
import uuid
from functools import partial
from pathlib import Path
from typing import Any

import structlog

from app.core.config.settings import get_settings
from app.core.exceptions.handlers import ValidationError
from app.modules.dataexchange.application.adapters import (
    EntityAdapter,
    coerce_row_generic,
    validate_row_generic,
)
from app.modules.dataexchange.application.file_parser import parse_upload

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Storage helpers
# ---------------------------------------------------------------------------


def _base_dir() -> Path:
    settings = get_settings()
    root = Path(settings.UPLOAD_DIR) / "dataexchange"
    root.mkdir(parents=True, exist_ok=True)
    return root


def store_upload(content: bytes, filename: str) -> str:
    """Persist an uploaded import file; returns the server-side path."""
    import re as _re

    safe = _re.sub(r"[^A-Za-z0-9._-]", "_", filename or "upload.csv")[-120:] or "upload.csv"
    target = _base_dir() / f"{uuid.uuid4().hex}-{safe}"
    target.write_bytes(content)
    return str(target)


def read_uploaded(path: str) -> bytes:
    file_path = Path(path)
    if not file_path.is_file():
        raise ValidationError("فایل بارگذاری‌شده روی سرور یافت نشد")
    return file_path.read_bytes()


# ---------------------------------------------------------------------------
# Parse + mapping
# ---------------------------------------------------------------------------


def parse_job_file(job: Any) -> tuple[list[str], list[tuple[int, dict[str, Any]]]]:
    """Parse the stored upload of an import job into headers + data rows."""
    content = read_uploaded(job.stored_file_path)
    return parse_upload(content, job.original_filename)


def auto_guess_mapping(headers: list[str], adapter: EntityAdapter) -> dict[str, str]:
    """Map each source header to a column key via labels/aliases (exact, then loose)."""
    alias_map = adapter.header_alias_map()
    mapping: dict[str, str] = {}
    used_targets: set[str] = set()
    # Pass 1: exact (case/space-insensitive) matches
    for header in headers:
        key = alias_map.get(header.strip().lower())
        if key and key not in used_targets:
            mapping[header] = key
            used_targets.add(key)
    # Pass 2: substring containment for Persian headers with decoration
    for header in headers:
        if header in mapping:
            continue
        normalized = header.strip().lower()
        for alias, key in alias_map.items():
            if key in used_targets or len(alias) < 2:
                continue
            if alias in normalized or normalized in alias:
                mapping[header] = key
                used_targets.add(key)
                break
    return mapping


def apply_mapping(
    rows: list[tuple[int, dict[str, Any]]],
    mapping: dict[str, str],
) -> list[tuple[int, dict[str, Any]]]:
    """Re-key rows from source headers to adapter column keys."""
    out: list[tuple[int, dict[str, Any]]] = []
    for row_no, row in rows:
        out.append((row_no, {mapping.get(k, k): v for k, v in row.items()}))
    return out


# ---------------------------------------------------------------------------
# Validate (dry run)
# ---------------------------------------------------------------------------


def validate_rows(
    rows: list[tuple[int, dict[str, Any]]],
    adapter: EntityAdapter,
    *,
    coerce_fn: Any = None,
    validate_fn: Any = None,
) -> tuple[list[tuple[int, dict[str, Any]]], list[dict[str, Any]], dict[str, int]]:
    """Dry-run every row through coercion + column validators.

    Returns ``(valid_rows, error_entries, stats)``. All errors are collected
    before returning — a 5,000-row file with 200 bad rows reports 200, not 1.
    Duplicate business keys *within the file* (the adapter's business key,
    e.g. SKU or slug) are flagged here too.

    Row functions resolve per adapter: an adapter may carry its own
    ``coerce_row``/``validate_row``, otherwise the generic ColumnSpec-driven
    implementations are used. ``coerce_fn``/``validate_fn`` remain injectable
    so unit tests can exercise custom functions without a registry.
    """
    if coerce_fn is None or validate_fn is None:
        if adapter.coerce_row is not None and adapter.validate_row is not None:
            coerce_fn, validate_fn = adapter.coerce_row, adapter.validate_row
        else:
            coerce_fn = partial(coerce_row_generic, columns=adapter.columns)
            validate_fn = partial(validate_row_generic, columns=adapter.columns)

    valid: list[tuple[int, dict[str, Any]]] = []
    errors: list[dict[str, Any]] = []

    # In-file duplicate detection on the business key column.
    key_column = adapter.business_key or (
        adapter.required_keys[0] if adapter.required_keys else None
    )
    seen_keys: dict[str, int] = {}

    for row_no, raw in rows:
        coerced = coerce_fn(raw)
        problems = validate_fn(coerced)
        if key_column and coerced.get(key_column):
            key = str(coerced[key_column]).strip().lower()
            if key in seen_keys:
                problems.append(
                    (
                        key_column,
                        f"کلید تکراری در فایل (ردیف {seen_keys[key]} نیز همین کلید را دارد)",
                    )
                )
            else:
                seen_keys[key] = row_no
        if problems:
            for column, message in problems:
                errors.append(
                    {
                        "row_number": row_no,
                        "column": column,
                        "message": message,
                        "raw_value": raw.get(column),
                    }
                )
        else:
            valid.append((row_no, coerced))

    stats = {
        "total": len(rows),
        "valid": len(valid),
        "invalid": len({e["row_number"] for e in errors}),
        "imported": 0,
        "skipped": 0,
    }
    return valid, errors, stats


# ---------------------------------------------------------------------------
# Execute
# ---------------------------------------------------------------------------


async def execute_import(
    db: Any,
    job: Any,
    adapter: EntityAdapter,
    valid_rows: list[tuple[int, dict[str, Any]]],
) -> tuple[dict[str, int], list[dict[str, Any]]]:
    """Upsert validated rows with per-row savepoint error capture.

    Adapters that declare ``upsert_accepts_created_by`` receive the importing
    user (``job.created_by``) as a keyword, so e.g. imported blog posts get a
    real author instead of a placeholder.
    """
    imported = 0
    errors: list[dict[str, Any]] = []
    upsert_kwargs: dict[str, Any] = {}
    if getattr(adapter, "upsert_accepts_created_by", False):
        upsert_kwargs["created_by"] = getattr(job, "created_by", None)
    for row_no, row in valid_rows:
        try:
            async with db.begin_nested():
                await adapter.upsert_row(db, row, **upsert_kwargs)
            imported += 1
        except Exception as exc:
            errors.append(
                {
                    "row_number": row_no,
                    "column": "*",
                    "message": str(exc),
                    "raw_value": None,
                }
            )
            await logger.awarning(
                "dataexchange_row_failed",
                job_id=str(job.id),
                row=row_no,
                error=str(exc),
            )
    stats = dict(job.stats or {})
    stats.update(
        {
            "imported": imported,
            "skipped": len(errors),
            "invalid": (stats.get("invalid") or 0),
        }
    )
    return stats, errors


# ---------------------------------------------------------------------------
# Error report CSV
# ---------------------------------------------------------------------------


def build_error_csv(errors: list[dict[str, Any]]) -> str:
    """Render row-level errors as CSV text (Persian headers, UTF-8 BOM for Excel)."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["ردیف", "ستون", "خطا", "مقدار خام"])
    for e in errors:
        writer.writerow(
            [e["row_number"], e["column"], e["message"], "" if e.get("raw_value") is None else e["raw_value"]]
        )
    return "﻿" + buffer.getvalue()


def write_error_report(job_id: uuid.UUID, errors: list[dict[str, Any]]) -> str | None:
    """Persist the error CSV next to the upload; returns the path (or None)."""
    if not errors:
        return None
    target = _base_dir() / f"errors-{job_id.hex}.csv"
    target.write_text(build_error_csv(errors), encoding="utf-8-sig")
    return str(target)


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


def _export_header_labels(adapter: EntityAdapter, extra_keys: list[str]) -> list[str]:
    labels = {c.key: c.label for c in adapter.columns}
    # product adapter exports two extra columns (id, created_at)
    labels.setdefault("id", "شناسه")
    labels.setdefault("created_at", "تاریخ ایجاد")
    order = ["id", *adapter.column_keys, "created_at"]
    return [labels.get(k, k) for k in order if k in labels or k in extra_keys]


async def run_export(db: Any, adapter: EntityAdapter, filters: dict[str, Any]) -> tuple[str, int]:
    """Stream adapter rows to a CSV file; returns ``(path, row_count)``."""
    target = _base_dir() / f"export-{adapter.entity_type}-{uuid.uuid4().hex[:12]}.csv"
    count = 0
    with target.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = None
        async for row in adapter.export_rows(db, filters):
            if writer is None:
                writer = csv.DictWriter(fh, fieldnames=list(row.keys()))
                writer.writeheader()
            writer.writerow(row)
            count += 1
        if writer is None:
            # no rows — still emit a header-only file
            keys = [c.key for c in adapter.columns]
            writer = csv.DictWriter(fh, fieldnames=keys)
            writer.writeheader()
    return str(target), count
