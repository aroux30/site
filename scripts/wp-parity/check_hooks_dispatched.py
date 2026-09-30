"""Permanent guard: every declared hook must have a dispatch site.

Wave 6 #80. `HOOK_PAGE_BODY_RENDER` and `HOOK_SEO_METADATA` were declared in
`shared/plugins/registry.py` and never dispatched anywhere, so a plugin binding
either one looked wired and silently never ran.

This is the "rules need execution preconditions" failure class: a declaration is
not a mechanism. The check parses the constant, greps the whole backend for a
call site, and fails when the count is zero.

Negative-tested by `negative_test_hooks.py`, which deletes a dispatch call and
confirms this exits non-zero. A guard that cannot fail is not a guard.

Run:  python scripts/wp-parity/check_hooks_dispatched.py
Exit:  0 = every hook dispatched, 1 = at least one is dead.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "backend" / "app" / "shared" / "plugins" / "registry.py"
BACKEND = ROOT / "backend" / "app"

# A hook is dispatched by being passed to apply_filters() or do_action() as the
# first argument. Matching the bare constant name would also match the
# declaration itself and the import line, which is how "0 dispatches" was
# previously reported as "looks referenced".
DISPATCHERS = ("apply_filters", "do_action")


def declared_hooks() -> dict[str, str]:
    """{constant_name: hook_string} for every HOOK_* constant."""
    tree = ast.parse(REGISTRY.read_text(encoding="utf-8"))
    out: dict[str, str] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id.startswith("HOOK_"):
                if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                    out[target.id] = node.value.value
    return out


def dispatch_sites() -> dict[str, list[str]]:
    """{constant_name: ["file:line", ...]} for real dispatch calls."""
    found: dict[str, list[str]] = {}
    for path in BACKEND.rglob("*.py"):
        if "__pycache__" in path.parts or path == REGISTRY:
            continue
        try:
            src = path.read_text(encoding="utf-8")
            tree = ast.parse(src)
        except Exception:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
            if name not in DISPATCHERS or not node.args:
                continue
            first = node.args[0]
            if isinstance(first, ast.Name) and first.id.startswith("HOOK_"):
                rel = path.relative_to(ROOT).as_posix()
                found.setdefault(first.id, []).append(f"{rel}:{first.lineno}")
    return found


def main() -> int:
    if not REGISTRY.exists():
        print(f"FAIL: {REGISTRY} not found")
        return 1

    hooks = declared_hooks()
    if not hooks:
        print("FAIL: no HOOK_* constants found — the parser is broken, not the code")
        return 1

    sites = dispatch_sites()
    print(f"declared hooks      : {len(hooks)}")
    print(f"hooks with dispatch : {len(sites)}")

    dead = sorted(name for name in hooks if name not in sites)

    for name in sorted(hooks):
        where = sites.get(name)
        mark = "OK  " if where else "DEAD"
        detail = ", ".join(where) if where else "no dispatch site"
        print(f"  [{mark}] {name:34} {hooks[name]:32} {detail}")

    if dead:
        print(f"\nFAIL: {len(dead)} hook(s) declared but never dispatched: {', '.join(dead)}")
        print("\nEither dispatch them at the right point, or delete the constant")
        print("so no plugin can bind to a seam that will never fire.")
        return 1

    print("\nPASS: every declared hook has a dispatch site.")
    return 0


if __name__ == "__main__":
    sys.exit(main())