"""Guard: there is one canonical sitemap, and the API path redirects to it.

P1 "فید: دو مسیر موازی سایت‌مپ". Two sitemaps shipped — a Next.js
``app/sitemap.ts`` and a backend ``/content/sitemap.xml`` index with per-provider
files. Crawlers were told about exactly one (robots.txt advertises
``/sitemap.xml``, served by the storefront), so the backend index was an
unreachable second copy. This asserts the resolution stuck: the canonical
sitemap exists, robots points at it, the backend path redirects rather than
emitting a rival document, and the orphaned index service is gone.

    python scripts/wp-parity/check_sitemap_single_surface.py [--sabotage]
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

SITEMAP_TS = ROOT / "frontend" / "app" / "sitemap.ts"
ROBOTS_ROUTE = ROOT / "frontend" / "app" / "robots.txt" / "route.ts"
CONTENT_ROUTES = ROOT / "backend" / "app" / "modules" / "content" / "api" / "routes.py"
ORPHAN_SERVICE = (
    ROOT / "backend" / "app" / "modules" / "content" / "application" / "sitemap_index_service.py"
)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


SABOTAGE: dict[str, tuple[Path, str, str]] = {
    "canonical:exists": (SITEMAP_TS, "export default async function sitemap(", "async function _sitemap_removed("),
    "robots:points": (ROBOTS_ROUTE, "/sitemap.xml", "/sitemap-REMOVED.xml"),
    "api:redirects": (CONTENT_ROUTES, "RedirectResponse(url=f", "Response(content=f"),
    "orphan:absent": (ORPHAN_SERVICE, "", ""),  # handled specially below
}


def evaluate() -> list[str]:
    failures: list[str] = []
    sitemap = read(SITEMAP_TS)
    robots = read(ROBOTS_ROUTE)
    routes = read(CONTENT_ROUTES)

    # 1. The canonical sitemap is still the storefront's.
    if "function sitemap(" not in sitemap:
        failures.append("frontend/app/sitemap.ts has no sitemap() export")

    # 2. robots.txt advertises exactly that path.
    if "/sitemap.xml" not in robots:
        failures.append("robots.txt does not advertise /sitemap.xml")

    # 3. The API path redirects to the canonical one, not emitting its own body.
    handler = routes.split('"/sitemap.xml"', 1)
    if len(handler) < 2:
        failures.append("the backend /content/sitemap.xml route is missing")
    else:
        body = handler[1].split("@router.get", 1)[0]
        # Match the return call, not the import: `from fastapi.responses import
        # RedirectResponse` still contains the name, so a bare check survived
        # the return being rewritten to a plain Response.
        if not re.search(r"return\s+RedirectResponse\(", body):
            failures.append(
                "the backend /content/sitemap.xml no longer redirects to the "
                "canonical sitemap"
            )

    # 4. The orphaned index service is gone.
    if ORPHAN_SERVICE.is_file():
        failures.append(
            "sitemap_index_service.py still exists — a second sitemap source"
        )

    return failures


def run_sabotage() -> int:
    print("sabotage audit — proving every rule can fail\n")
    problems = 0
    for rule_id, (path, find, replace) in SABOTAGE.items():
        if rule_id == "orphan:absent":
            # The breakage is "the file reappears". Simulate by creating it.
            existed = path.exists()
            path.write_text("PROBE\n", encoding="utf-8")
            try:
                failures = evaluate()
            finally:
                if not existed:
                    path.unlink()
            if failures:
                print(f"  caught {rule_id}")
            else:
                problems += 1
                print(f"  MISSED {rule_id}: a reappearing service did not trip a rule")
            continue
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
        print("FAIL: the sitemap is not a single canonical surface")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("PASS: one canonical sitemap; the API path redirects and no orphan service")
    return 0


if __name__ == "__main__":
    sys.exit(main())