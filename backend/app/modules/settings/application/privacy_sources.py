"""Per-source exporters and erasers, so privacy work is pluggable.

``export_user_data`` and ``erase_user_data`` were two long functions that
knew about every table in the system. That has three costs: a source added
later is silently missing from a legal obligation, there is no way to report
*which* sources were covered, and a partial failure is indistinguishable from a
complete one.

WordPress solves the first two with ``wp_privacy_personal_data_exporters`` and
``wp_privacy_personal_data_erasers`` — filters that register one callback per
source, each answering with what it did. This module is that idea for this
codebase: a registry of sources, each knowing how to export and erase itself,
plus a report that says per source what happened.

Two design points worth stating, because they are what make a per-source report
honest rather than decorative:

* **A source that raises is recorded, not swallowed.** An export that silently
  omits an orders table because of a schema error is worse than one that fails
  loudly, because the subject is told their data was exported.
* **Erasure distinguishes removed from retained.** Financial and audit records
  are legally required to be kept, so they are anonymised rather than deleted —
  and the report has to say so, because "we erased your data" is false.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class SourceResult:
    """What one source did, for one subject.

    ``items_removed``/``items_retained`` are counted rather than merely flagged so
    a reviewer can see that a source did something. A source that reported
    success with zero of both is indistinguishable from one that silently did
    nothing.
    """

    exporter: str
    exported: int = 0
    items_removed: int = 0
    items_retained: int = 0
    error: str | None = None
    #: Set when a source deliberately keeps rows for a legal retention duty.
    #: Rendered to the subject, so "erased" is never a claim the data is gone
    #: when it is merely de-identified.
    retained_reason: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": self.exporter,
            "exported": self.exported,
            "items_removed": self.items_removed,
            "items_retained": self.items_retained,
            "retained_reason": self.retained_reason,
            "error": self.error,
        }


#: An exporter returns ``(rows, payload)`` — the count for the report, and the
#: rows themselves for the archive. Returning only a count would leave the
#: registry able to say "45 sources covered" while the file handed to the
#: subject contained none of them, which is the failure this module exists to
#: prevent. A source with nothing to report returns an empty list rather than
#: being skipped, so its presence in the report is still visible.
Exporter = Callable[["AsyncSession", uuid.UUID], Awaitable[tuple[int, Any]]]
Eraser = Callable[
    ["AsyncSession", uuid.UUID],
    Awaitable[tuple[int, int, str | None]],
]


@dataclass
class Registry:
    """The registered sources, in the order they should be reported."""

    exporters: dict[str, Exporter] = field(default_factory=dict)
    erasers: dict[str, Eraser] = field(default_factory=dict)
    #: Human-readable label per source, for the subject-facing report.
    labels: dict[str, str] = field(default_factory=dict)

    def register(
        self,
        name: str,
        *,
        exporter: Exporter | None = None,
        eraser: Eraser | None = None,
        label: str = "",
    ) -> None:
        if exporter is not None:
            self.exporters[name] = exporter
        if eraser is not None:
            self.erasers[name] = eraser
        if label:
            self.labels[name] = label

    def label(self, name: str) -> str:
        return self.labels.get(name, name)

    def names(self) -> list[str]:
        return sorted(set(self.exporters) | set(self.erasers))


registry = Registry()


async def collect_export(db: "AsyncSession", user_id: uuid.UUID) -> dict[str, Any]:
    """Build the full data-subject archive, plus a per-source report.

    Returns both the payload and the report together, because separating them is
    how a caller ends up serving the file without ever reading the report — and
    the report is the part that says which sources failed. A caller that ignores
    ``report`` still cannot be misled about completeness, since
    ``report["complete"]`` is the only thing that should gate "your data is
    ready".
    """
    from app.modules.settings.application.privacy_core_sources import ensure_registered

    ensure_registered()

    results: list[SourceResult] = []
    payload: dict[str, Any] = {}

    for name, fn in registry.exporters.items():
        # Savepoint per source, for the same reason as run_erasers: one bad
        # source must not abort the transaction and take the rest of the
        # archive with it.
        savepoint = await db.begin_nested()
        try:
            rows, data = await fn(db, user_id)
        except Exception as exc:  # noqa: BLE001 - one bad source must not hide the rest
            await savepoint.rollback()
            logger.exception("privacy_export_source_failed", source=name, user_id=str(user_id))
            results.append(SourceResult(exporter=name, error=str(exc)))
            continue
        else:
            await savepoint.commit()
        results.append(SourceResult(exporter=name, exported=rows))
        payload[name] = data

    report = summarise(results)
    return {"data": payload, "report": report}


async def run_exporters(
    db: "AsyncSession",
    user_id: uuid.UUID,
    registry: "Registry | None" = None,
) -> list[SourceResult]:
    """Run every registered exporter for its count and failure status.

    Kept as a separate entry point for callers that only need the report. Prefer
    :func:`collect_export` when building the file itself — running this and then
    re-querying the sources separately would double every read.
    """
    active = registry if registry is not None else globals()["registry"]
    if registry is None:
        from app.modules.settings.application.privacy_core_sources import (
            ensure_registered,
        )

        ensure_registered()
        active = globals()["registry"]
    results: list[SourceResult] = []
    for name, fn in active.exporters.items():
        savepoint = await db.begin_nested()
        try:
            rows, _data = await fn(db, user_id)
        except Exception as exc:  # noqa: BLE001 - one bad source must not hide the rest
            await savepoint.rollback()
            logger.exception("privacy_export_source_failed", source=name, user_id=str(user_id))
            results.append(SourceResult(exporter=name, error=str(exc)))
            continue
        else:
            await savepoint.commit()
        results.append(SourceResult(exporter=name, exported=rows))
    return results


async def run_erasers(
    db: "AsyncSession",
    user_id: uuid.UUID,
    registry: "Registry | None" = None,
) -> list[SourceResult]:
    """Run every registered eraser, recording per-source outcomes.

    A source that fails is reported as failed. Silently continuing would let a
    partially-completed erasure be recorded as done, which is the one outcome a
    data-subject request must never have.
    """
    if registry is None:
        # Without this the registry can still be empty here -- collect_export
        # registers on entry but these two entry points did not, so a process
        # whose first privacy call is run_erasers would erase nothing and
        # report zero sources rather than thirty.
        from app.modules.settings.application.privacy_core_sources import (
            ensure_registered,
        )

        ensure_registered()

    active = registry if registry is not None else globals()["registry"]
    results: list[SourceResult] = []
    for name, fn in active.erasers.items():
        # Each source runs inside a SAVEPOINT. Without one, a single SQL error
        # aborts the enclosing transaction and every later source fails with
        # "current transaction is aborted" — measured on the live database as 27
        # reported failures where only 3 were real. The healthy sources were not
        # merely misreported: their work was rolled back too, so a partially
        # completed erasure was recorded as a complete one.
        savepoint = await db.begin_nested()
        try:
            removed, retained, reason = await fn(db, user_id)
        except Exception as exc:  # noqa: BLE001
            await savepoint.rollback()
            logger.exception("privacy_erase_source_failed", source=name, user_id=str(user_id))
            results.append(SourceResult(exporter=name, error=str(exc)))
            continue
        else:
            await savepoint.commit()
        results.append(
            SourceResult(
                exporter=name,
                items_removed=removed,
                items_retained=retained,
                retained_reason=reason,
            )
        )
    return results


def summarise(results: list[SourceResult]) -> dict[str, Any]:
    """Roll a per-source report up into the shape the API and UI consume."""
    failed = [r for r in results if not r.ok]
    return {
        "sources": [r.as_dict() for r in results],
        "total_exported": sum(r.exported for r in results),
        "total_removed": sum(r.items_removed for r in results),
        "total_retained": sum(r.items_retained for r in results),
        "complete": not failed,
        "failed_sources": [r.exporter for r in failed],
    }


def build_export_zip(
    archive: dict[str, Any],
    *,
    subject_label: str,
) -> bytes:
    """Package a collected export as a ZIP a person can actually open.

    The raw JSON was the whole archive in one file: a subject who asked for
    their data got a wall of nested objects with no way to tell which table
    was which. This lays it out the way every other data-export tool does —
    a human-readable ``index.html`` that lists what is inside and links each
    source, one JSON file per source, and a ``_report.json`` that records what
    was exported and what failed.

    ``index.html`` is generated here rather than shipped as a template so the
    counts in it match the archive it is zipped beside; a static page would
    say "your data" while the files next to it changed shape.

    Returns the raw ZIP bytes. The caller names the download.
    """
    import html
    import io
    import json
    import zipfile

    data = archive.get("data", {})
    report = archive.get("report", {})

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for source, payload in data.items():
            # A source name is server-controlled (a registry key), so it is a
            # safe path segment; the JSON is written indented so a person
            # opening one file can read it.
            zf.writestr(
                f"data/{source}.json",
                json.dumps(payload, ensure_ascii=False, indent=2, default=str),
            )
        zf.writestr(
            "_report.json",
            json.dumps(report, ensure_ascii=False, indent=2, default=str),
        )

        rows = "".join(
            f'<li><a href="data/{html.escape(str(name))}.json">'
            f"{html.escape(str(name))}</a></li>"
            for name in sorted(data)
        )
        failed = report.get("failed_sources") or []
        failed_html = (
            "<p class='warn'>این منابع کامل استخراج نشدند: "
            + ", ".join(html.escape(str(f)) for f in failed)
            + "</p>"
            if failed
            else "<p class='ok'>همهٔ منابع کامل استخراج شدند.</p>"
        )
        index = f"""<!doctype html>
<html lang="fa" dir="rtl"><head><meta charset="utf-8">
<title>خروجی داده‌های {html.escape(subject_label)}</title>
<style>
 body{{font-family:system-ui,Tahoma,sans-serif;max-width:44rem;margin:2rem auto;padding:0 1rem;line-height:1.9}}
 ul{{columns:2}} a{{color:#0b6}}
 .ok{{color:#0a0}} .warn{{color:#c00;font-weight:bold}}
</style></head><body>
<h1>خروجی داده‌های شخصی</h1>
<p>این بستهٔ داده‌های حساب <strong>{html.escape(subject_label)}</strong> است،
همان‌طور که در قوانین حریم خصوصی توضیح داده شده.</p>
<p>تعداد رکوردهای استخراج‌شده: {html.escape(str(report.get("total_exported", 0)))}</p>
{failed_html}
<h2>فایل‌ها</h2>
<ul>{rows}</ul>
<p>فایل <code>_report.json</code> گزارش کامل هر منبع را دارد.</p>
</body></html>"""
        zf.writestr("index.html", index)

    return buf.getvalue()
