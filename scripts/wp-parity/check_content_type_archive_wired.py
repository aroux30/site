"""A content type's archive must be reachable, and rendered from its fields.

`GET /content-types/{slug}/entries` existed with no caller anywhere in the
frontend, so a type an operator had carefully defined and filled was
unreachable on the storefront — the entries existed and nothing showed them.
A route without a consumer is not a feature.

So this checks the chain, in both directions:

  * the public route exists and returns only published entries;
  * the public client addresses it — and is separate from the admin client,
    because that one can list entries in *any* status, and a storefront page
    reaching for it would silently widen what it shows;
  * a page consumes it, renders the declared fields rather than dumping JSON,
    and 404s on an unknown slug instead of rendering an empty archive.

Run:  python scripts/wp-parity/check_content_type_archive_wired.py
"""

from __future__ import annotations

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import console_safe  # noqa: F401  — makes stdout safe for non-ASCII

ROUTES = os.path.join(ROOT, "backend", "app", "modules", "content",
                      "api", "routes.py")
CLIENT = os.path.join(ROOT, "frontend", "lib", "api", "cms-admin.ts")
PAGE = os.path.join(ROOT, "frontend", "app", "(store)", "content", "[slug]",
                    "page.tsx")

failures: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {label}: {ok}")
    if not ok:
        failures.append(f"{label}: {detail}" if detail else label)


def _decorator_of(source: str, path_fragment: str) -> str | None:
    """The whole `@router.<verb>( ... )` decorator naming `path_fragment`.

    Brackets are balanced by hand. A `[^)]*` character class looks like it does
    the same thing and does not: it stops at the first `)`, which in these
    decorators is inside `summary="... (something)"`, so anything written after
    the summary is invisible — and a guard added there is exactly the change
    this check is looking for.
    """
    at = source.find(f'"{path_fragment}"')
    if at == -1:
        return None
    start = source.rfind("@router.", 0, at)
    if start == -1:
        return None
    open_at = source.find("(", start)
    if open_at == -1:
        return None
    depth = 0
    for i in range(open_at, len(source)):
        if source[i] == "(":
            depth += 1
        elif source[i] == ")":
            depth -= 1
            if depth == 0:
                return source[start:i + 1]
    return None


def main() -> int:
    for path in (ROUTES, CLIENT, PAGE):
        if not os.path.isfile(path):
            print(f"FAIL: missing {path}")
            return 1
    routes, client, page = (read(p) for p in (ROUTES, CLIENT, PAGE))

    # 1. the routes
    check("the public entries route exists",
          '"/content-types/{type_slug}/entries"' in routes)
    check("and returns only published entries",
          "status=PageStatus.PUBLISHED" in routes)
    check("a public type list exists for the archive to read",
          '"/content-types"' in routes and "list_public_content_types" in routes)
    # The whole decorator, brackets balanced. `[^)]*` stopped at the first `)`
    # — which is inside `summary="...(storefront)"` — so a guard added after the
    # summary was invisible and the check passed on a route that would 403 every
    # customer.
    guard = _decorator_of(routes, "/content-types")
    check("the type list is not behind a write guard",
          guard is not None and "dependencies" not in guard,
          "the public type list would require a write permission")

    # 2. the client. Separate from the admin one on purpose, and the separation
    #    has to hold or a storefront page inherits admin visibility.
    check("a public client exists", "contentTypesPublicApi" in client)
    check("it calls the public entries route",
          "/content/content-types/${typeSlug}/entries" in client)
    # Slice from the *declaration*, not the first mention: a bare find() on
    # "export const contentTypesApi" is a prefix of neither, but searching for
    # the object name returns a slice that starts at its first reference —
    # inside the public client — and so reported the public client as reaching
    # into the admin one.
    admin_at = client.find("export const contentTypesApi = {")
    public_at = client.find("export const contentTypesPublicApi = {")
    admin_block = client[admin_at:public_at] if admin_at != -1 and public_at != -1 else ""
    check("the admin client is not reused for the storefront",
          "contentTypesPublicApi" not in admin_block,
          "the storefront client is defined inside the admin client")

    # 3. the page
    check("an archive page exists", os.path.isfile(PAGE))
    check("it reads the type list", "contentTypesPublicApi.list()" in page)
    check("it reads the entries", "contentTypesPublicApi.entries(" in page)
    check("an unknown slug 404s rather than rendering empty",
          "notFound()" in page)
    check("fields are rendered by their declared label",
          "field_schema" in page and "label" in page)
    check("and not as a raw JSON dump",
          "JSON.stringify(entry.data)" not in page,
          "the page renders the raw object instead of its declared fields")
    check("declared order is kept", "declared" in page and "rest" in page)
    check("the page is a server component, so entries render without JS",
          "use client" not in page)

    if failures:
        print("\nFAIL:")
        for f in failures:
            print(f"  {f}")
        return 1
    print("\nPASS: a content type's published entries are reachable at "
          "/content/<slug>, rendered from their declared fields.")
    return 0


def read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


if __name__ == "__main__":
    sys.exit(main())