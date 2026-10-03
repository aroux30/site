#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run the whole migration chain against an empty schema and see whether it lands.

This is the only check in the repository that exercises a deployment. Every
other migration check — `alembic heads == current`, the revision graph, the
models' own schema sync — compares the one database everybody is looking at.
That database was migrated file by file over months and is healthy. A new
customer's database gets the chain applied in one pass, in an order the graph
does not show, and the two are different things.

Measured 2026-10-03, on the tree as it stood: `alembic upgrade head` against an
empty schema applied 94 migrations and then died with
`KeyError: 'f0a1b2c3d4e5'`. Three of the graph checks passed on that
same tree — the file was clean, the ids were unique, and alembic reported one
head. Nothing in the source could see it.

So the gate runs the chain. It uses `ALEMBIC_SCHEMA`, which `alembic/env.py`
already supports, rather than a scratch database: a schema inside the live
database needs no `CREATEDB` and is dropped with one statement. Two details
that are not optional:

* **the schema is created first.** `ALEMBIC_SCHEMA` sets `search_path` and does
  not create it, so pointing at a name that does not exist makes every
  `CREATE TABLE` fail with `no schema has been selected to create in` — a
  failure that looks like a broken migration and is not.
* **the schema name is unique per run.** A gate that always uses the same name
  collides with a concurrent run, and the two then interleave `upgrade head` and
  `DROP SCHEMA` into each other. The pid is in the name for that reason, and
  the drop is in a `finally` so a failed run leaves nothing behind.

**On reproducing the original failure — done, and the earlier doubt was
right to be recorded.** Five hand-built shapes were tried first (a merge naming
an already-consumed parent; the same across parallel branches; the same chained
onto the first merge; a four-parent merge; a tree with two heads) and only the
two-head shape aborted — so I recorded that the trigger was not established
rather than repeating the earlier claim. It is established now: the 04:43
backup, the tree as it stood before the merge fix, reproduces it exactly.
`alembic upgrade head` against an empty schema on that tree dies at
`k7m8n9p0p1q2` with `KeyError: 'f0a1b2c3d4e5'` after 94 migrations, and this
gate reports it as a failure with alembic's own output. The trigger is a merge
whose parent another merge on the same line already consumed; the shapes built
by hand did not reproduce it because they each introduced their own heads
rather than reproducing that line.

Needs a live PostgreSQL it may create schemas in. It writes nothing outside the
schema it makes and removes it on the way out, including on failure.

    python scripts/wp-parity/check_migration_chain_from_empty.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import console_safe  # noqa: F401  — idempotent; makes stdout safe for non-ASCII

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
BACKEND = os.path.join(ROOT, "backend")
PY = sys.executable

#: Long enough for 111 migrations on a developer machine, short enough that a
#: hung run is reported rather than waited on forever. The chain took ~40s when
#: it worked and the whole gate ~70s.
TIMEOUT_SECONDS = 900


