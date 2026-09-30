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


def main() -> int:
    back = backend_tags()
    front = client_tags()
    # iframe is in the client list and handled separately on the server (an
    # iframe is only kept from a known host), so it is expected to differ.
    front_only = front - back - {"iframe"}
    back_only = back - front

    print(f"backend ALLOWED_TAGS : {len(back)}")
    print(f"client  ALLOWED_TAGS : {len(front)}")

    ok = True
    if front_only:
        ok = False
        print(f"\nFAIL: client allows tags the server would strip: {sorted(front_only)}")
        print("      the editor would show them, the store would lose them.")
    if back_only:
        ok = False
        print(f"\nFAIL: server allows tags the editor strips: {sorted(back_only)}")
        print("      an inserted pattern would be unwrapped on the first keystroke.")
    if ok:
        print("\nPASS: the editor and the store agree on the tag set.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())