"""Safe CSV builders for report exports.

Conventions follow the project's dataexchange/tax exporters:

- **UTF-8 with BOM** (``utf-8-sig``) so Persian headers and values open
  correctly in Microsoft Excel.
- **Formula-injection hardening**: any *text* cell whose value starts with
  one of the spreadsheet execution prefixes (``= + - @`` or a tab/newline)
  is prefixed with a single quote so Excel/LibreOffice/Google Sheets render
  it as inert text instead of evaluating it. Numeric cells (``int``) are
  never quoted — money stays integer Rials end to end.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable
from typing import Any

# Characters that a spreadsheet treats as "evaluate this cell" when a text
# value begins with them. Leading tab/CR is included per OWASP guidance —
# they strip to a formula too.
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def sanitize_csv_cell(value: Any) -> Any:
    """Escape one cell for formula-injection safety.

    ``int``/``float``/``None`` pass through untouched (numbers stay numeric
    for spreadsheet math); strings beginning with a dangerous prefix get a
    leading apostrophe.
    """
    if value is None or isinstance(value, (int, float)):
        return value
    text = str(value)
    if text.startswith(_FORMULA_PREFIXES):
        return "'" + text
    return text


def sanitize_csv_rows(rows: Iterable[Iterable[Any]]) -> list[list[Any]]:
    """Apply :func:`sanitize_csv_cell` to every cell of a 2-D row sequence."""
    return [[sanitize_csv_cell(cell) for cell in row] for row in rows]


def build_csv_bytes(header: list[Any], rows: Iterable[Iterable[Any]]) -> bytes:
    """Render header + rows as UTF-8-BOM CSV bytes (Excel-safe)."""
    buffer = io.StringIO()
    # Explicit BOM marker before any data so Excel picks UTF-8 even if the
    # consumer ignores the content-type charset (matches tax_routes.py).
    buffer.write("﻿")
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow([sanitize_csv_cell(cell) for cell in header])
    for row in sanitize_csv_rows(rows):
        writer.writerow(row)
    return buffer.getvalue().encode("utf-8")
