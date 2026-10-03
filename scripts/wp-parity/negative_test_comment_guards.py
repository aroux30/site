"""Negative test for the comment guards: sabotage each and require a failure.

  A. require_name_email stops being enforced — the form-hint-without-a-guard
     case, where the option looks live and does nothing
  B. the rate ceilings stop counting existing comments, so the ceiling reads as
     "nothing recent" and never refuses
  C. the ceilings stop checking whether the option is off, so a site that set
     them to 0 cannot turn them off

    python scripts/wp-parity/negative_test_comment_guards.py
"""

from __future__ import annotations

import sys as _sys
_sys.path.insert(0, __import__("os").path.dirname(__file__))
import console_safe  # noqa: F401  — makes stdout safe for non-ASCII

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
FIXTURE = os.path.join(ROOT, ".p1-tests", "comment_guards_test.py")
SERVICE = os.path.join(
    ROOT, "backend", "app", "modules", "blog", "application", "comment_service.py"
)


def read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def run_fixture() -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, FIXTURE],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def main() -> int:
    for path in (FIXTURE, SERVICE):
        if not os.path.isfile(path):
            print(f"FAIL: missing {path}")
            return 1

    original = read(SERVICE)

    rc, out = run_fixture()
    if rc != 0:
        print("FAIL: the fixture does not pass on the real code, so a failure "
              "below would prove nothing.")
        print(out.strip()[-700:])
        return 1

    failures: list[str] = []

    def sabotage(label: str, old: str, new: str) -> None:
        if old not in original:
            failures.append(f"{label}: the sabotage matched nothing — the code "
                            f"moved and this test is pointing at nothing")
            return
        patched = original.replace(old, new, 1)
        with open(SERVICE, "w", encoding="utf-8") as fh:
            fh.write(patched)
        try:
            rc_s, _ = run_fixture()
        finally:
            with open(SERVICE, "w", encoding="utf-8") as fh:
                fh.write(original)
        if rc_s == 0:
            failures.append(f"{label}: the checks still passed")
        else:
            print(f"  {label}: caught (as it must be)")

    # A. the name/email requirement stops being checked
    sabotage(
        "A: require_name_email is not enforced",
        "        if author_id is None and await self._require_name_email_setting():",
        "        if False:  # sabotaged: the option is read but never applied",
    )

    # B. the ceiling stops counting what is already there
    sabotage(
        "B: the rate ceiling counts nothing",
        "            if recent >= limit:",
        "            if False:  # sabotaged: the count is ignored",
    )

    # C. a ceiling of 0 no longer disables the check
    sabotage(
        "C: a ceiling of 0 is ignored",
        "            if limit <= 0:\n                continue",
        "            pass  # sabotaged: 0 no longer disables",
    )

    rc_final, out_final = run_fixture()
    if rc_final != 0:
        print("FAIL: the fixture does not pass again after restoring the file — "
              "this test left the repository modified.")
        print(out_final.strip()[-700:])
        return 1

    if failures:
        for f in failures:
            print(f"FAIL: {f}")
        return 1
    print("\nPASS: all three sabotages were caught.")
    return 0


if __name__ == "__main__":
    sys.exit(main())