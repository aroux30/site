"""Negative test for the one-click moderation link.

A bearer capability is only as good as the checks behind it, and every check
here has a way of quietly disappearing while the feature still looks finished —
the endpoint keeps returning a page, the mail keeps carrying links, and nothing
raises. So each sabotage removes one protection and the fixture must go red.

  A. Drop the `already_done` half of single-use. The link then acts twice: the
     fixture clicks it twice and expects the second to be refused.
  B. Drop the action binding from the verifier, so a token minted for approving
     works for trashing — one leaked link becomes a general moderation
     capability rather than a single comment's.
  C. Drop the comment binding, so a token works on any comment.
  D. Drop the expiry check.

The ones that matter most are B and C. A and D are real protections; B and C are
the ones that turn a mail into a permanent capability for whoever reads it.

Run:  python scripts/wp-parity/negative_test_comment_action.py
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
FIXTURE = os.path.join(ROOT, ".p1-tests", "comment_action_test.py")
TOKEN = os.path.join(
    ROOT, "backend", "app", "modules", "blog", "application",
    "comment_moderation_token.py",
)

SABOTAGES = [
    (
        "A: the link stops being single-use",
        [("    if already_done:\n        return False",
          "    if False:  # sabotage: single-use removed")],
    ),
    (
        "B: a token is no longer bound to its action",
        [("    if not hmac.compare_digest(token_action, action):\n        return False",
          "    if False:  # sabotage: action binding removed")],
    ),
    (
        "C: a token is no longer bound to its comment",
        [("    if not hmac.compare_digest(str(token_id), str(comment_id)):\n        return False",
          "    if False:  # sabotage: comment binding removed")],
    ),
    (
        "D: tokens never expire",
        [("        if int(expiry) <= current:\n            return False",
          "        if False:  # sabotage: expiry removed")],
    ),
]


def run_fixture() -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, FIXTURE],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=600,
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def apply(pairs: list[tuple[str, str]]) -> str | None:
    """Patch the verifier, refusing to proceed if a sabotage did not land.

    A negative test whose sabotage silently failed to apply proves nothing —
    the fixture could go red for an unrelated reason and the check would still
    pass. So every anchor is verified present before anything is written.
    """
    with open(TOKEN, encoding="utf-8") as fh:
        original = fh.read()
    text = original
    for needle, replacement in pairs:
        if needle not in text:
            print(f"FAIL: anchor not found, sabotage not applied: {needle[:60]!r}")
            return None
        text = text.replace(needle, replacement, 1)
    with open(TOKEN, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    return original


def main() -> int:
    if not os.path.isfile(FIXTURE):
        print(f"FAIL: fixture missing at {FIXTURE}")
        return 1

    rc, out = run_fixture()
    if rc != 0:
        print("FAIL: the fixture does not pass on the real code, so a failure "
              "below would prove nothing.")
        print(out.strip()[-900:])
        return 1
    print("fixture passes on the real code")

    for label, pairs in SABOTAGES:
        original = apply(pairs)
        if original is None:
            return 1
        try:
            rc_broken, out_broken = run_fixture()
        finally:
            with open(TOKEN, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(original)

        rc_after, out_after = run_fixture()
        if rc_after != 0:
            print(f"FAIL: {label} — the fixture did not pass again after "
                  f"restoring.")
            print(out_after.strip()[-900:])
            return 1
        if rc_broken == 0:
            print(f"FAIL: {label} still passed. The fixture cannot see it.")
            return 1

        caught = [ln.strip() for ln in out_broken.splitlines() if "GAPS" in ln]
        print(f"  {label} -> caught")
        for line in caught:
            print(f"      {line[:200]}")

    print("\nPASS: every protection was proven load-bearing, and the fixture "
          "was green again after each restore.")
    return 0


if __name__ == "__main__":
    sys.exit(main())