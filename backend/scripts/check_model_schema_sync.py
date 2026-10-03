"""Guard: a live migration must cover every column the ORM models declare.

This class of break is invisible until a request 500s: a column is added to a
model, the matching migration is not written, and every query that selects the
table dies with UndefinedColumnError. It happened twice in one day on this
project — once for `cms_pages.allow_comments`, once for
`media_assets.source_asset_id` — and both times the failure surfaced from an
unrelated-looking error ("this Session's transaction has been rolled back")
because the first statement to fail aborted everything after it.

So this compares the ORM's own metadata against information_schema, live, and
reports the difference. It needs no database writes and no fixtures.

    cd backend && PYTHONPATH=. python scripts/check_model_schema_sync.py
"""

from __future__ import annotations

import asyncio
import importlib
import io
import pkgutil
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import app.modules as _modules  # noqa: E402

for _m in pkgutil.walk_packages(_modules.__path__, "app.modules."):
    try:
        importlib.import_module(_m.name)
    except Exception:  # noqa: BLE001 - a module that cannot import is not our subject
        pass

from app.core.database.base import Base  # noqa: E402

# Tables whose schema is owned elsewhere. The outbox and the migration table
# are not ORM models, and comparing them would report every column as missing.
SKIP_TABLES = {"alembic_version"}


def _database_url() -> str:
    for line in open(".env", encoding="utf-8"):
        if line.startswith("DATABASE_URL="):
            return line.split("=", 1)[1].strip().strip("\"'")
    raise SystemExit("DATABASE_URL not found in .env")


async def main() -> int:
    engine = create_async_engine(_database_url())
    async with engine.connect() as conn:
        rows = (
            await conn.execute(
                text(
                    "SELECT table_name, column_name FROM information_schema.columns "
                    "WHERE table_schema = 'public'"
                )
            )
        ).fetchall()
    await engine.dispose()

    live: dict[str, set[str]] = {}
    for table, column in rows:
        live.setdefault(table, set()).add(column)

    missing: list[str] = []
    unknown_tables: list[str] = []

    for table, meta in sorted(Base.metadata.tables.items()):
        if table in SKIP_TABLES:
            continue
        if table not in live:
            # A model with no table: either unmigrated or a view. Either way the
            # ORM cannot read it, so it belongs in the report.
            unknown_tables.append(table)
            continue
        for column in meta.columns:
            if column.name not in live[table]:
                missing.append("%s.%s" % (table, column.name))

    for t in unknown_tables:
        print("FAIL: model %s has no table in the database" % t)
    for m in missing:
        print(
            "FAIL: %s is on the model but not in the database — write and apply "
            "its migration, or every query on that table 500s" % m
        )

    if missing or unknown_tables:
        print("")
        print(
            "%d column(s) and %d table(s) are out of sync. Until the migration "
            "lands, the whole module is down."
            % (len(missing), len(unknown_tables))
        )
        return 1

    print(
        "PASS: every ORM column exists in the database (%d tables checked)."
        % len(Base.metadata.tables)
    )
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))