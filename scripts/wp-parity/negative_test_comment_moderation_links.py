"""Negative test for check_comment_moderation_links.

The gate asserts the mail carries three links and renders no placeholder. Both
assertions can go vacuous — a template that drops a link still "has no leftover
placeholder", and a variable that is declared but never supplied is exactly the
bug this gate exists for, so a sabotage in the *template's* variables list must
be visible.

Two sabotages:

  A. Remove `{{approve_url}}` from the template html. The mail then offers two
     of three links. Nothing raises; a moderator just opens the panel.
  B. Add a variable to the template that the code never supplies, so every
     rendered mail shows the literal `{{...}}` where a button should be. This
     is the failure the gate's first assertion exists to catch, and it is the
     one that ships silently.

Run:  python scripts/wp-parity/negative_test_comment_moderation_links.py
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
GATE = os.path.join(HERE, "check_comment_moderation_links.py")
TEMPLATES = os.path.join(
    ROOT, "backend", "app", "modules", "notifications", "application",
    "email_service.py",
)

ANCHOR = '<a href="{{approve_url}}"'

SABOTAGES = [
    (
        "A: drop the approve link from the mail",
        [(ANCHOR, '<a href="#"')],
    ),
    (
        "B: declare a variable nothing supplies",
        [('"approve_url", "spam_url", "trash_url",',
          '"approve_url", "spam_url", "trash_url", "never_supplied",')],
    ),
]


def run_gate() -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, GATE], capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=600,
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


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

    with open(TEMPLATES, encoding="utf-8") as fh:
        original = fh.read()

    for label, pairs in SABOTAGES:
        text = original
        for needle, replacement in pairs:
            if needle not in text:
                print(f"FAIL: anchor not found, sabotage not applied: {needle[:60]!r}")
                return 1
            text = text.replace(needle, replacement, 1)
        with open(TEMPLATES, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        try:
            rc_broken, out_broken = run_gate()
        finally:
            with open(TEMPLATES, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(original)

        rc_after, _ = run_gate()
        if rc_after != 0:
            print(f"FAIL: {label} — the gate did not pass again after restoring.")
            return 1
        if rc_broken == 0:
            print(f"FAIL: {label} still passed. The gate cannot see it.")
            return 1

        caught = [ln.strip() for ln in out_broken.splitlines()
                  if ln.strip().startswith("-") or "FAIL" in ln]
        print(f"  {label} -> caught")
        for line in caught[:3]:
            print(f"      {line[:180]}")

    print("\nPASS: the gate went red on a missing link and on an unsupplied "
          "variable, and green again after each restore.")
    return 0


if __name__ == "__main__":
    sys.exit(main())