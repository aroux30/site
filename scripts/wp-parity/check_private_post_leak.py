"""Guard: a PRIVATE blog post body must never be served from the public route.

Gap: docs/store-relevant-cms-gaps-2026-10-01.md, P0 "نوشته: نشت نوشته‌ی خصوصی
از مسیر جزئیات". ``BlogService.get_post_by_slug`` filtered ``status`` but not
``visibility``, so any visitor holding the URL could read the body of a post
whose author marked it private.

This guard is structural, not behavioural: it asserts the public read path
applies the same ``visibility`` filter the public listings already apply. It
cannot be satisfied by a comment, a docstring, or an unused helper — it fails
unless the filter is in the query that the public route actually calls.

    python scripts/wp-parity/check_private_post_leak.py
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SERVICE = ROOT / "backend" / "app" / "modules" / "blog" / "application" / "blog_service.py"
ROUTES = ROOT / "backend" / "app" / "modules" / "blog" / "api" / "routes.py"


def find_method(tree: ast.AST, cls_name: str, method_name: str) -> ast.FunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == cls_name:
            for item in node.body:
                if isinstance(item, ast.AsyncFunctionDef) and item.name == method_name:
                    return item
    raise SystemExit("FAIL: %s.%s not found in %s" % (cls_name, method_name, SERVICE))


def public_route_uses_published_only(tree: ast.AST) -> bool:
    """The public GET /posts/{slug} route must read with only_published=True.

    If the route ever stops pinning that flag the guard below would silently
    stop describing the public path, so this is asserted rather than assumed.
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "get_post_by_slug":
            for call in ast.walk(node):
                if (
                    isinstance(call, ast.Call)
                    and isinstance(call.func, ast.Attribute)
                    and call.func.attr == "get_post_by_slug"
                ):
                    for kw in call.keywords:
                        if kw.arg == "only_published" and isinstance(kw.value, ast.Constant):
                            return bool(kw.value.value)
    raise SystemExit("FAIL: no get_post_by_slug service call found in the public route")


def filters_visibility(meth: ast.AsyncFunctionDef) -> bool:
    """True when the SELECT built in this method filters ``visibility``.

    Looks for a comparison of BlogPost.visibility inside a ``where(...)`` call
    on the statement that the method builds, which is where the other public
    listings put it. Comparing against the attribute anywhere in the method is
    not enough: a read of ``post.visibility`` in a lock check is unrelated.
    """
    for node in ast.walk(meth):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        if node.func.attr != "where":
            continue
        for sub in ast.walk(node):
            if (
                isinstance(sub, ast.Compare)
                and isinstance(sub.left, ast.Attribute)
                and sub.left.attr == "visibility"
            ):
                return True
    return False


def main() -> int:
    service_tree = ast.parse(SERVICE.read_text(encoding="utf-8"))
    route_tree = ast.parse(ROUTES.read_text(encoding="utf-8"))

    if not public_route_uses_published_only(route_tree):
        print("FAIL: the public /posts/{slug} route no longer pins only_published=True.")
        print("      The guard below would not describe the public path any more.")
        return 1

    meth = find_method(service_tree, "BlogService", "get_post_by_slug")
    if not filters_visibility(meth):
        print("FAIL: get_post_by_slug does not filter BlogPost.visibility.")
        print("      A PRIVATE post is reachable by URL and its body is served.")
        print("      Every public listing here filters visibility; the detail path must too.")
        return 1

    print("PASS: the public post detail path filters visibility as well as status.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
