"""Negative test: the maintenance-mode check can actually fail.

A verification script that only ever prints PASS is a gate that cannot fail, and
a gate that cannot fail is not a gate. This breaks each property the check
depends on, one at a time, and requires the check to go red for the stated
reason.

The three worth the trouble are the failures that look like the feature working:

  - no self-expiry, so an operator who sets the flag and goes home leaves a store
    nobody can reach until they return
  - staff not exempt, so the same migration ends by being locked out of the panel
  - a corrupt flag honoured rather than ignored, which turns a database blip into
    a storefront-wide outage

The middle one is the most dangerous and the least likely to be tested: the
feature demonstrably works — the site goes down, the page appears — and it has
still made the situation worse.
"""

from __future__ import annotations

import io
import os
import subprocess
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BACKEND = Path(__file__).resolve().parents[1]
CHECK = BACKEND / "scripts" / "verify_maintenance_mode.py"
SERVICE = BACKEND / "app" / "modules" / "settings" / "application" / "maintenance_service.py"
MIDDLEWARE = BACKEND / "app" / "core" / "middleware" / "maintenance_middleware.py"
ROUTES = BACKEND / "app" / "modules" / "settings" / "api" / "routes.py"

# (name, file, original, broken, expected substring in the check's output)
CASES: list[tuple[str, Path, str, str, str]] = [
    (
        "the flag never lapses — an operator who goes home leaves a store down",
        SERVICE,
        "    if expires is None or expires <= datetime.now(UTC):",
        "    if False:",
        "still reads as active",
    ),
    (
        # Same shape as the exemption case: dropping the `active` key check alone
        # does nothing, because the expiry comparison below it rejects the value
        # anyway. What has to go is the expiry comparison itself, which is the
        # property the flag's safety rests on.
        "an elapsed flag is honoured because it carries a timestamp",
        SERVICE,
        "    if expires is None or expires <= datetime.now(UTC):",
        "    if False:",
        "still reads as active",
    ),
    (
        "a corrupt flag locks the store out",
        SERVICE,
        '        logger.warning("maintenance_flag_unreadable_treated_as_off")\n        return OFF',
        '        logger.warning("maintenance_flag_unreadable_treated_as_off")\n        return MaintenanceState(active=True, reason="maintenance")',
        "locks the store out",
    ),
    (
        # The whole predicate, not the superuser branch. On this store the
        # superuser also holds the admin role, so deleting the `is_superuser`
        # check changes nothing — the role branch below still lets them through,
        # and an injection that measures nothing is worse than no injection
        # because it reports coverage that is not there.
        "staff are no longer exempt at all",
        SERVICE,
        "    user = await db.get(User, user_id)\n    if user is None or not user.is_active:\n        return False",
        "    user = await db.get(User, user_id)\n    if user is None or not user.is_active:\n        return False\n    if True:\n        return False",
        "a superuser was blocked",
    ),
    (
        "an inactive staff account is let through",
        SERVICE,
        "    if user is None or not user.is_active:\n        return False",
        "    if user is None:\n        return False",
        "a deactivated staff account got through",
    ),
    (
        "health checks are blocked, so the instance is pulled and the flag cannot be cleared",
        SERVICE,
        '        or p.startswith("/api/v1/health")',
        '        or p.startswith("/api/v1/health_disabled_for_test")',
        "was blocked during maintenance",
    ),
    (
        "the gate answers 200, which every CDN caches",
        MIDDLEWARE,
        "            status_code=503,",
        "            status_code=200,",
        "rather than 503",
    ),
    (
        "the gate carries no Retry-After",
        MIDDLEWARE,
        '                "Retry-After": str(RETRY_AFTER_SECONDS),',
        "",
        "carries no Retry-After",
    ),
    (
        # The failure a module-level cache produces, written as code that
        # actually runs: the state is read once and then reused, so clearing the
        # flag changes nothing the gate can see. A real store keeps answering
        # 503 after the operator turns maintenance off — the outage the feature
        # was added to prevent, built out of the feature.
        "the flag is cached and never re-read",
        MIDDLEWARE,
        "                state = await get_state(db)",
        "                global _cached_state\n"
        "                _cached_state = globals().get('_cached_state') or await get_state(db)\n"
        "                state = _cached_state",
        "traffic is still blocked after the flag was cleared",
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
        # The outermost restore. This check writes the store's maintenance flag,
        # and an exit between "set" and "clear" leaves the whole storefront
        # answering 503 — the outage this feature exists to prevent, created by
        # the test for it.
        for path, original in saved.items():
            if path.read_text(encoding="utf-8") != original:
                path.write_text(original, encoding="utf-8")
                print("restored %s" % path.name)

    # The flag itself is restored by the check's own finally, which runs inside
    # the child process. This is only here for the case where that child could
    # not start at all.


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
