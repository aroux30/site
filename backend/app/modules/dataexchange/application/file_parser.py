"""Tabular file parsing for import jobs (CSV + XLSX).

Returns a header row plus a list of ``(row_number, {header: cell})`` tuples.
Row numbers are 1-based *data* row numbers (header excluded) so the error
report can point the operator at a spreadsheet row.
"""

from __future__ import annotations

import csv
import io
from typing import Any

from app.core.exceptions.handlers import ValidationError

MAX_IMPORT_ROWS = 10_000
MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB

CSV_EXTENSIONS = (".csv", ".txt", ".tsv")
XLSX_EXTENSIONS = (".xlsx", ".xlsm")


def _clean_header(raw: Any) -> str:
    return str(raw).strip() if raw is not None else ""


def _dedupe_headers(headers: list[str]) -> list[str]:
    """Suffix duplicate header names (``price``, ``price_2``) so dict keys stay unique."""
    seen: dict[str, int] = {}
    out: list[str] = []
    for h in headers:
        if h in seen:
            seen[h] += 1
            out.append(f"{h}_{seen[h]}")
        else:
            seen[h] = 1
            out.append(h)
    return out


def parse_csv(content: bytes) -> tuple[list[str], list[tuple[int, dict[str, str]]]]:
    text = content.decode("utf-8-sig", errors="replace")
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.reader(io.StringIO(text), dialect)
    rows = list(reader)
    if not rows:
        raise ValidationError("فایل خالی است")
    headers = _dedupe_headers([_clean_header(h) for h in rows[0]])
    if not any(headers):
        raise ValidationError("ردیف سرستون فایل خالی است")
    data: list[tuple[int, dict[str, str]]] = []
    for idx, raw in enumerate(rows[1:], start=1):
        if not raw or all(not str(c).strip() for c in raw):
            continue  # skip fully blank lines
        row = {
            headers[i]: (str(raw[i]).strip() if i < len(raw) else "")
            for i in range(len(headers))
        }
        data.append((idx, row))
    return headers, data


def parse_xlsx(content: bytes) -> tuple[list[str], list[tuple[int, dict[str, Any]]]]:
    try:
        import openpyxl
    except ImportError as exc:  # pragma: no cover — openpyxl is a declared dep
        raise ValidationError("پشتیبانی از فایل اکسل در این نصب فعال نیست") from exc

    wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True, read_only=True)
    try:
        sheet = wb.active
        if sheet is None:
            raise ValidationError("فایل اکسل هیچ برگه‌ای ندارد")
        iterator = sheet.iter_rows(values_only=True)
        try:
            header_row = next(iterator)
        except StopIteration:
            raise ValidationError("فایل اکسل خالی است") from None
        headers = _dedupe_headers([_clean_header(h) for h in header_row])
        if not any(headers):
            raise ValidationError("ردیف سرستون فایل خالی است")
        data: list[tuple[int, dict[str, Any]]] = []
        for idx, raw in enumerate(iterator, start=1):
            if raw is None or all(v is None or str(v).strip() == "" for v in raw):
                continue
            row = {
                headers[i]: (raw[i] if i < len(raw) else None)
                for i in range(len(headers))
            }
            data.append((idx, row))
        return headers, data
    finally:
        wb.close()


def parse_upload(content: bytes, filename: str) -> tuple[list[str], list[tuple[int, dict[str, Any]]]]:
    """Dispatch on extension; enforces size and row caps."""
    if len(content) > MAX_FILE_BYTES:
        raise ValidationError("حجم فایل بیش از ۱۰ مگابایت است")
    if not content:
        raise ValidationError("فایل خالی است")

    lowered = filename.lower()
    if lowered.endswith(XLSX_EXTENSIONS):
        headers, rows = parse_xlsx(content)
    elif lowered.endswith(CSV_EXTENSIONS):
        headers, rows = parse_csv(content)
    else:
        raise ValidationError("فرمت فایل پشتیبانی نمی‌شود (فقط CSV یا XLSX)")

    if len(rows) > MAX_IMPORT_ROWS:
        raise ValidationError(f"تعداد ردیف‌ها بیش از حد مجاز است (حداکثر {MAX_IMPORT_ROWS})")
    return headers, rows
