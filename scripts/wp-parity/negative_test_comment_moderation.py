"""Negative test for comment moderation: sabotage each guard and require a failure.

Four sabotages, each aimed at something that would otherwise be a quiet
regression:

  A. the public list stops withholding the address — the single worst outcome
  B. update_comment stops honouring model_fields_set, so an edit of the body
     also erases the author email
  C. bulk stops reporting per-comment outcomes, so a batch with one bad id
     reports a clean success
  D. trash deletes the row instead of flagging it, which is not recoverable

    python scripts/wp-parity/negative_test_comment_moderation.py
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
FIXTURE = os.path.join(ROOT, ".p1-tests", "comment_moderation_test.py")
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
                            f"moved and this test is now pointing at nothing")
            return
        patched = original.replace(old, new, 1)
        delta = sum(
            1 for a, b in zip(original.splitlines(), patched.splitlines())
            if a != b
        )
        print(f"  (sabotage {label.split(':')[0]} changed {delta} line(s))")
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

    # A. the public path stops withholding moderation fields
    sabotage(
        "A: the public list leaks the address",
        "        if moderation_fields:\n"
        "            return BlogCommentAdminResponse.model_validate(comment)",
        "        if True:  # sabotaged: public reads get the admin schema\n"
        "            return BlogCommentAdminResponse.model_validate(comment)",
    )

    # B. the update ignores which fields were actually sent
    sabotage(
        "B: an unrelated edit clears the author email",
        '        for field in ("author_name", "author_email", "author_url", "author_date"):\n'
        "            if field in data.model_fields_set:",
        '        for field in ("author_name", "author_email", "author_url", "author_date"):\n'
        "            if True:  # sabotaged: model_fields_set ignored",
    )

    # C. bulk stops counting the failures
    sabotage(
        "C: bulk hides a failed row",
        "                failed += 1\n"
        '                results.append({"id": str(cid), "ok": False, "error": str(exc)})',
        "                pass  # sabotaged: the failure is neither counted nor reported",
    )

    # D. trash deletes rather than flags
    sabotage(
        "D: trash deletes the row",
        '                if action == "delete":\n'
        "                    await self.db.delete(comment)\n"
        "                else:\n"
        "                    comment.status = target",
        '                if action in ("delete", "trash"):\n'
        "                    await self.db.delete(comment)\n"
        "                else:\n"
        "                    comment.status = target",
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
    print("\nPASS: all four sabotages were caught.")
    return 0


if __name__ == "__main__":
    sys.exit(main())