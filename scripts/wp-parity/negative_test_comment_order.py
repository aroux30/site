"""Negative test for comment_order.

A sort setting is the easiest thing in this codebase to ship as decoration, so
the sabotages are the two ways that reads as done while doing nothing:

  A. Read the option and ignore it — the value is fetched, nothing raises, and
     the list comes back in whatever order the query already had.
  B. Reverse only the top level. The thread flips and its replies stay
     ascending, so the setting works on the first screen and not on the second
     — a fixture that only checks the first four rows passes.

And one that is not a sabotage at all but the failure the tiebreak exists to
prevent, checked by removing the `id` tiebreak: with comments written in the
same second, the database is free to return them in any order, and paging
through a thread then repeats or skips one.

Run:  python scripts/wp-parity/negative_test_comment_order.py
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
FIXTURE = os.path.join(ROOT, ".p1-tests", "comment_order_test.py")
SERVICE = os.path.join(
    ROOT, "backend", "app", "modules", "blog", "application", "comment_service.py"
)

SABOTAGES = [
    (
        "A: read comment_order and ignore it",
        [("        first = BlogComment.created_at.desc() if descending "
          "else BlogComment.created_at.asc()",
          "        first = BlogComment.created_at.asc()  # sabotage: read, then ignored")],
    ),
    (
        "B: reverse only the top level, not the replies",
        [("        stmt = stmt.order_by(*(await self._comment_order()))\n"
          "        replies = (await self.db.execute(stmt)).scalars().all()",
          "        stmt = stmt.order_by(BlogComment.created_at.asc())\n"
          "        # sabotage: replies keep the old hard-coded order\n"
          "        replies = (await self.db.execute(stmt)).scalars().all()")],
    ),
    (
        "C: drop the id tiebreak",
        [("        return [first, BlogComment.id.asc()]",
          "        return [first]  # sabotage: same-second rows are unordered")],
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

    print("\nPASS: the ordering is proven load-bearing at the list, the reply "
          "path, and the tiebreak.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
