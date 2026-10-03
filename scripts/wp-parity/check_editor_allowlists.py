"""Fail when the editor's client allowlist drifts from the backend's.

Three allowlists used to exist and disagreed. The narrowest one — the list the
editor applies on every keystroke — was missing 45 tags the backend accepts,
so inserting any of the app's own block patterns and typing one character
silently unwrapped them. Nothing caught it: tsc passed, lint passed, and the
pattern looked right in the picker.

The client list now lives in `frontend/lib/editor/allowlist.ts`. This compares
it against `ALLOWED_TAGS` in the backend sanitizer and fails on any difference,
in either direction.

Run:  python scripts/wp-parity/check_editor_allowlists.py
"""

from __future__ import annotations

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CLIENT = os.path.join(ROOT, "frontend", "lib", "editor", "allowlist.ts")
BACKEND = os.path.join(ROOT, "backend", "app", "shared", "content", "html_sanitizer.py")


def _extract(path: str, marker: str) -> set[str]:
    src = open(path, encoding="utf-8").read()
    i = src.find(marker)
    if i < 0:
        raise SystemExit(f"FAIL: {marker!r} not found in {path}")
    # Walk forward from the marker over quoted strings until the list closes.
    tags: set[str] = set()
    for m in re.finditer(r"[\"']([a-z0-9]+)[\"']", src[i:]):
        tags.add(m.group(1))
        if m.end() > len(src[i:]) - 1:
            break
    return tags


def backend_tags() -> set[str]:
    """ALLOWED_TAGS from the Python sanitizer, read from source."""
    src = open(BACKEND, encoding="utf-8").read()
    i = src.find("ALLOWED_TAGS: frozenset[str] = frozenset(")
    if i < 0:
        raise SystemExit("FAIL: backend ALLOWED_TAGS not found")
    j = src.find(")\n", i)
    body = src[i:j]
    return set(re.findall(r'"([a-z0-9]+)"', body))


def client_tags() -> set[str]:
    src = open(CLIENT, encoding="utf-8").read()
    i = src.find("export const ALLOWED_TAGS")
    if i < 0:
        raise SystemExit("FAIL: client ALLOWED_TAGS not found")
    j = src.find("];", i)
    return set(re.findall(r'"([a-z0-9]+)"', src[i:j]))


def _python_set(src: str, decl: str) -> set[str]:
    """Values of a frozenset literal in the backend sanitizer."""
    i = src.find(decl)
    if i < 0:
        raise SystemExit(f"FAIL: {decl} not found")
    j = src.find(")", i)
    return set(re.findall(r'"([a-z0-9-]+)"', src[i:j]))


def backend_attrs() -> set[str]:
    """Every attribute the server permits.

    Read by importing the module's constants rather than by parsing the source
    with a regex. The regex version had to guess where a multi-line
    `frozenset(...)` ended, and every guess was wrong in a way that reported
    tag names (`a`, `img`, `td`) and missed real attributes. The module is
    importable without a database — it only imports bleach and tinycss2.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location("_html_sanitizer", BACKEND)
    if spec is None or spec.loader is None:
        raise SystemExit("FAIL: could not load the backend sanitizer module")
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception as exc:  # pragma: no cover - import failure is the message
        raise SystemExit(f"FAIL: could not import the backend sanitizer: {exc}")

    found: set[str] = set()
    for table in (mod.ALLOWED_ATTRIBUTES, getattr(mod, "_EMBED_ALLOWED_ATTRIBUTES", {})):
        for names in table.values():
            found |= set(names)
    return found


def backend_css() -> set[str]:
    import importlib.util

    spec = importlib.util.spec_from_file_location("_html_sanitizer_css", BACKEND)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return set(mod.ALLOWED_CSS_PROPERTIES)


def client_attrs() -> set[str]:
    return _client_list("export const ALLOWED_ATTR")


def client_css() -> set[str]:
    return _client_list("export const ALLOWED_CSS_PROPERTIES")


def _client_list(marker: str) -> set[str]:
    """Quoted names in a client list literal.

    Comments are stripped first. They matter here: this gate was reporting
    `center` as an allowed attribute, picked up from a code comment explaining
    why the alignment button used to do nothing — a false failure caused by
    prose, which is exactly the kind of noise that trains people to ignore a
    gate.
    """
    src = open(CLIENT, encoding="utf-8").read()
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    src = re.sub(r"//[^\n]*", "", src)
    i = src.find(marker)
    if i < 0:
        raise SystemExit(f"FAIL: client {marker} not found")
    j = src.find("];", i)
    if j < 0:
        raise SystemExit(f"FAIL: client {marker} is not a closed list")
    return set(re.findall(r'"([a-z0-9-]+)"', src[i:j]))


def main() -> int:
    ok = True

    back, front = backend_tags(), client_tags()
    # iframe is in the client list and handled separately on the server (an
    # iframe is only kept from a known host), so it is expected to differ.
    front_only = front - back - {"iframe"}
    back_only = back - front

    print(f"backend ALLOWED_TAGS : {len(back)}")
    print(f"client  ALLOWED_TAGS : {len(front)}")
    if front_only:
        ok = False
        print(f"\nFAIL: client allows tags the server would strip: {sorted(front_only)}")
        print("      the editor would show them, the store would lose them.")
    if back_only:
        ok = False
        print(f"\nFAIL: server allows tags the editor strips: {sorted(back_only)}")
        print("      an inserted pattern would be unwrapped on the first keystroke.")

    # Attributes. The server keeps `style` on every tag plus a per-tag map; the
    # client's flat list is the union of both, so the comparison is one-way:
    # anything the editor keeps that the server would drop is a silent loss.
    back_a, front_a = backend_attrs(), client_attrs()
    attr_only = front_a - back_a
    attr_missing = back_a - front_a
    print(f"\nbackend attributes  : {len(back_a)}")
    print(f"client  attributes  : {len(front_a)}")
    if attr_only:
        ok = False
        print(f"\nFAIL: client allows attributes the server would strip: {sorted(attr_only)}")
        print("      the editor would keep them, the store would lose them.")
    if attr_missing:
        ok = False
        print(f"\nFAIL: server allows attributes the editor strips: {sorted(attr_missing)}")
        print("      an attribute the backend keeps would be dropped on every keystroke.")

    # CSS properties inside `style`. Without this the editor silently dropped
    # `text-align` — the alignment buttons wrote a style that never survived —
    # and nothing caught it, because this gate only compared tags.
    back_c, front_c = backend_css(), client_css()
    css_only = front_c - back_c
    css_missing = back_c - front_c
    print(f"\nbackend CSS props   : {len(back_c)}")
    print(f"client  CSS props   : {len(front_c)}")
    if css_only:
        ok = False
        print(f"\nFAIL: client allows CSS properties the server would strip: {sorted(css_only)}")
        print("      they would render in the editor and vanish on save.")
    if css_missing:
        ok = False
        print(f"\nFAIL: server allows CSS properties the editor strips: {sorted(css_missing)}")
        print("      a style the backend keeps would be removed on every keystroke.")

    if ok:
        print("\nPASS: the editor and the store agree on tags, attributes and CSS.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())