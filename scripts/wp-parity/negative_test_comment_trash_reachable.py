"""Negative test for check_comment_trash_reachable.

The regression this guards is a *removal*: the trash filter was deleted with a
comment saying nothing ever writes TRASH, while the bulk button in the same
panel did. So the sabotage is the deletion, and the gate has to go red on it.

  A. Delete the trash option — the original bug.
  B. Delete the bulk restore action — trash without a way back.
  C. Drop `restore` from the local action union. TypeScript would normally
     catch this, but only if the union is checked; and the failure mode is
     exactly the one this gate exists to prevent.

Run:  python scripts/wp-parity/negative_test_comment_trash_reachable.py
"""

from __future__ import annotations

import sys as _sys
_sys.path.insert(0, __import__("os").path.dirname(__file__))
import console_safe  # noqa: F401  — makes stdout safe for non-ASCII

import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
GATE = os.path.join(HERE, "check_comment_trash_reachable.py")
PANEL = os.path.join(
    ROOT, "frontend", "components", "admin", "blog", "comments-moderation-tab.tsx"
)

FILTER_LINE = '<option value="trash">'

RESTORE_BLOCK_RE = re.compile(
    r'    \{\n'
    r'      // The other half of trash\..*?\n'
    r'      id: "restore",\n'
    r'.*?\n'
    r'    \},\n',
    re.S,
)


def run_gate() -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, GATE], capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=300,
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def sabotage(label: str, apply_fn) -> bool:
    # Read with the newline normalised and write it back the way the file had
    # it. The panel is CRLF on disk; leaving that off makes every `\n` anchor
    # miss and the sabotage a silent no-op — the script would report success
    # having tested nothing. Checked rather than assumed, so a line-ending
    # change cannot quietly disarm this again.
    with open(PANEL, encoding="utf-8", newline="") as fh:
        on_disk = fh.read()
    crlf = "\r\n" in on_disk
    original = on_disk.replace("\r\n", "\n")

    def write(text: str) -> None:
        payload = text.replace("\n", "\r\n") if crlf else text
        with open(PANEL, "w", encoding="utf-8", newline="") as fh:
            fh.write(payload)

    try:
        changed = apply_fn(original)
        if changed == original:
            print(f"FAIL: {label} — the sabotage changed nothing, so the gate "
                  f"would be testing its own no-op.")
            return False
        write(changed)
        try:
            rc, out = run_gate()
        finally:
            write(original)
        rc_after, _ = run_gate()
        if rc_after != 0:
            print(f"FAIL: {label} — the gate did not pass again after restoring.")
            return False
        if rc == 0:
            print(f"FAIL: {label} still passed. The gate cannot see it.")
            return False
        caught = [ln.strip() for ln in out.splitlines()
                  if ln.strip().startswith("- ")]
        print(f"  {label} -> caught")
        for line in caught[:2]:
            print(f"      {line[:160]}")
        return True
    finally:
        write(original)


def main() -> int:
    if not os.path.isfile(GATE):
        print(f"FAIL: gate missing at {GATE}")
        return 1
    rc, out = run_gate()
    if rc != 0:
        print("FAIL: the gate does not pass on the real code, so a failure "
              "below would prove nothing.")
        print(out.strip()[-800:])
        return 1
    print("gate passes on the real code")

    ok = True

    def drop_filter(text: str) -> str:
        # Two `<option value="trash">` exist — the status filter and the
        # per-row edit dialog. Only the filter is the regression, so it is
        # anchored on the line that precedes it.
        anchor = '<option value="spam">اسپم / جفنگ</option>\n'
        if anchor not in text:
            raise AssertionError("the spam option anchor was not found")
        i = text.index(anchor) + len(anchor)
        j = text.index(FILTER_LINE, i)
        end = text.index("\n", j) + 1
        return text[:j] + text[end:]

    def drop_restore(text: str) -> str:
        new, n = RESTORE_BLOCK_RE.subn("", text, count=1)
        if n != 1:
            raise AssertionError(f"restore block matched {n} times")
        return new

    def drop_union(text: str) -> str:
        return text.replace(
            'action: "approve" | "unapprove" | "spam" | "trash" | "restore",',
            'action: "approve" | "unapprove" | "spam" | "trash",', 1)

    for label, fn in (
        ("A: delete the trash filter (the original bug)", drop_filter),
        ("B: delete the bulk restore action", drop_restore),
        ("C: drop restore from the local action union", drop_union),
    ):
        try:
            ok = sabotage(label, fn) and ok
        except AssertionError as exc:
            print(f"FAIL: {label} — {exc}")
            ok = False

    if not ok:
        return 1
    print("\nPASS: the gate goes red on every removal that would make the trash "
          "unreachable, and green again after each restore.")
    return 0


if __name__ == "__main__":
    sys.exit(main())