def _run(argv: list[str], env: dict[str, str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        argv,
        cwd=BACKEND,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=TIMEOUT_SECONDS,
    )


def _database_url() -> str:
    """The application's own connection string, or the environment's.

    Read through the settings object rather than from `.env` so the gate uses
    exactly what alembic will use; a different database here would test a
    database nobody deploys.
    """
    sys.path.insert(0, BACKEND)
    try:
        from app.core.config.settings import get_settings

        url = get_settings().database_url_str
        # The application's URL carries SQLAlchemy's driver suffix
        # (`postgresql+asyncpg://`). Alembic wants it; asyncpg rejects it as an
        # unknown scheme. Both halves of this gate need the same string, so it is
        # normalised once here and the alembic half puts the suffix back.
        return url.replace("postgresql+asyncpg://", "postgresql://")
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(
            "FAIL: could not read the application's database URL (%s), so there "
            "is nothing to test against." % exc
        )


def _drop_schema(base_url: str, schema: str) -> None:
    """Remove the probe schema, whatever happened to it.

    `DROP SCHEMA ... CASCADE` because `alembic upgrade head` may have aborted
    halfway with tables already created; without CASCADE that drop fails on the
    objects and the next run inherits them.
    """
    env = dict(os.environ)
    env["PYTHONPATH"] = BACKEND + os.pathsep + env.get("PYTHONPATH", "")
    script = (
        "import asyncio, asyncpg, sys\n"
        "async def main():\n"
        "    c = await asyncpg.connect(sys.argv[1])\n"
        "    await c.execute('DROP SCHEMA IF EXISTS ' + sys.argv[2] + ' CASCADE')\n"
        "    await c.close()\n"
        "asyncio.run(main())\n"
    )
    subprocess.run(
        [PY, "-B", "-c", script, base_url, schema],
        cwd=BACKEND,
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )


def _create_schema(base_url: str, schema: str) -> None:
    _run_or_die(base_url, schema, "CREATE SCHEMA " + schema, "create")


def _run_or_die(base_url: str, schema: str, sql: str, what: str) -> None:
    env = dict(os.environ)
    env["PYTHONPATH"] = BACKEND + os.pathsep + env.get("PYTHONPATH", "")
    script = (
        "import asyncio, asyncpg, sys\n"
        "async def main():\n"
        "    c = await asyncpg.connect(sys.argv[1])\n"
        "    await c.execute(sys.argv[2])\n"
        "    await c.close()\n"
        "asyncio.run(main())\n"
    )
    proc = subprocess.run(
        [PY, "-B", "-c", script, base_url, sql],
        cwd=BACKEND,
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )
    if proc.returncode != 0:
        raise SystemExit(
            "FAIL: could not %s the probe schema %s.\n%s"
            % (what, schema, (proc.stderr or proc.stdout).strip()[-600:])
        )


def _table_counts(base_url: str, schema: str) -> tuple[int, int]:
    """(tables in the probe schema, tables in public)."""
    env = dict(os.environ)
    env["PYTHONPATH"] = BACKEND + os.pathsep + env.get("PYTHONPATH", "")
    script = (
        "import asyncio, asyncpg, sys\n"
        "async def main():\n"
        "    c = await asyncpg.connect(sys.argv[1])\n"
        "    q = \"select count(*) from information_schema.tables where table_schema = $1\"\n"
        "    probe = (await c.fetch(q, sys.argv[2]))[0]['count']\n"
        "    live = (await c.fetch(q, 'public'))[0]['count']\n"
        "    print(probe, live)\n"
        "    await c.close()\n"
        "asyncio.run(main())\n"
    )
    proc = subprocess.run(
        [PY, "-B", "-c", script, base_url, schema],
        cwd=BACKEND,
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )
    try:
        probe, live = proc.stdout.split()
        return int(probe), int(live)
    except ValueError:
        return -1, -1


def main() -> int:
    base_url = _database_url()
    # The pid keeps two concurrent runs off each other; `CREATE SCHEMA` on an
    # existing name fails loudly rather than quietly reusing someone else's.
    schema = "alembic_chain_probe_%d" % os.getpid()
    env = dict(os.environ)
    env["ALEMBIC_SCHEMA"] = schema
    # Back to the driver alembic and the app both speak. env.py sets the URL
    # from get_settings() itself, so this only matters for a subprocess that
    # would otherwise inherit the stripped form.
    env["DATABASE_URL"] = base_url.replace("postgresql://", "postgresql+asyncpg://")

    began = time.monotonic()
    _create_schema(base_url, schema)
    try:
        proc = _run([PY, "-B", "-m", "alembic", "upgrade", "head"], env)
        # Counted while the schema still exists. A count alone would be a weak
        # check — a chain that creates 20 of 194 tables and returns 0 also ends
        # here — so it is compared against the live schema, and the schema that
        # a customer would actually get is the one that matters.
        probe_tables, live_tables = _table_counts(base_url, schema)
    finally:
        # Dropped whatever happened: on success so the database is left as it was
        # found, on failure so the next run starts from nothing.
        _drop_schema(base_url, schema)

    if proc.returncode != 0:
        tail = [
            ln
            for ln in (proc.stdout + proc.stderr).splitlines()
            if ln.strip() and not ln.startswith("  ")
        ][-6:]
        print(
            "FAIL: `alembic upgrade head` against an empty schema exited %d "
            "after %.0fs." % (proc.returncode, time.monotonic() - began)
        )
        print("  A new deployment cannot reach this point, so this is not about")
        print("  the database you are looking at — it never applied these")
        print("  migrations in this order.")
        print()
        for line in tail:
            print("  " + line)
        return 1

    if probe_tables < 0:
        print(
            "FAIL: the chain applied in %.0fs but its schema could not be "
            "counted, so it is not established that a fresh database ends up "
            "with the tables the application reads."
            % (time.monotonic() - began)
        )
        return 1

    if probe_tables != live_tables:
        print(
            "FAIL: a fresh database gets %d tables, the live one has %d." % (
                probe_tables,
                live_tables,
            )
        )
        print("  The chain runs now, so this is a different failure from a broken")
        print("  one — and it is the failure nobody sees until a new customer")
        print("  signs up and a page queries a table that was never created.")
        return 1

    print(
        "PASS: the chain applies from empty in %.0fs and builds %d tables, "
        "matching the live schema." % (time.monotonic() - began, probe_tables)
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())