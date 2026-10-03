"""Image undo/redo navigation and save-as-copy, on the real chain.

P2 "مدیا: تاریخچه‌ی ویرایش تصویر (Undo/Redo)". Four live bugs lived in this
feature while every layer of it "existed":

  * the edit routes passed ``asset.file_path`` (``media/<name>``) to the
    editor, which opens it from cwd — the file lives at
    ``<UPLOAD_DIR>/media/<name>``, so every crop/resize/rotate/flip/optimize
    raised FileNotFoundError;
  * the route helper called ``register_derived_asset(edit_operation=...)``
    where the service takes ``suffix`` — TypeError on every edit that got
    that far;
  * the client read ``data.items`` off a route that returns a bare array, so
    the history panel was handed undefined and never rendered;
  * ``list_edit_history`` fetched only direct children of the root, so a
    chain of depth > 1 lost its original and its current file — no
    ``is_current`` match, no undo/redo index, no badge;
  * the EXIF route had the same wrong path base, reading a missing file and
    returning ``{}`` (the error is swallowed) — "no camera data" for a photo
    that had some.

This gate drives the whole flow through the ASGI app: edit twice, read the
chain, duplicate, and check the copy is standalone.

    python scripts/wp-parity/check_media_undo_redo.py
"""

from __future__ import annotations

import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def _repo_root() -> str:
    d = HERE
    for _ in range(6):
        if os.path.isdir(os.path.join(d, ".p1-tests")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    return os.path.normpath(os.path.join(HERE, "..", ".."))


ROOT = _repo_root()
FIXTURE = os.path.join(ROOT, ".p1-tests", "media_undo_redo_test.py")
CLIENT = os.path.join(ROOT, "frontend", "lib", "api", "wp-parity.ts")
PAGE = os.path.join(ROOT, "frontend", "app", "admin", "media", "page.tsx")
ROUTES = os.path.join(ROOT, "backend", "app", "modules", "media", "api", "routes.py")
CHECK_LINE = re.compile(r"^\d+\.")


def main() -> int:
    failures: list[str] = []

    def check(label: str, ok: bool, detail: str = "") -> None:
        print(f"  {label}: {ok}")
        if not ok:
            failures.append(f"{label}: {detail}" if detail else label)

    # The UI half: undo/redo buttons and a save-as-copy control exist and are
    # wired to handlers (a button with no handler is decoration).
    page = open(PAGE, encoding="utf-8").read() if os.path.isfile(PAGE) else ""
    check("the page has undo and redo controls",
          "واگرد" in page and "ازنو" in page,
          "no undo/redo buttons on the media page")
    check("they walk the chain",
          "navigateChain" in page, "buttons exist but do not navigate")
    check("the page has a save-as-copy control",
          "ذخیره به‌عنوان کپی" in page and "duplicateImage" in page,
          "no save-as-copy button")

    # The client half: history parses the array shape, duplicate exists.
    client = open(CLIENT, encoding="utf-8").read() if os.path.isfile(CLIENT) else ""
    check("the client parses the history array shape",
          "Array.isArray(data)" in client,
          "the client still reads data.items off an array")
    check("the client has a duplicate method",
          "/edit/duplicate" in client)

    # The route half: the edit routes resolve the real on-disk path.
    routes = open(ROUTES, encoding="utf-8").read() if os.path.isfile(ROUTES) else ""
    check("the edit routes resolve the real file path",
          "_resolve_edit_source" in routes and "asset.file_path, x=body.x" not in routes,
          "a route still hands the editor the relative file_path")
    check("the EXIF route resolves the real file path",
          "extract_exif(_resolve_edit_source(asset))" in routes,
          "EXIF reads asset.file_path relative to cwd and returns {} silently")
    check("the duplicate route exists", "/edit/duplicate" in routes)

    # Behaviour: the whole flow through the app.
    if not os.path.isfile(FIXTURE):
        print(f"SKIP: fixture missing at {FIXTURE}")
        return 2
    try:
        proc = subprocess.run(
            [sys.executable, "-B", FIXTURE],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=300,
        )
    except subprocess.TimeoutExpired:
        check("the undo/redo fixture ran", False, "timed out")
    else:
        for ln in (proc.stdout or "").splitlines():
            if CHECK_LINE.match(ln.strip()):
                print(f"     {ln.strip()}")
        check("the chain is navigable and the copy is standalone",
              proc.returncode == 0, (proc.stdout or "")[-400:])

    if failures:
        print("\nFAIL:")
        for f in failures:
            print(f"  {f}")
        return 1
    print("\nPASS: image edits chain, the chain is navigable, and save-as-copy "
          "produces a standalone asset.")
    return 0


if __name__ == "__main__":
    sys.exit(main())