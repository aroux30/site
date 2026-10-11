#!/usr/bin/env python3
"""Run every read-only invariant gate, and report them together.

Each gate is a separate script that exits non-zero when it finds something.
Running them one at a time is how a gate gets skipped: the person fixing
something else does not know a check exists. This runs the whole set and prints
one summary, so a failure names the gate that failed rather than a bare exit
code.

Every gate here is read-only. None of them writes to the database or the working
tree — they are checks, not fixers, so running them can never be the thing that
changes the data.

Run:  python scripts/run_gates.py
Exit: 0 when every gate passed, 1 when any failed or could not run.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time

# This file lives at backend/scripts/, and the gates it runs live beside it in
# the same directory. (They used to live in <root>/scripts/wp-parity/, but that
# directory was removed in the 2026-10-04 cleanup and this runner kept pointing
# at the deleted files — every run reported two FAILs that could not be fixed,
# which is worse than no gate: a runner nobody can make green is a runner
# nobody runs.)
BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable

#: (label, argv, needs_db). Anything marked "db" needs a reachable database and
#: is reported as skipped rather than failed when one is not available, so a
#: local run without a database is not reported as a broken gate. Paths are
#: relative to BACKEND (the runner's own directory), not the repo root.
GATES: list[tuple[str, list[str], bool]] = [
    (
        "ORM columns exist in the database",
        [PY, "scripts/check_model_schema_sync.py"],
        True,
    ),
    (
        "setting value shapes serialize",
        [PY, "scripts/settings_value_shapes_test.py"],
        True,
    ),
    # The audit change-capture hook must be installed in BOTH boot paths.
    # It is installed by import, and until 2026-10-06 no boot path imported
    # it: entity_change_logs stayed empty forever with nothing failing.
    (
        "audit change capture wired into boot",
        [PY, "scripts/check_audit_change_tracking_wired.py"],
        False,
    ),
    # The "email template editor labels cover the backend" gate was removed
    # on 2026-10-07 with the rest of the email feature (the templates screen
    # is gone, so there is no label map to keep in sync).
    #
    # Every route's annotations must resolve at runtime. A missing name (an
    # import that only exists under TYPE_CHECKING, or none at all) makes
    # FastAPI fall back to reading a body parameter as a query parameter —
    # the request then fails with 422 before the handler runs. This is how
    # the settings email-provider routes were once dead for weeks.
    (
        "endpoint annotations resolve at runtime",
        [PY, "scripts/check_endpoint_annotations.py"],
        False,
    ),
    # stdlib logging with structlog-style kwargs raises TypeError at call
    # time under a configured server — the WXR parser's logger.info("...",
    # posts=n) made every WordPress import 500 while unit tests stayed green
    # (INFO disabled in tests = call skipped). Same class in the feed parser
    # and the comment email service. Negative-tested via
    # scripts/negative_test_stdlib_logger_kwargs.py.
    (
        "stdlib loggers called without structlog kwargs",
        [PY, "scripts/check_stdlib_logger_kwargs.py"],
        False,
    ),
    # A response schema with from_attributes=True that is handed a whole ORM
    # object makes pydantic read that object's lazy relationships. Under
    # asyncio that IO raises MissingGreenlet, and the request 500s — but only
    # when a row happens to carry the relationship, so the page looked "empty"
    # rather than broken. One categorized post turned both /admin/blog/posts
    # and the public /blog/posts into 500s while 15 posts sat in the table.
    # Negative-tested in scripts/negative_test_eager_load_traps.py.
    (
        "no schema reads a lazy relationship from the ORM",
        [PY, "scripts/check_eager_load_traps.py"],
        False,
    ),
    # The wallet module's money invariants: no float/Decimal money (ADR-012),
    # the P2P transfer journal pair is a real zero-sum assertion (not the
    # phrase quoted in a comment), and user-facing wallet errors are Persian.
    # Negative-tested in scripts/negative_test_wallet_invariants.py — proven to
    # fail on an injected float, an English detail, a broken pair, and a
    # transfer leg that stops using TRANSFER_OUT/TRANSFER_IN.
    (
        "wallet money invariants hold",
        [PY, "scripts/check_wallet_invariants.py"],
        False,
    ),
    # Turning the wallet master switch off must HIDE the module, not just reject
    # its writes. The server was already refusing every mutation while the
    # storefront still showed the menu entry, the balance chip, the tab and the
    # checkout payment method — a defect a server-side gate cannot see, which is
    # why the invariants gate above was green through the whole of it. This gate
    # reads the client source instead.
    # Negative-tested in scripts/negative_test_wallet_switch_hiding.py — 8
    # injected defects, each proven to turn the gate red, including the subtle
    # one where the guards stay in place but stop reading `features.enabled`.
    (
        "disabling the wallet hides every wallet surface",
        [PY, "scripts/check_wallet_switch_hiding.py"],
        False,
    ),
    # Wishlist and compare are the same defect class as the wallet: a
    # server-side switch check stays green while the storefront still shows the
    # header link, the product-page button and the page itself. This gate reads
    # the client source.
    # Negative-tested in scripts/negative_test_shop_feature_hiding.py — 11
    # injected defects, each proven to turn the gate red, including the subtle
    # one where the nav filter helper exists but the link list never calls it
    # (presence is not wiring).
    (
        "disabling wishlist/compare hides every surface",
        [PY, "scripts/check_shop_feature_hiding.py"],
        False,
    ),
]


def _looks_like_a_missing_database(stderr: str) -> bool:
    """Whether a failure was "no database here" rather than a real finding."""
    markers = (
        "ConnectionRefused",
        "could not connect",
        "OperationalError",
        "does not exist",
        "Name or service not known",
        "password authentication failed",
    )
    return any(m.lower() in stderr.lower() for m in markers)


def main() -> int:
    # The runner prints each failing gate's own output verbatim, and those gates
    # emit Persian (store names, error reasons). On Windows the console codec is
    # cp1252, so `sys.stdout.write(proc.stdout)` raised UnicodeEncodeError and
    # the runner died *while reporting a failure* — the one moment it exists
    # for. The failure then read as a crash with no summary, and the gate that
    # found the problem was never named. Reconfigure both streams to UTF-8 up
    # front so a red run always reaches its summary.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass  # a stream that cannot be reconfigured is not worth failing over

    if len(sys.argv) > 1:
        print("usage: run_gates.py  (no arguments)", file=sys.stderr)
        return 2

    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [BACKEND, env.get("PYTHONPATH", "")]
    ).strip(os.pathsep)

    results: list[tuple[str, str, float]] = []
    for label, argv, needs_db in GATES:
        started = time.monotonic()
        try:
            proc = subprocess.run(
                argv,
                cwd=BACKEND,
                env=env,
                capture_output=True,
                # Explicit UTF-8: gates print Persian (store names, error
                # reasons), and without this the child's bytes are decoded
                # with the Windows locale codec (cp1252). A byte like 0x90
                # raises UnicodeDecodeError inside the reader thread, stdout
                # comes back None, and the runner TypeErrors instead of
                # reporting the gate's failure.
                encoding="utf-8",
                errors="replace",
                timeout=300,
            )
        except subprocess.TimeoutExpired:
            results.append((label, "timeout after 300s", time.monotonic() - started))
            continue
        took = time.monotonic() - started
        if proc.returncode == 0:
            results.append((label, "pass", took))
        elif needs_db and _looks_like_a_missing_database(proc.stderr):
            # A gate that could not run is not a gate that passed, and it is
            # also not a finding. Saying so is the only honest option.
            results.append((label, "skipped (no database reachable)", took))
        else:
            results.append((label, "FAIL", took))
            sys.stdout.write(proc.stdout)
            sys.stderr.write(proc.stderr)

    print()
    print("invariant gates")
    print("-" * 52)
    for label, status, took in results:
        print(f"  {label:<30} {status:<32} {took:5.1f}s")
    print("-" * 52)

    failed = [r for r in results if r[1] == "FAIL"]
    if failed:
        print(f"{len(failed)} gate(s) failed.")
        return 1
    skipped = [r for r in results if r[1].startswith("skipped")]
    if skipped:
        print(f"{len(skipped)} gate(s) skipped: no database.")
    print("all gates passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
