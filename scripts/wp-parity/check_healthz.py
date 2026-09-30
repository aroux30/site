"""Live test for /healthz (#83) — prove both branches, not just the happy path.

The bug was that /healthz returned a constant, so a container with Postgres
down reported healthy. The fix reports `degraded` in the body while keeping
200, because Docker's liveness check uses `curl -f` and must not restart every
worker on a database outage.

This test therefore asserts BOTH:
  1. database up   -> status == "ok", and 200
  2. database down -> status == "degraded", still 200 (liveness preserved)

A test that only covers (1) would pass against the original constant-returning
code, which is the exact bug. Run:
    python scripts/wp-parity/check_healthz.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
os.chdir(ROOT / "backend")


async def _call(app=None) -> tuple[int, dict]:
    import httpx

    from app.main import create_app

    target = app if app is not None else create_app()
    transport = httpx.ASGITransport(app=target)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.get("/healthz")
        return r.status_code, r.json()


def _healthz_cache_of(app) -> None:
    """Clear the liveness probe's cache on whichever app instance we are testing."""
    for r in app.routes:
        if getattr(r, "path", "") == "/healthz":
            ep = r.endpoint
            for cell in ep.__closure__ or ():
                if isinstance(cell.cell_contents, dict) and "payload" in cell.cell_contents:
                    cell.cell_contents.clear()


async def main() -> int:
    failures: list[str] = []

    # ── 1. database reachable ──────────────────────────────────────────────
    try:
        code, body = await _call()
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: /healthz raised on the happy path: {exc!r}")
        return 1

    print(f"[1/3] database up   -> HTTP {code}  {body}")
    if code != 200:
        failures.append(f"liveness must be 200 with a healthy database, got {code}")
    if body.get("status") != "ok":
        failures.append(f"expected status 'ok', got {body.get('status')!r}")

    # ── 2. database unreachable ────────────────────────────────────────────
    # `create_app()` does `from app.core.database.session import engine` and
    # closes over it, so the only faithful way to break the probe is to build a
    # whole app while the session module hands out a dead engine. Patching the
    # running app's closure is not possible from outside.
    import app.core.database.session as session_mod

    real_engine = session_mod.engine

    class _DeadEngine:
        def connect(self):  # noqa: ANN201
            raise RuntimeError("simulated database outage")

    session_mod.engine = _DeadEngine()  # type: ignore[assignment]

    dead_app = None
    try:
        from app.main import create_app

        dead_app = create_app()
        code, body = await _call(dead_app)
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: /healthz raised during an outage: {exc!r}")
        return 1
    finally:
        session_mod.engine = real_engine

    print(f"[2/3] database down -> HTTP {code}  {body}")
    if body.get("status") != "degraded":
        failures.append(
            f"a database outage must report 'degraded', got {body.get('status')!r} "
            "— this is the original bug"
        )
    if code != 200:
        failures.append(
            f"liveness must stay 200 during a database outage, got {code} — "
            "Docker would restart every worker"
        )

    # ── 3. the cache must not pin a stale verdict ─────────────────────────
    # Same dead engine, called twice inside 10s: the second call is served from
    # the cache, so it must agree with the first rather than reverting to "ok".
    code2, body2 = await _call(dead_app)
    print(f"[3/3] outage, cached -> HTTP {code2}  {body2}")
    if body2.get("status") != "degraded":
        failures.append(
            f"a cached outage verdict must stay 'degraded', got "
            f"{body2.get('status')!r}"
        )

    # …and once the database is back, the verdict must recover.
    from app.main import create_app

    healthy_app = create_app()
    _healthz_cache_of(healthy_app)
    code3, body3 = await _call(healthy_app)
    print(f"[3b/3] recovered  -> HTTP {code3}  {body3}")
    if body3.get("status") != "ok":
        failures.append(
            f"status must recover to 'ok' once the database is back, got "
            f"{body3.get('status')!r} — a cached stale verdict"
        )

    if failures:
        print("\nFAIL:")
        for f in failures:
            print(f"  - {f}")
        return 1

    print("\nPASS: /healthz reports degraded on a real outage, stays 200, and recovers.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))