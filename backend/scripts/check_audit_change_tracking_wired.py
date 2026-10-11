"""Read-only gate: the audit change-capture hook is wired into the boot paths.

Why this gate exists (2026-10-06): ``entity_change_logs`` held zero rows since
the day it was created. The capture module installs its SQLAlchemy flush
hooks at import — and no boot path imported it, so the hooks never ran in any
process. Nothing failed: the table was simply always empty, and the admin
"تاریخچه تغییرات فیلدها" tab showed its empty state forever.

Presence in a file is not wiring. This gate runs a fresh probe process for
each real boot path and asserts that merely importing the boot module pulls
the capture module in (which is what installs the listeners):

  app.main               — the API process (uvicorn imports this)
  app.worker.celery_app  — the worker process (celery -A imports this)

The probe must NOT import the capture module itself before the check —
doing so would install the hook and mask the bug. Only after the
sys.modules check does it import for the listener reference.

Read-only: no database, no writes. Exits non-zero when the wiring is broken.

    cd backend && PYTHONPATH=. python scripts/check_audit_change_tracking_wired.py
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent

#: Runs in a fresh interpreter. Checks, in order:
#:   1. importing BOOT_TARGET alone puts change_tracking in sys.modules
#:   2. the flush listeners are attached to the sync Session class
#:   3. the default tracked entities all registered
PROBE = r"""
import sys

MODULE = "app.modules.audit.application.change_tracking"
BOOT_TARGET = {boot_target!r}

try:
    __import__(BOOT_TARGET)
except Exception as exc:
    print(
        f"boot import failed: {{type(exc).__name__}}: {{exc}}",
        file=sys.stderr,
    )
    sys.exit(2)

if MODULE not in sys.modules:
    print(
        f"importing {{BOOT_TARGET}} did not import {{MODULE}} — "
        "the flush hook is never installed in this process",
        file=sys.stderr,
    )
    sys.exit(1)

from sqlalchemy import event
from sqlalchemy.orm import Session as SyncSession

from app.modules.audit.application import change_tracking as ct

if not event.contains(SyncSession, "after_flush", ct._after_flush):
    print("after_flush listener is not attached", file=sys.stderr)
    sys.exit(1)
if not event.contains(SyncSession, "before_flush", ct._before_flush):
    print("before_flush listener is not attached", file=sys.stderr)
    sys.exit(1)

missing = sorted(set(ct.TRACKED_ENTITIES) - set(ct.REGISTERED_ENTITIES))
if missing:
    print(f"tracked entities failed to register: {{missing}}", file=sys.stderr)
    sys.exit(1)

print(f"wired: {{len(ct.REGISTERED_ENTITIES)}} entities tracked")
"""


def _run_probe(boot_target: str) -> tuple[bool, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [str(BACKEND), env.get("PYTHONPATH", "")]
    ).strip(os.pathsep)
    proc = subprocess.run(
        [sys.executable, "-c", PROBE.format(boot_target=boot_target)],
        cwd=BACKEND,
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )
    output = (proc.stdout + proc.stderr).strip()
    return proc.returncode == 0, output


def main() -> int:
    failures: list[str] = []

    for boot_target in ("app.main", "app.worker.celery_app"):
        try:
            ok, output = _run_probe(boot_target)
        except subprocess.TimeoutExpired:
            failures.append(f"{boot_target}: probe timed out after 180s")
            continue
        if ok:
            print(f"  {boot_target:<24} wired — {output}")
        else:
            failures.append(f"{boot_target}: {output}")

    if failures:
        print("FAIL — audit change capture is not wired into boot:")
        for f in failures:
            print(f"  - {f}")
        return 1

    print("PASS — change capture is wired in both boot paths.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
