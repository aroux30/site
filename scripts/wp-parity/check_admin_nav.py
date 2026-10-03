"""Permanent guard: every admin page route must be linked from the sidebar.

Replaces the promise in a code comment. `admin/layout.tsx` said "Exported so a
test can assert that every admin route is reachable", but no such test
existed — so two routes had already shipped with no sidebar entry and could
only be opened by typing the URL.

This runs the real check by parsing both sides, and it is negative-tested by
``scripts/wp-parity/negative_test_admin_nav.py``: drop one link and confirm
this exits non-zero. A guard that cannot fail is not a guard.

Run:  python scripts/wp-parity/check_admin_nav.py
Exit: 0 = every route linked, 1 = an unlinked route exists (or the file is
      unreadable, which is also a failure — never a silent pass).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LAYOUT = ROOT / "frontend" / "app" / "admin" / "layout.tsx"
ADMIN_APP = ROOT / "frontend" / "app" / "admin"

# Routes that are legitimately not sidebar entries.
#   /admin            — a redirect stub to /admin/dashboard
#   /admin/<x>/[id]   — detail pages reached by clicking a row on their list
ALWAYS_IGNORE = {
    "/admin",
    # A test fixture, not a feature: the page that mounts the content editor on
    # its own so frontend/scripts/verify-editor-toolbar.mjs can drive its
    # toolbar in a real browser. It belongs under /admin (the staff guard in
    # middleware.ts covers only /admin and /account, so at its original
    # /editor-probe path it was reachable by anyone who typed the URL), which
    # is exactly why it must never appear in the sidebar. If it is ever linked
    # in adminLinks, this exception is no longer needed and the entry should go
    # — a navigation entry to a test page is itself a bug.
    "/admin/editor-probe",
}


def parse_links() -> set[str]:
    """Every href in the exported ``adminLinks`` array."""
    src = LAYOUT.read_text(encoding="utf-8")
    start = src.find("export const adminLinks")
    if start < 0:
        raise SystemExit("FAIL: adminLinks not found in layout.tsx")
    end = src.find("\n];", start)
    if end < 0:
        raise SystemExit("FAIL: adminLinks array is unterminated")
    block = src[start:end]
    return {"/" + m for m in re.findall(r'href:\s*"/([^"]+)"', block)}


def discover_routes() -> set[str]:
    """Every /admin route that renders a page.tsx."""
    found: set[str] = set()
    for page in ADMIN_APP.rglob("page.tsx"):
        rel = page.parent.relative_to(ADMIN_APP)
        parts = rel.parts
        if any(p.startswith("[") for p in parts):
            continue  # dynamic segment — reached via its list page
        found.add("/admin/" + "/".join(parts) if parts else "/admin")
    return found


def is_linked(route: str, links: set[str]) -> bool:
    if route in ALWAYS_IGNORE:
        return True
    if route in links:
        return True
    # A section link covers its children: /admin/products covers
    # /admin/products/123. The bare "/admin" link is a redirect stub, not a
    # real entry, so it must not be treated as covering everything.
    return any(
        link != "/admin" and route.startswith(link + "/") for link in links
    )


def main() -> int:
    if not LAYOUT.exists():
        print(f"FAIL: {LAYOUT} not found")
        return 1
    if not ADMIN_APP.exists():
        print(f"FAIL: {ADMIN_APP} not found")
        return 1

    links = parse_links()
    routes = discover_routes()

    unlinked = sorted(r for r in routes if not is_linked(r, links))

    print(f"admin sidebar links : {len(links)}")
    print(f"admin page routes   : {len(routes)}")

    if unlinked:
        print(f"\nFAIL: {len(unlinked)} admin route(s) have no sidebar link:")
        for route in unlinked:
            print(f"  - {route}")
        print("\nAdd an entry to `adminLinks` in frontend/app/admin/layout.tsx.")
        return 1

    print("\nPASS: every admin page route is reachable from the sidebar.")
    return 0


if __name__ == "__main__":
    sys.exit(main())