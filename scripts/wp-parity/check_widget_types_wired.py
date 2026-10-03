"""Guard: widget types, per-widget config, and operator-created areas stay wired.

P1 "ویجت: انواع ویجت", "ویجت: تنظیمات هر ویجت", "ویجت: نواحی و چیدمان".

The recurring failure class here is a type that is registered but renders
nothing, or a client method with no caller. So this checks the whole chain for
each: registered type → a storefront `case` that renders it → a config schema
the admin form can draw → an admin control that writes it.

    python scripts/wp-parity/check_widget_types_wired.py [--sabotage]
"""

from __future__ import annotations

import argparse
import io
import re
import sys
from pathlib import Path

import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(__file__))
import console_safe  # noqa: F401  — idempotent. A plain TextIOWrapper
# here is closed by the next module that wraps stdout, which is how a test
# that imports a guard ends up dying on "I/O operation on closed file".

ROOT = Path(__file__).resolve().parents[2]

WIDGETS = ROOT / "backend" / "app" / "shared" / "content" / "widgets.py"
ROUTES = ROOT / "backend" / "app" / "modules" / "settings" / "api" / "routes.py"
WIDGET_AREA = ROOT / "frontend" / "components" / "layout" / "widget-area.tsx"
WP_PARITY = ROOT / "frontend" / "lib" / "api" / "wp-parity.ts"
ADMIN_WIDGETS = ROOT / "frontend" / "app" / "admin" / "widgets" / "page.tsx"

# The WordPress core widget types the gap list named as missing.
NEW_TYPES = ("archives", "calendar", "recent_comments", "pages", "meta", "rss", "links")


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


SABOTAGE: dict[str, tuple[Path, str, str]] = {
    "type:registered": (WIDGETS, '"archives": {"name"', '"archivesX": {"name"'),
    "type:renderer": (WIDGET_AREA, 'case "archives":', 'case "archivesX":'),
    "type:schema": (WIDGETS, '"recent_comments": [', '"recent_commentsX": ['),
    "area:service": (WIDGETS, "async def create_area(", "async def _create_area_removed("),
    "area:route": (ROUTES, "async def create_widget_area(", "async def _create_widget_area_removed("),
    "area:client": (WP_PARITY, "createArea: async", "createAreaX: async"),
    "area:ui": (ADMIN_WIDGETS, "widgetsApi.createArea(", "widgetsApi.createAreaX("),
    "config:ui": (ADMIN_WIDGETS, "<ConfigField", "<ConfigFieldX"),
}


def evaluate() -> list[str]:
    failures: list[str] = []
    widgets = read(WIDGETS)
    routes = read(ROUTES)
    widget_area = read(WIDGET_AREA)
    wp_parity = read(WP_PARITY)
    admin = read(ADMIN_WIDGETS)

    # 1. Each named type is registered in WIDGET_TYPES. Matched as
    #    `"type": {` (a dict value), which only the WIDGET_TYPES entries use —
    #    the config schema uses `"type": [`, so a bare `"type":` check passed
    #    even after the registration was removed.
    for t in NEW_TYPES:
        if not re.search(rf'"{re.escape(t)}":\s*\{{', widgets):
            failures.append(f"widget type {t!r} is not registered in WIDGET_TYPES")

    # 2. The storefront renders each: a `case "<type>":` in widget-area.tsx.
    for t in NEW_TYPES:
        if not re.search(rf'case\s+"{re.escape(t)}"\s*:', widget_area):
            failures.append(f"widget-area.tsx has no case for {t!r} — it renders nothing")

    # 3. The config schema exists and covers the new types.
    if "WIDGET_CONFIG_SCHEMA" not in widgets:
        failures.append("WIDGET_CONFIG_SCHEMA was removed")
    else:
        for t in ("recent_posts", "recent_comments", "archives", "pages"):
            if f'"{t}": [' not in widgets:
                failures.append(f"no config schema for widget type {t!r}")

    # 4. Area create/delete exist as service + route + client + UI.
    if "async def create_area(" not in widgets or "async def delete_area(" not in widgets:
        failures.append("WidgetService.create_area/delete_area is missing")
    # Match the handlers, not a bare path string: `"/admin/widgets"` also
    # appears on the list GET, so a path-only check survived the create/delete
    # routes being removed.
    if "async def create_widget_area(" not in routes:
        failures.append("POST /settings/admin/widgets (create_widget_area) is missing")
    if "async def delete_widget_area(" not in routes:
        failures.append("DELETE /settings/admin/widgets/{id} (delete_widget_area) is missing")
    if "createArea:" not in wp_parity or "deleteArea:" not in wp_parity:
        failures.append("widgetsApi.createArea/deleteArea is missing")
    # The admin screen must actually call them — a client method with no caller
    # is the "route without a consumer" bug this project keeps re-finding.
    if "widgetsApi.createArea(" not in admin:
        failures.append("the widgets page never calls createArea")
    if "widgetsApi.deleteArea(" not in admin:
        failures.append("the widgets page never calls deleteArea")

    # 5. The per-widget config form is rendered (not just a title/content input).
    if "configSchema" not in admin:
        failures.append("the widgets page does not read the config schema")
    # Match the JSX element boundary, not a bare prefix: "<ConfigFieldX" still
    # contains "<ConfigField", so a substring check survived the rename.
    if not re.search(r"<ConfigField[\s/>]", admin):
        failures.append("the widgets page does not render per-widget config fields")
    # Drag & drop: the row must be draggable and reorder on drop.
    if "draggable" not in admin or "onDrop" not in admin:
        failures.append("the widgets page has no drag & drop reorder")

    return failures


def run_sabotage() -> int:
    print("sabotage audit — proving every rule can fail\n")
    problems = 0
    for rule_id, (path, find, replace) in SABOTAGE.items():
        if not path.is_file():
            print(f"  SKIP  {rule_id}: {path.name} absent")
            continue
        original = path.read_text(encoding="utf-8")
        if find not in original:
            print(f"  SKIP  {rule_id}: anchor not found")
            continue
        path.write_text(original.replace(find, replace), encoding="utf-8")
        try:
            failures = evaluate()
        finally:
            path.write_text(original, encoding="utf-8")
        if failures:
            print(f"  caught {rule_id}")
        else:
            problems += 1
            print(f"  MISSED {rule_id}: injected breakage did not trip any rule")
    if problems:
        print(f"\nsabotage: {problems} rule(s) failed to catch their own breakage")
        return 1
    print("\nsabotage: every rule caught its breakage")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sabotage", action="store_true")
    args = parser.parse_args()
    if args.sabotage:
        return run_sabotage()
    failures = evaluate()
    if failures:
        print("FAIL: widget types / config / areas are not fully wired")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("PASS: widget types, per-widget config and areas are wired end to end")
    return 0


if __name__ == "__main__":
    sys.exit(main())