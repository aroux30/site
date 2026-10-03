"""Negative test: the reassignment check can actually fail.

A verification script that only ever prints PASS is a gate that cannot fail, and
a gate that cannot fail is not a gate. This breaks each property the check
depends on, one at a time, and requires the check to go red for the stated
reason.

The two cases worth the trouble are the halves of the same feature pointing in
opposite directions:

  - dropping a content table from the discovery loses real work silently
  - admitting an action record (`order_status_history.changed_by`) moves it
    without anything failing, and puts a name on a refund that person never
    processed. Neither failure produces an error; one loses posts and the other
    falsifies an audit trail, and only the second is invisible.

    cd backend && PYTHONPATH=. python scripts/negative_test_content_reassignment.py
"""

from __future__ import annotations

import io
import os
import subprocess
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BACKEND = Path(__file__).resolve().parents[1]
CHECK = BACKEND / "scripts" / "verify_content_reassignment.py"
SERVICE = BACKEND / "app" / "users" / "application" / "reassign_service.py"
SERVICE = BACKEND / "app" / "modules" / "users" / "application" / "reassign_service.py"

# (name, file, original, broken, expected substring in the check's output)
CASES: list[tuple[str, Path, str, str, str]] = [
    (
        "a content table stops being discovered",
        SERVICE,
        '    "author_id",\n    "owner_id",',
        '    "owner_id",',
        "is not covered by the reassignment",
    ),
    (
        # An action column admitted as authorship. Nothing raises: the UPDATE
        # succeeds, the rows move, and the audit trail now names somebody who did
        # not do the thing. This is the half of the feature whose failure is
        # invisible, which is why it is a case at all.
        "an action record is admitted as authorship",
        SERVICE,
        '    "reviewer_id",\n    "approved_by_user",\n)',
        '    "reviewer_id",\n    "approved_by_user",\n    "changed_by",\n)',
        "reassigning it would put a name on an action",
    ),
    (
        # `lead_inquiries.owner_id` matches the `owner_id` fragment, so it is
        # reassigned — and a lead's owner is a conversion target an operator may
        # have assigned by hand. It is also the column whose loss is invisible:
        # no rows raise, the store keeps working, and a sale is quietly
        # re-attributed to somebody who never touched it. The exclusion is the
        # only thing preventing that, and nothing else in the codebase checks it.
        "a lead's owner column starts being reassigned",
        SERVICE,
        "        (\"lead_inquiries\", \"owner_id\"),\n",
        "        (\"lead_inquiries\", \"converted_user_id\"),\n",
        "reassigning it would put a name on an action",
    ),
    (
        "reassigning to oneself is allowed",
        SERVICE,
        '    if from_user_id == to_user_id:\n        raise ValueError(',
        "    if False:\n        raise ValueError(",
        "was allowed",
    ),
    (
        # The count has to be a real WHERE on the column. A constant-false query
        # returns zero for every table, which is what "this user owns nothing"
        # looks like — so the operator is shown an empty estate and nobody
        # bothers with a reassignment.
        "the pre-delete count is not filtered by the column",
        SERVICE,
        '            text("SELECT count(*) FROM {t} WHERE {c} = :u".format(t=col.table, c=col.column)),',
        '            text("SELECT count(*) FROM {t} WHERE {c} = :u".format(t=col.table, c="id")),',
        "the pre-delete count found",
    ),
    (
        "the heir is not verified, so content points at nothing",
        SERVICE,
        "    if from_user_id == to_user_id:",
        "    if False:",
        "was allowed",
    ),
]


def run_check() -> tuple[int, str]:
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
    for _, path, _, _, _ in CASES:
        if path not in saved:
            saved[path] = path.read_text(encoding="utf-8")

    try:
        return _run(saved)
    finally:
        # The outermost restore. Without it a run that exits before the loop —
        # the baseline going red, an interrupt, a stale marker — leaves an
        # injected defect on disk, and the next run fails for an unrelated reason.
        for path, original in saved.items():
            if path.read_text(encoding="utf-8") != original:
                path.write_text(original, encoding="utf-8")
                print("restored %s" % path.name)


def _run(saved: dict[Path, str]) -> int:
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
    for name, path, original, broken, expected in CASES:
        source = saved[path]
        if original not in source:
            failures.append(
                "%s: the marker to break is not in %s, so this case would prove "
                "nothing -- update it for the current source" % (name, path.name)
            )
            continue
        path.write_text(source.replace(original, broken, 1), encoding="utf-8")
        try:
            code, out = run_check()
        finally:
            path.write_text(source, encoding="utf-8")

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
        failures.append("the check is red again after restoring every file")
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