"""Negative test for the awaiting-mod count.

Two sabotages, each aimed at a way this feature can look finished and be
misleading:

  A. Count notes as well. The moderation list includes them, so a count copied
    from that list's total reports the moderator's own annotations as a
    moderation queue — and the number no longer matches what approving one does
    to it.
  B. Merge spam into the same bucket as pending. Then a spam wave reads as a
    backlog of comments waiting on a person, and the moderator triages the
    wrong thing.

Both are caught by the fixture comparing the count against what actually moved
in the database, rather than against a stored value.

Run:  python scripts/wp-parity/negative_test_pending_count.py
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
FIXTURE = os.path.join(ROOT, ".p1-tests", "pending_count_test.py")
SERVICE = os.path.join(
    ROOT, "backend", "app", "modules", "blog", "application", "comment_service.py"
)

SABOTAGES = [
    (
        "A: count notes as part of the moderation queue",
        [("                BlogComment.comment_type == COMMENT_TYPE_COMMENT,\n"
          "            )\n"
          "            .group_by(BlogComment.status)",
          "            )\n"
          "            .group_by(BlogComment.status)")],
    ),
    (
        "B: merge spam into the pending bucket",
        [('            "spam": int(counts.get(CommentStatus.SPAM, 0)),',
          '            "spam": int(counts.get(CommentStatus.SPAM, 0))\n'
          '            + int(counts.get(CommentStatus.PENDING, 0)),')],
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
            if text.count(needle) != 1:
                print(f"FAIL: anchor found {text.count(needle)} times, "
                      f"sabotage not applied: {needle[:60]!r}")
                return 1
            text = text.replace(needle, replacement, 1)
        with open(SERVICE, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
        try:
            rc_broken, out_broken = run_fixture()
        finally:
            with open(SERVICE, "w", encoding="utf-8", newline="") as fh:
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

    print("\nPASS: the count excludes notes and keeps spam in its own bucket.")
    return 0


if __name__ == "__main__":
    sys.exit(main())