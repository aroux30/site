"""Negative test: the guest-comment privacy check can actually fail.

A verification script that only ever prints PASS is a gate that cannot fail, and
a gate that cannot fail is not a gate. This restores the defect the check exists
to catch — the id-only comment query — one variant at a time, and requires the
check to go red for the stated reason.

Four variants rather than one, because the two halves of the request fail
differently and one of them fails differently again on a hard delete. A check
that only noticed the first would be a check written against a bug, not against
a property.

    cd backend && PYTHONPATH=. python scripts/negative_test_guest_comment_privacy.py
"""

from __future__ import annotations

import io
import os
import subprocess
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BACKEND = Path(__file__).resolve().parents[1]
CHECK = BACKEND / "scripts" / "verify_guest_comment_privacy.py"
SERVICE = (
    BACKEND / "app" / "modules" / "settings" / "application" / "privacy_service.py"
)

# (name, original, broken, expected substring in the check's output).
# A broken variant must NOT contain the marker it replaces, or a check that
# greps for the marker still passes on the broken file.
CASES: list[tuple[str, str, str, str]] = [
    (
        "the subject-matching helper is gone, so guest comments are invisible again",
        "    conditions = (\n"
        "        [BlogComment.author_id == author_id, BlogComment.author_email.ilike(email)]\n"
        "        if email\n"
        "        else [BlogComment.author_id == author_id]\n"
        "    )",
        "    conditions = [BlogComment.author_id == author_id]",
        "omits the subject's guest comment",
    ),
    (
        "the match goes back to being case-sensitive",
        "BlogComment.author_email.ilike(email)",
        "BlogComment.author_email == email",
        # The account stores the address as typed and the comment form lowercases
        # it, so an equality test finds nothing for a subject who is obviously the
        # author -- which is the real shape of this bug, not a hypothetical.
        "omits the subject's guest comment",
    ),
    (
        "anonymization stops clearing the email",
        # Two adjacent lines only. A four-line marker spans the explanatory
        # comment that sits between author_url and author_ip, so it stops
        # matching the moment that comment is reworded — and the case reports
        # "the marker is not in the source" for a file it never touched.
        "                    comment.author_email = None\n"
        "                    comment.author_url = None\n",
        "                    comment.author_url = None\n",
        "still readable on a public comment",
    ),
    (
        "the hard delete goes back to relying on the cascade",
        "            guest_pass_ok = True\n"
        "            try:\n"
        "                stmt = _comments_by_subject(user_id, user.email)",
        "            guest_pass_ok = True\n"
        "            try:\n"
        "                stmt = _comments_by_subject(user_id, None)",
        "the data outlives the deletion",
    ),
]


def run_check() -> tuple[int, str]:
    # The child inherits this process's whole environment and only adds
    # PYTHONPATH: a hand-built env drops SystemRoot, and the Windows socket
    # layer then fails to load at import time -- which looks like a broken check
    # rather than a broken environment.
    proc = subprocess.run(
        [sys.executable, str(CHECK)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=BACKEND,
        env={**os.environ, "PYTHONPATH": "."},
    )
    return proc.returncode, proc.stdout + proc.stderr


def main() -> int:
    saved: dict[Path, str] = {}
    try:
        return _run(saved)
    finally:
        # The outermost restore, and the reason this function is split in two.
        # The per-case `finally` covers an exception raised by the *check*, but a
        # failure before the loop starts -- the baseline run going red, an
        # interrupt, a missing marker -- returns without ever entering it, and
        # left an injected defect on disk. That is how a broken test suite becomes
        # a broken tree: the next run then fails for a reason that has nothing to
        # do with the code it is testing.
        for path, original in saved.items():
            if path.read_text(encoding="utf-8") != original:
                path.write_text(original, encoding="utf-8")
                print("restored %s" % path.name)


def _run(saved: dict[Path, str]) -> int:
    source = SERVICE.read_text(encoding="utf-8")

    print("baseline (unbroken tree):")
    code, out = run_check()
    if code != 0:
        print(out)
        print(
            "FAIL: the check does not pass on the unbroken tree, so a red run below "
            "would mean nothing"
        )
        return 1
    print("  PASS as expected")
    print("")

    failures: list[str] = []
    for name, original, broken, expected in CASES:
        if original not in source:
            failures.append(
                "%s: the marker to break is not in privacy_service.py, so this case "
                "would prove nothing -- update it for the current source" % name
            )
            continue
        SERVICE.write_text(source.replace(original, broken, 1), encoding="utf-8")
        try:
            code, out = run_check()
        finally:
            SERVICE.write_text(source, encoding="utf-8")

        if code == 0:
            failures.append("%s: the check still passed" % name)
            print("  FAIL %s -- the check still passed" % name)
        elif expected not in out:
            failures.append(
                "%s: the check went red, but not for this reason -- expected %r in "
                "the output" % (name, expected)
            )
            print("  FAIL %s -- red for the wrong reason" % name)
            print("    " + out.strip().replace("\n", "\n    "))
        else:
            print("  PASS %s -> check went red for the right reason" % name)

    code, out = run_check()
    if code != 0:
        print(out)
        failures.append("the check is red again after restoring the file")
    else:
        print("")
        print("PASS: the tree is green again after every injection was reverted.")

    if failures:
        print("")
        for f in failures:
            print("FAIL: %s" % f)
        return 1
    print("")
    print("PASS: every defect this check targets makes it go red, for its own reason.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
