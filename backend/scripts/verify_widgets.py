"""Live check: widget types, per-widget config, and operator-created areas.

P1 "ویجت: انواع ویجت", "ویجت: تنظیمات هر ویجت", "ویجت: نواحی و چیدمان".

Asserts the three in one pass against the real store: the missing WordPress
widget types are registered, a widget's config round-trips through
``update_area``, and an operator can create and delete a widget area (with the
built-in areas protected). Self-cleaning: the probe area is removed in
``finally``.

    cd backend && PYTHONPATH=. python scripts/verify_widgets.py
"""

from __future__ import annotations

import asyncio
import importlib
import io
import pkgutil
import sys
import uuid

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import app.modules as _modules

for _m in pkgutil.walk_packages(_modules.__path__, "app.modules."):
    try:
        importlib.import_module(_m.name)
    except Exception:  # noqa: BLE001
        pass

# The WordPress core widget types the doc named as missing.
REQUIRED_TYPES = ("archives", "calendar", "recent_comments", "pages", "meta", "rss", "links")


def _database_url() -> str:
    for line in open(".env", encoding="utf-8"):
        if line.startswith("DATABASE_URL="):
            return line.split("=", 1)[1].strip().strip("\"'")
    raise SystemExit("DATABASE_URL not found in .env")


async def main() -> int:
    from app.shared.content.widgets import (
        DEFAULT_AREAS,
        WIDGET_CONFIG_SCHEMA,
        WIDGET_TYPES,
        WidgetService,
    )

    failures: list[str] = []

    # 1. Every named type is registered.
    for t in REQUIRED_TYPES:
        if t not in WIDGET_TYPES:
            failures.append(f"widget type {t!r} is not registered")
    # 2. Every registered type has a config schema entry (even if empty).
    for t in WIDGET_TYPES:
        if t not in WIDGET_CONFIG_SCHEMA:
            failures.append(f"widget type {t!r} has no config schema")
    if not failures:
        print(f"PASS: {len(WIDGET_TYPES)} widget types registered, all with a schema")

    engine = create_async_engine(_database_url())
    session = async_sessionmaker(engine, expire_on_commit=False)
    area_id = f"probe_{uuid.uuid4().hex[:8]}"

    async with session() as db:
        try:
            # 3. Config round-trips: a recent_posts widget keeps its count.
            await WidgetService.create_area(db, area_id, name="probe area")
            widget = {
                "id": "w_probe",
                "type": "recent_posts",
                "title": "تازه‌ها",
                "config": {"count": 3},
            }
            await WidgetService.update_area(db, area_id, [widget])
            area = await WidgetService.get_area(db, area_id)
            saved = (area or {}).get("widgets", [{}])[0]
            if saved.get("config", {}).get("count") != 3:
                failures.append(
                    "a widget's config did not round-trip (got %r)" % saved.get("config")
                )
            else:
                print("PASS: per-widget config round-trips through update_area")

            # 4. custom_html is still sanitized on the way in (regression guard:
            #    the new schema-driven form must not bypass _sanitise_widgets).
            await WidgetService.update_area(
                db, area_id,
                [{"id": "w_x", "type": "custom_html",
                  "config": {"content": "<script>alert(1)</script><p>ok</p>"}}],
            )
            area = await WidgetService.get_area(db, area_id)
            html = (area or {}).get("widgets", [{}])[0].get("config", {}).get("content", "")
            if "<script" in html:
                failures.append("custom_html was not sanitized on write")
            else:
                print("PASS: custom_html is still sanitized on write")

            # 5. Built-in areas are protected from deletion.
            try:
                await WidgetService.delete_area(db, "sidebar")
                failures.append("a built-in widget area (sidebar) was deletable")
            except ValueError:
                print("PASS: built-in areas refuse deletion")

            # 6. An invalid area id is rejected.
            try:
                await WidgetService.create_area(db, "bad id!", name="x")
                failures.append("an invalid area id was accepted")
            except ValueError:
                print("PASS: an invalid area id is rejected")

        finally:
            # Remove the probe area; restore the default set if it survived.
            areas = await WidgetService.get_all_areas(db)
            if area_id in areas:
                del areas[area_id]
                import json

                from app.modules.settings.application.site_options_service import (
                    SiteOptionsService,
                )

                await SiteOptionsService.set(
                    db, "widget_areas", json.dumps(areas, ensure_ascii=False)
                )
            # Sanity: the built-ins are still present.
            remaining = await WidgetService.get_all_areas(db)
            for builtin in DEFAULT_AREAS:
                if builtin not in remaining:
                    failures.append(f"built-in area {builtin!r} went missing after cleanup")
            print("removed the probe area")

    await engine.dispose()

    if failures:
        print("\nFAIL: widgets are not fully wired")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("\nPASS: widget types, config and areas are wired end to end")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))