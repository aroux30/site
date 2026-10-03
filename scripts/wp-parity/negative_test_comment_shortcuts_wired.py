"""Negative test for check_comment_shortcuts_wired.

Two sabotages, and the first is the one a presence-only check cannot see.

  A. **Swap two bindings.** `a` trashes and `t` approves. The listener still
     registers eight cases, every key still "does something", and every
     assertion that counts cases passes. A moderator hitting `a` to approve
     forty comments empties the trash instead. This is why the gate reads each
     case's body rather than looking for the key.
  B. **Remove the typing guard.** Now the listener fires on every keystroke
     anywhere on the page, and typing "just a note" into the search box approves
     the focused row on `a`, trashes it on `t`, and unapproves it on `u`. The
     listener is unchanged; only the guard is gone.

Run:  python scripts/wp-parity/negative_test_comment_shortcuts_wired.py
"""

from __future__ import annotations

import sys as _sys
_sys.path.insert(0, __import__("os").path.dirname(__file__))
import console_safe  # noqa: F401  — makes stdout safe for non-ASCII

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
GATE = os.path.join(HERE, "check_comment_shortcuts_wired.py")
PANEL = os.path.join(ROOT, "frontend", "components", "admin", "blog",
                     "comments-moderation-tab.tsx")

NL = chr(10)

APPROVE_CASE = '        case "a":' + NL + '          e.preventDefault();' + NL + \
    '          void runBulk("approve", [current]);'
TRASH_CASE = '        case "t":' + NL + '          e.preventDefault();' + NL + \
    '          void runBulk("trash", [current]);'

GUARD = (
    '      if (' + NL +
    '        target &&' + NL +
    '        (target.tagName === "INPUT" ||' + NL +
    '          target.tagName === "TEXTAREA" ||' + NL +
    '          target.isContentEditable)' + NL +
    '      ) {' + NL +
    '        return;' + NL +
    '      }'
)


def run_gate() -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, GATE], capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=300,
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def main() -> int:
    with open(PANEL, encoding="utf-8", newline="") as fh:
        on_disk = fh.read()
    crlf = NL in on_disk and chr(13) + chr(10) in on_disk
    original = on_disk.replace(chr(13) + chr(10), NL)

    def write(text: str) -> None:
        payload = text.replace(NL, chr(13) + chr(10)) if crlf else text
        with open(PANEL, "w", encoding="utf-8", newline="") as fh:
            fh.write(payload)

    rc, out = run_gate()
    if rc != 0:
        print("FAIL: the gate does not pass on the real code.")
        print(out.strip()[-800:])
        return 1
    print("gate passes on the real code")

    ok = True
    for label, changed in (
        ("A: swap 'a' (approve) and 't' (trash)",
         original.replace(APPROVE_CASE, TRASH_CASE, 1)
         .replace(TRASH_CASE.replace("runBulk(\"trash\"", "runBulk(\"approve\""),
                                    APPROVE_CASE.replace("runBulk(\"approve\"",
                                                         "runBulk(\"trash\""), 1)
         if APPROVE_CASE in original and TRASH_CASE in original else None),
        ("B: remove the typing guard",
         original.replace(GUARD, "      // sabotage: the guard is gone", 1)
         if GUARD in original else None),
    ):
        if changed is None:
            print(f"FAIL: {label} — the anchor is not in the expected shape, so "
                  f"the gate was never tested against this sabotage.")
            ok = False
            continue
        if changed == original:
            print(f"FAIL: {label} — nothing changed.")
            ok = False
            continue

        write(changed)
        try:
            rc_broken, out_broken = run_gate()
        finally:
            write(original)

        rc_after, _ = run_gate()
        if rc_after != 0:
            print(f"FAIL: {label} — the gate did not pass again after restoring.")
            ok = False
            continue
        if rc_broken == 0:
            print(f"FAIL: {label} still passed. The gate cannot see it.")
            ok = False
            continue

        caught = [ln.strip() for ln in out_broken.splitlines()
                  if ln.strip().startswith("- ")]
        print(f"  {label} -> caught")
        for line in caught[:3]:
            print(f"      {line[:150]}")

    if not ok:
        return 1
    print("\nPASS: the gate goes red on swapped bindings and on a listener that "
          "fires while the user types.")
    return 0


if __name__ == "__main__":
    sys.exit(main())