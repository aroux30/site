"""A lock so two live checks cannot write the same tables at once.

Three sessions share this development database. A live check that inserts a
probe row, does its work and deletes it is fine on its own and wrong beside
another: two checks counting the same table see each other's rows, and the one
that finishes first deletes rows the other is still asserting on.

The failure looks like a product bug and is not one. ``check_publish_and_quickedit``
goes red on comment counts while a comment-writing check runs beside it, and
goes green alone — which is the hardest kind of report to act on, because the
first thing anyone tries is to "fix" the counting logic that was right all along.

So every live check in this directory takes this lock for the duration of its
run. It is an advisory lock on a *file*, not on the database:

  - a file lock is process-wide and needs no session, no table and no schema, so
    it cannot be defeated by a transaction that rolls back
  - a database advisory lock would be held by a session that dies mid-run and
    leaves the lock to time out rather than release
  - ``O_EXCL`` on a lock file is enough for the case that matters here, since
    two sessions are two processes on one machine

Waiting is the right behaviour rather than skipping: a skipped check reports as
"nothing to check", and this project's standing rule is that a gate which cannot
fail is not a gate. Waiting costs seconds; skipping costs the guarantee.

    PYTHONPATH=. python scripts/with_lock.py verify_comment_ip_retention.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

#: One lock for every live check, not one per table. Per-table would be faster
#: and worse: two checks on different tables still contend for the rows they
#: share through `users`, `audit_logs` and `site_options`, and a partial lock
#: gives the false sense that the remaining pair is safe.
LOCK_PATH = Path(os.environ.get("LIVE_CHECK_LOCK", Path(__file__).with_name(".live-checks.lock")))

#: Generous, because the hold is a whole check and some of them run migrations
#: and take their time. Past this, the lock is treated as stale — see below.
WAIT_SECONDS = 300


def _acquire() -> "object | None":
    """Take the lock, or return None if it is already held.

    The stale case is real rather than hypothetical: a session killed mid-check
    leaves the file behind, and without this every later check would wait five
    minutes and then fail — a self-inflicted denial of service on the very gates
    meant to catch problems.
    """
    while True:
        try:
            fd = os.open(LOCK_PATH, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode())
            return fd
        except FileExistsError:
            try:
                age = time.time() - LOCK_PATH.stat().st_mtime
            except FileNotFoundError:
                continue  # released between the two calls
            if age > WAIT_SECONDS:
                # Say so rather than removing it silently: two processes
                # deciding independently that a lock is stale is how two
                # processes end up holding it.
                print(
                    "warning: removing a live-check lock older than %ds; the "
                    "session that took it did not release it"
                    % WAIT_SECONDS,
                    file=sys.stderr,
                )
                try:
                    LOCK_PATH.unlink()
                except FileNotFoundError:
                    pass
                continue
            time.sleep(1)


def _release(fd: "object | None") -> None:
    if fd is None:
        return
    try:
        os.close(fd)  # type: ignore[arg-type]
    except OSError:
        pass
    try:
        LOCK_PATH.unlink()
    except FileNotFoundError:
        pass


def run(script: str) -> int:
    """Run one live check under the lock, and return its exit code."""
    here = Path(__file__).resolve().parent
    backend = here.parent
    # Two things, both learned by breaking them first. ``PYTHONPATH`` has to be
    # the backend root or ``import app`` fails, and the working directory has to
    # be the backend root too — every check in this directory opens ``.env`` by
    # relative path, and a check started from ``scripts/`` fails on that before
    # it runs a single assertion. Either mistake exits 1, which the runner
    # reports as a product failure rather than as a broken wrapper.
    env = {**os.environ, "PYTHONPATH": str(backend)}
    fd = _acquire()
    try:
        proc = subprocess.run(
            [sys.executable, script],
            cwd=str(backend),
            env=env,
        )
        return proc.returncode
    finally:
        _release(fd)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(
            "usage: with_lock.py <script.py>\n"
            "  Runs the named live check with the shared database lock held.",
            file=sys.stderr,
        )
        return 2
    target = argv[1]
    path = Path(target)
    if not path.is_absolute():
        path = Path(__file__).parent / target
    if not path.is_file():
        print("no such check: %s" % target, file=sys.stderr)
        return 2
    return run(str(path))


if __name__ == "__main__":
    sys.exit(main(sys.argv))
