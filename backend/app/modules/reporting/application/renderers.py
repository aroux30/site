"""Report renderers.

PDF export is **deferred**: the project ships no PDF library (no
reportlab/weasyprint dependency is installed, and adding one is out of
scope). The :class:`ReportRenderer` protocol is the seam a future PDF
renderer plugs into; today :class:`HtmlReportRenderer` produces an
archivable RTL HTML document that is stored next to the CSV artifact and
can be printed to PDF from the browser (the admin UI exposes it via the
run download endpoint).
"""

from __future__ import annotations

import html
from typing import Protocol

from app.modules.reporting.application.report_service import ReportResult


class ReportRenderer(Protocol):
    """Render a report to a persistent artifact."""

    content_type: str
    extension: str

    def render(self, result: ReportResult, *, title: str) -> bytes:
        """Render the report; returns artifact bytes."""
        ...


def _format_cell(value: object, kind: str) -> str:
    if value is None:
        return "—"
    if kind in ("int", "money") and isinstance(value, int):
        return f"{value:,}"
    return html.escape(str(value))


class HtmlReportRenderer:
    """Standalone RTL HTML rendering (print-friendly, no external assets)."""

    content_type = "text/html; charset=utf-8"
    extension = "html"

    def render(self, result: ReportResult, *, title: str) -> bytes:
        header_cells = "".join(
            f"<th>{html.escape(col.label)}</th>" for col in result.columns
        )
        body_rows = []
        for row in result.rows:
            cells = "".join(
                f'<td class="{col.kind}">{_format_cell(row.get(col.key), col.kind)}</td>'
                for col in result.columns
            )
            body_rows.append(f"<tr>{cells}</tr>")
        if not body_rows:
            body_rows.append(
                f'<tr><td colspan="{len(result.columns)}" class="empty">'
                "داده‌ای در این بازه یافت نشد</td></tr>"
            )

        totals_row = ""
        if result.totals:
            cells = "".join(
                f'<td class="{col.kind}">{_format_cell(result.totals.get(col.key), col.kind)}</td>'
                for col in result.columns
            )
            totals_row = f'<tr class="totals">{cells}</tr>'

        notes = "".join(
            f"<li>{html.escape(note)}</li>" for note in result.notes
        )
        notes_block = f"<ul class='notes'>{notes}</ul>" if notes else ""

        document = f"""<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
body {{ font-family: Tahoma, Arial, sans-serif; margin: 24px; color: #111827; }}
h1 {{ font-size: 18px; margin: 0 0 4px; }}
.meta {{ color: #6b7280; font-size: 12px; margin-bottom: 16px; }}
table {{ border-collapse: collapse; width: 100%; font-size: 12px; }}
th, td {{ border: 1px solid #d1d5db; padding: 6px 8px; text-align: right; }}
th {{ background: #f3f4f6; }}
td.int, td.money {{ font-variant-numeric: tabular-nums; direction: ltr; text-align: left; }}
tr.totals td {{ font-weight: bold; background: #f9fafb; }}
td.empty {{ text-align: center; color: #6b7280; }}
.notes {{ color: #6b7280; font-size: 11px; margin-top: 12px; }}
</style>
</head>
<body>
<h1>{html.escape(title)}</h1>
<p class="meta">از {result.date_from.isoformat()} تا {result.date_to.isoformat()}
— گروه‌بندی: {html.escape(result.group_by)} — {result.row_count:,} ردیف</p>
<table>
<thead><tr>{header_cells}</tr></thead>
<tbody>{"".join(body_rows)}</tbody>
{"<tfoot>" + totals_row + "</tfoot>" if totals_row else ""}
</table>
{notes_block}
</body>
</html>"""
        return document.encode("utf-8")
