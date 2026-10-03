"""Negative test for check_scheduled_tasks.py.

The guard's own docstring describes the failure it exists for: a beat entry for a
task the worker never registered, which reads like a working schedule and never
fires. That is invisible from the schedule itself, so the guard has to be shown
able to catch it.

    python scripts/wp-parity/negative_test_scheduled_tasks.py
"""

from __future__ import annotations

import sys as _sys
_sys.path.insert(0, __import__("os").path.dirname(__file__))
import console_safe  # noqa: F401  — makes stdout safe for non-ASCII

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GUARD = ROOT / "scripts" / "wp-parity" / "check_scheduled_tasks.py"
CELERY = ROOT / "backend" / "app" / "worker" / "celery_app.py"
TASKS = ROOT / "backend" / "app" / "modules" / "media" / "application" / "tasks.py"

BEAT_ENTRY = """    "purge-media-trash": {
        "task": "app.modules.media.application.tasks.purge_expired_media_trash",
        "schedule": crontab(hour=3, minute=20),
        "options": {"queue": "default"},
    },
"""

MODES = [
    (
        "a module dropped from autodiscover",
        CELERY,
        '        "app.modules.media",\n',
        "",
    ),
    (
        "a task decorator renamed away from its schedule",
        TASKS,
        'name="app.modules.media.application.tasks.purge_expired_media_trash"',
        'name="app.modules.media.tasks.purge_expired_media_trash"',
    ),
    (
        "the media purge's beat entry deleted",
        CELERY,
        BEAT_ENTRY,
        "",
    ),
]


def run() -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, str(GUARD)], capture_output=True, text=True, timeout=300
    )
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def main() -> int:
    originals = {p: p.read_text(encoding="utf-8") for p in (CELERY, TASKS)}

    def restore() -> None:
        for p, s in originals.items():
            p.write_text(s, encoding="utf-8")

    try:
        code, out = run()
        if code != 0:
            print("FAIL: the guard is red on the current tree, so a red result below "
                  "would prove nothing.\n%s" % out)
            return 2
        print("[0/%d] guard passes on the current tree" % (len(MODES) + 1))

        for i, (name, path, old, new) in enumerate(MODES, start=1):
            src = path.read_text(encoding="utf-8")
            if old not in src:
                print("FAIL: cannot inject %r — the snippet moved. Update this test." % name)
                restore()
                return 2
            path.write_text(src.replace(old, new, 1), encoding="utf-8")
            try:
                code, out = run()
            finally:
                path.write_text(src, encoding="utf-8")
            if code == 0:
                print("FAIL: guard passed while %s." % name)
                print(out)
                return 1
            print("[%d/%d] correctly fails on: %s" % (i, len(MODES) + 1, name))

        code, out = run()
        if code != 0:
            print("FAIL: guard still red after restore.\n%s" % out)
            return 1
        print("[%d/%d] guard is green again after restore" % (len(MODES) + 1, len(MODES) + 1))
    finally:
        restore()

    print("")
    print("PASS: the scheduled-task guard fails on all three ways a job stops running.")
    return 0


if __name__ == "__main__":
    sys.exit(main())