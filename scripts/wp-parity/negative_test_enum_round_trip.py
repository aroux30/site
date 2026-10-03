"""Negative test for check_enum_round_trip: break a default and require a failure.

The gate is only worth running if it can go red. Reverting one column's default
to the lowercase *value* — the exact mistake it was written for — must fail it,
and the row it writes must then fail to read back through the ORM.

    python scripts/wp-parity/negative_test_enum_round_trip.py
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
GATE = os.path.join(HERE, "check_enum_round_trip.py")
MIGRATIONS = os.path.join(ROOT, "backend", "alembic", "versions")


def run_gate() -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, GATE],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def main() -> int:
    if not os.path.isfile(GATE):
        print(f"FAIL: gate missing at {GATE}")
        return 1

    rc, out = run_gate()
    if rc != 0:
        print("FAIL: the gate does not pass on the real code, so a failure "
              "below would prove nothing.")
        print(out.strip()[-600:])
        return 1

    # Break it the way it really broke: a column whose default writes the
    # enum *value* while the ORM reads the *name*. Applied to the database
    # rather than the model, because that is the half a model edit cannot fix.
    try:
        # The same DDL through the app's own engine, so the check runs
        # wherever the gate does — psql is not necessarily installed.
        driver = f"""
import asyncio, sys
sys.path.insert(0, {os.path.join(ROOT, 'backend')!r})
import app.main
from sqlalchemy import text
from app.core.database.session import _build_engine

async def run():
    e = _build_engine()
    async with e.begin() as c:
        await c.execute(text("ALTER TABLE cms_pages ALTER COLUMN visibility SET DEFAULT 'public'::character varying"))
        await c.execute(text("UPDATE cms_pages SET visibility = 'public' WHERE visibility = 'PUBLIC'"))
    await e.dispose()

asyncio.run(run())
"""
        result = subprocess.run(
            [sys.executable, "-c", driver],
            capture_output=True,
            text=True,
            timeout=180,
        )
        if result.returncode != 0:
            print("FAIL: could not apply the sabotage to the database.")
            print((result.stderr or "").strip()[-400:])
            return 1

        rc_broken, out_broken = run_gate()
    finally:
        restore = f"""
import asyncio, sys
sys.path.insert(0, {os.path.join(ROOT, 'backend')!r})
import app.main
from sqlalchemy import text
from app.core.database.session import _build_engine

async def run():
    e = _build_engine()
    async with e.begin() as c:
        await c.execute(text("UPDATE cms_pages SET visibility = 'PUBLIC' WHERE visibility = 'public'"))
        await c.execute(text("ALTER TABLE cms_pages ALTER COLUMN visibility SET DEFAULT 'PUBLIC'::character varying"))
    await e.dispose()

asyncio.run(run())
"""
        subprocess.run(
            [sys.executable, "-c", restore], capture_output=True, text=True, timeout=180
        )

    rc_after, _ = run_gate()
    if rc_after != 0:
        print("FAIL: the gate does not pass again after restoring — the "
              "sabotage was not cleaned up.")
        return 1

    if rc_broken == 0:
        print("FAIL: a lowercase default still passed. The gate cannot see the "
              "mistake it was written for.")
        return 1

    print("\nPASS: the gate went red on a lowercase default and green again "
          "once restored, so it is a real gate.")
    return 0


if __name__ == "__main__":
    sys.exit(main())