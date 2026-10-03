"""Negative test: the comment-IP retention check can actually fail.

A verification script that only ever prints PASS is a gate that cannot fail, and
a gate that cannot fail is not a gate. This breaks each property the check
depends on, one at a time, and requires the check to go red for the stated
reason.

The v4/v6 pair is here because the bug is asymmetric: a v4-only implementation
looks correct on every v4 row and quietly leaves every v6 comment's address
exact. An IPv6 comment is one device, and its /64 is the block an ISP hands to
one customer — anonymizing v4 while leaving v6 intact is anonymizing only the
easier half of the commenters.

    cd backend && PYTHONPATH=. python scripts/negative_test_comment_ip_retention.py
"""

from __future__ import annotations

import io
import os
import subprocess
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BACKEND = Path(__file__).resolve().parents[1]
CHECK = BACKEND / "scripts" / "verify_comment_ip_retention.py"
ANON = BACKEND / "app" / "core" / "security" / "ip_anonymize.py"
SERVICE = (
    BACKEND
    / "app"
    / "modules"
    / "settings"
    / "application"
    / "comment_ip_retention_service.py"
)
TASKS = BACKEND / "app" / "modules" / "settings" / "application" / "tasks.py"

# (name, file, original, broken, expected substring in the check's output)
CASES: list[tuple[str, Path, str, str, str]] = [
    (
        "the sweep blanks the address instead of masking it",
        SERVICE,
        "                await db.execute(\n"
        "                    update(BlogComment)\n"
        "                    .where(BlogComment.id == row_id)\n"
        "                    .values(author_ip=masked)",
        "                await db.execute(\n"
        "                    update(BlogComment)\n"
        "                    .where(BlogComment.id == row_id)\n"
        "                    .values(author_ip=None)",
        "so is the network the flood check groups by",
    ),
    (
        "the age filter is dropped, so fresh comments are masked too",
        SERVICE,
        "                    BlogComment.created_at < cutoff,\n"
        "                )\n"
        "                .order_by(BlogComment.id)",
        "                )\n"
        "                .order_by(BlogComment.id)",
        "the moderator reading a fresh",
    ),
    (
        "the IPv6 branch is removed, so a v6 address is passed through",
        ANON,
        "    return _network_address(parsed)\n",
        "    return str(parsed)\n",
        "still reads",
    ),
    (
        "masking is not idempotent, so the sweep rewrites forever",
        ANON,
        "    prefix = V4_PREFIX_LEN if parsed.version == 4 else V6_PREFIX_LEN\n"
        "    return parsed == ipaddress.ip_network(f\"{parsed}/{prefix}\", strict=False).network_address",
        "    return False",
        "re-reads every row past",
    ),
    (
        "the mask is no longer scheduled",
        TASKS,
        'name="app.modules.settings.application.tasks.mask_expired_comment_ips",',
        'name="app.modules.settings.application.tasks.mask_ips_v2",',
        "registered",
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
    failures: list[str] = []
    saved: dict[Path, str] = {}
    try:
        return _run(saved, failures)
    finally:
        # The outermost restore, and the reason this function is split in two.
        # The per-case `finally` covers an exception raised by the *check*, but
        # a failure before the loop starts — the baseline run going red, an
        # interrupt, a missing marker — returns without ever entering it, and
        # left an injected task name on disk. That is how a broken test suite
        # becomes a broken tree: the next run then fails for a reason that has
        # nothing to do with the code it is testing.
        for path, original in saved.items():
            if path.read_text(encoding="utf-8") != original:
                path.write_text(original, encoding="utf-8")
                print("restored %s" % path.name)


def _run(saved: dict[Path, str], failures: list[str]) -> int:
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

    for name, path, original, broken, expected in CASES:
        if path not in saved:
            saved[path] = path.read_text(encoding="utf-8")
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
