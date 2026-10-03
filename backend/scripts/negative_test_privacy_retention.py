"""Negative test: the retention check can actually fail.

A verification script that only ever prints PASS is a gate that cannot fail, and
a gate that cannot fail is not a gate. This restores each defect the check exists
to catch, one at a time, and requires the check to go red for the stated reason.

Three independent defects, three different failure modes — which is the point:
a check that only noticed the first would be a check written against a bug, not
against a property.

    cd backend && PYTHONPATH=. python scripts/negative_test_privacy_retention.py
"""

from __future__ import annotations

import io
import os
import subprocess
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BACKEND = Path(__file__).resolve().parents[1]
CHECK = BACKEND / "scripts" / "verify_privacy_retention.py"
SERVICE = BACKEND / "app" / "modules" / "settings" / "application" / "privacy_request_service.py"
TASKS = BACKEND / "app" / "modules" / "settings" / "application" / "tasks.py"
MODELS = BACKEND / "app" / "modules" / "settings" / "domain" / "models.py"


def run_check() -> tuple[int, str]:
    # The child inherits this process's whole environment and only adds
    # PYTHONPATH: a hand-built env drops SystemRoot, and the Windows socket
    # layer then fails to load at import time -- which looks like a broken check
    # rather than a broken environment.
    env = {**os.environ, "PYTHONPATH": "."}
    proc = subprocess.run(
        [sys.executable, str(CHECK)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=BACKEND,
        env=env,
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
    # Each case is (name, edits, expected substring in the check's output), where
    # an edit is (file, original, broken) and all of a case's edits are applied
    # together.
    #
    # Two properties turned out to be unbreakable from the outside once the fix
    # landed, and that is worth recording rather than hiding:
    #
    #  - Comparing the type column by enum value instead of name used to be a
    #    real defect, but this column is VARCHAR and SQLAlchemy 2.x binds a
    #    str-Enum member through its *name* on both paths, so `.value` and
    #    `.name` produce the identical statement. Verified live: both match the
    #    same 3 rows. It cannot be reintroduced from this call site, so a case
    #    for it would only ever be decoration.
    #
    #  - The bulk UPDATE in purge_expired writes `null()` -- SQL's NULL, by
    #    definition. There is no way to express "the JSON value null" through
    #    that call, so the ORM half of the bug cannot come back on that path at
    #    all. Only get_result, which assigns the attribute, was ever able to
    #    reproduce it, and the case below removes the model wrapper to prove it.
    #
    # So the cases break what is actually reachable: the model wrapper, the
    # expiry comparison, and the scheduler wiring.
    cases: list[tuple[str, list[tuple[Path, str, str]], str]] = [
        (
            "the model lets a JSON null stand in for an empty column",
            [
                (
                    MODELS,
                    "    result_payload: Mapped[dict[str, Any] | None] = mapped_column(\n"
                    "        SqlNullOnNone, nullable=True\n"
                    "    )",
                    "    result_payload: Mapped[dict[str, Any] | None] = mapped_column(\n"
                    "        JSONB, nullable=True\n"
                    "    )",
                ),
            ],
            "never actually released",
        ),
        (
            "the expiry comparison is dropped, so nothing is ever swept",
            [
                (
                    SERVICE,
                    "PrivacyRequest.result_expires_at <= datetime.now(UTC),",
                    "PrivacyRequest.result_expires_at <= datetime.now(UTC) + timedelta(days=365),",
                ),
            ],
            "inside its retention window",
        ),
        (
            "the purge is registered under a name the beat does not dispatch",
            [
                (
                    TASKS,
                    'name="app.modules.settings.application.tasks.purge_expired_privacy_results",',
                    'name="app.modules.settings.application.tasks.purge_expired_results_v2",',
                ),
            ],
            "registered",
        ),
    ]

    failures: list[str] = []
    print("baseline (unbroken tree):")
    code, out = run_check()
    if code != 0:
        print(out)
        print("FAIL: the check does not pass on the unbroken tree, so a red run "
              "below would mean nothing")
        return 1
    print("  PASS as expected")
    print("")

    saved: dict[Path, str] = {}
    for name, edits, expected in cases:
        # Every edit of a case lands together and reverts together: half of a
        # two-line change (the call without the import it needs) is a
        # SyntaxError, which turns the case into a check on the parser rather
        # than on the behaviour.
        touched = {path for path, _, _ in edits}
        for path in touched:
            if path not in saved:
                saved[path] = path.read_text(encoding="utf-8")

        missing = [path.name for path, original, _ in edits if original not in saved[path]]
        if missing:
            failures.append(
                "%s: the marker to break is not in %s, so this case would prove "
                "nothing -- update it for the current source" % (name, ", ".join(missing))
            )
            continue

        for path, original, broken in edits:
            path.write_text(saved[path].replace(original, broken, 1), encoding="utf-8")
        try:
            code, out = run_check()
        finally:
            for path in touched:
                path.write_text(saved[path], encoding="utf-8")

        if code == 0:
            failures.append("%s: the check still passed" % name)
            print("  FAIL %s -- the check still passed" % name)
        elif expected not in out:
            failures.append(
                "%s: the check went red, but not for this reason -- expected %r "
                "in the output" % (name, expected)
            )
            print("  FAIL %s -- red for the wrong reason" % name)
            print("    " + out.strip().replace("\n", "\n    "))
        else:
            print("  PASS %s -> check went red for the right reason" % name)

    # Everything restored, and the tree is green again.
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
