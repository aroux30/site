"""Negative test for comment_previously_approved.

The dangerous version of this feature is not "it does nothing" — that is
invisible and merely makes the queue work harder. The dangerous version is "it
approves the wrong comment", which looks identical from the outside and turns
the switch into a publisher for anyone who borrows a name.

So the sabotages here all *widen* the trust, and the fixture must notice:

  A. Key on the name alone. This is the classic hole: a spammer posting as
     "Sara" inherits Sara's approval. The fixture asserts that the same name
     with a different address stays queued.
  B. Drop the moderation-keyword escape hatch. Then an address already in the
     database — one that got in before the word list existed — can never be
     held again, which is the case WordPress explicitly guards.
  C. Skip the name/email emptiness check. Both columns are NULL on rows, and a
     NULL comparison matches NULL, so this approves every nameless or
     address-less comment on the site.

Run:  python scripts/wp-parity/negative_test_previously_approved.py
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
FIXTURE = os.path.join(ROOT, ".p1-tests", "previously_approved_test.py")
SERVICE = os.path.join(
    ROOT, "backend", "app", "modules", "blog", "application", "comment_service.py"
)

SABOTAGES = [
    (
        "A: key on the name alone (the name-borrowing hole)",
        [("            query = query.where(BlogComment.author_name == name)",
          "            query = query.where(BlogComment.author_name == name)\n"
          "            query = select(BlogComment.id).where(\n"
          "                BlogComment.status == CommentStatus.APPROVED)")],
    ),
    (
        "B: drop the moderation-keyword escape hatch",
        [("        if keys and email in keys.lower():\n"
          '            logger.info("comment_previous_approval_overridden", author_email=email[:64])\n'
          "            return False",
          "        if False:  # sabotage: keyword escape hatch removed")],
    ),
    (
        "C: stop requiring both a name and an address",
        [("        if not name or not email:\n            return False",
          "        if False:  # sabotage: the NULL match is back")],
    ),
]


def run_fixture() -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, FIXTURE], capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=600,
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


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

    with open(SERVICE, encoding="utf-8") as fh:
        original = fh.read()

    for label, pairs in SABOTAGES:
        text = original
        for needle, replacement in pairs:
            if needle not in text:
                print(f"FAIL: anchor not found, sabotage not applied: {needle[:70]!r}")
                return 1
            text = text.replace(needle, replacement, 1)
        with open(SERVICE, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        try:
            rc_broken, out_broken = run_fixture()
        finally:
            with open(SERVICE, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(original)

        rc_after, out_after = run_fixture()
        if rc_after != 0:
            print(f"FAIL: {label} — the fixture did not pass again after restoring.")
            print(out_after.strip()[-900:])
            return 1
        if rc_broken == 0:
            print(f"FAIL: {label} still passed. The fixture cannot see it.")
            return 1

        caught = [ln.strip() for ln in out_broken.splitlines() if "GAPS" in ln]
        print(f"  {label} -> caught")
        for line in caught:
            print(f"      {line[:200]}")

    print("\nPASS: every widening of the trust was caught, and the fixture was "
          "green again after each restore.")
    return 0


if __name__ == "__main__":
    sys.exit(main())