"""Negative tests for the quick-edit and take-over gates.

Both gates were written after the work they cover had already been done and the
gap was "nobody would notice if it broke again". So each sabotage removes one
hop and the gate has to notice.

  Quick edit:
    A. Remove the component from the page list's JSX. The file still exports
       it, the import still resolves, and every check on the dialog's own body
       still passes — the feature is simply unreachable.
    B. Drop a field from the payload. The form still shows it, the save still
       reports success, and the row behind the dialog does not change. This is
       the failure a "does the component exist" check cannot see.

  Take-over:
    C. Remove one of the two routes. Posts keep theirs; pages silently do not.
    D. Replace `force_release` with a bare `acquire`. Every string the gate
       looks for still exists, the endpoint answers `acquired: true`, and the
       caller gets no lock at all — because acquire reports "already held" for
       a lock somebody else owns.

Run:  python scripts/wp-parity/negative_test_wiring_pair.py
"""

from __future__ import annotations

import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "scripts", "wp-parity"))
import console_safe  # noqa: F401  — makes stdout safe for non-ASCII

GATE_QE = os.path.join(HERE, "check_page_quick_edit_wired.py")
GATE_TO = os.path.join(HERE, "check_lock_takeover_wired.py")

PAGES_PAGE = os.path.join(ROOT, "frontend", "app", "admin", "pages", "page.tsx")
QE_DIALOG = os.path.join(ROOT, "frontend", "components", "admin", "pages",
                         "quick-edit-page-dialog.tsx")
ROUTES = os.path.join(ROOT, "backend", "app", "modules", "blog", "api", "routes.py")
HOOK = os.path.join(ROOT, "frontend", "hooks", "use-page-editing-lock.ts")


def run_gate(gate: str) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, gate], capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=300,
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def edit(gate: str, label: str, path: str, fn) -> bool:
    with open(path, encoding="utf-8", newline="") as fh:
        on_disk = fh.read()
    crlf = "\r\n" in on_disk
    original = on_disk.replace("\r\n", "\n")

    def write(text: str) -> None:
        payload = text.replace("\n", "\r\n") if crlf else text
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write(payload)

    try:
        changed = fn(original)
    except AssertionError as exc:
        print(f"FAIL: {label} — {exc}")
        return False
    if changed == original:
        print(f"FAIL: {label} — nothing changed.")
        return False

    write(changed)
    try:
        rc, out = run_gate(gate)
    finally:
        write(original)

    rc_after, _ = run_gate(gate)
    if rc_after != 0:
        print(f"FAIL: {label} — the gate did not pass again after restoring.")
        return False
    if rc == 0:
        print(f"FAIL: {label} still passed. The gate cannot see it.")
        return False

    caught = [ln.strip() for ln in out.splitlines() if ln.strip().startswith("- ")]
    print(f"  {label} -> caught")
    for line in caught[:2]:
        print(f"      {line[:140]}")
    return True


def main() -> int:
    ok = True

    for gate in (GATE_QE, GATE_TO):
        rc, out = run_gate(gate)
        if rc != 0:
            print(f"FAIL: {os.path.basename(gate)} does not pass on the real code.")
            print(out.strip()[-600:])
            return 1
    print("both gates pass on the real code")

    # A: the dialog is no longer rendered by the page list.
    def drop_render(text: str) -> str:
        new, n = re.subn(r"[ \t]*<QuickEditPageDialog\b.*?/>\n", "", text, count=1,
                        flags=re.S)
        if n != 1:
            raise AssertionError(f"the render matched {n} times")
        return new

    ok = edit(GATE_QE, "A: remove the dialog from the page list", PAGES_PAGE,
              drop_render) and ok

    # B: a field is rendered but no longer sent.
    def drop_field(text: str) -> str:
        needle = "        allow_comments: allowComments,"
        if needle not in text:
            raise AssertionError("the allow_comments payload line is not in the expected shape")
        return text.replace(needle, "        // sabotage: field dropped", 1)

    ok = edit(GATE_QE, "B: drop allow_comments from the payload", QE_DIALOG,
              drop_field) and ok

    # C: one of the two routes disappears.
    def drop_page_route(text: str) -> str:
        needle = '"/pages/{page_id}/lock/take-over"'
        if needle not in text:
            raise AssertionError("the page take-over route is not in the expected shape")
        return text.replace(needle, '"/articles/{page_id}/lock/take-over"', 1)

    ok = edit(GATE_TO, "C: remove the page take-over route", ROUTES,
              drop_page_route) and ok

    # D: force-release replaced by a bare acquire.
    def acquire_only(text: str) -> str:
        needle = "    await PostLockService.force_release(page_id)"
        if needle not in text:
            raise AssertionError("the force_release call is not in the expected shape")
        return text.replace(needle, "    # sabotage: acquire without releasing", 1)

    ok = edit(GATE_TO, "D: take over by acquiring without releasing", ROUTES,
              acquire_only) and ok

    if not ok:
        return 1
    print("\nPASS: both gates see a removed render, a dropped field, a missing "
          "route, and an acquire that cannot break a lock.")
    return 0


if __name__ == "__main__":
    sys.exit(main())