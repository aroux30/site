"""List every column in the live database that could hold a media URL.

The media-usage warning needs to know where an image can be referenced from,
and the honest answer is the database's, not a list someone remembered: models
and migrations have drifted before in this project. Run from the repo root:

    python scripts/wp-parity/find_media_reference_columns.py
"""

from __future__ import annotations

import asyncio
import os
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PATTERNS = ("%image%", "%_url", "%avatar%", "%logo%", "%banner%", "%icon%")


def database_url() -> str:
    path = os.path.join(ROOT, "backend", ".env")
    for line in open(path, encoding="utf-8"):
        if line.startswith("DATABASE_URL="):
            return line.split("=", 1)[1].strip().strip("\"'")
    raise SystemExit("DATABASE_URL not found in backend/.env")


async def main() -> int:
    engine = create_async_engine(database_url())
    clause = " OR ".join("column_name ILIKE :p%d" % i for i in range(len(PATTERNS)))
    params = {"p%d" % i: p for i, p in enumerate(PATTERNS)}
    async with engine.connect() as c:
        rows = (
            await c.execute(
                text(
                    "SELECT table_name, column_name FROM information_schema.columns "
                    "WHERE table_schema = 'public' "
                    "AND data_type IN ('character varying', 'text', 'character') "
                    "AND (" + clause + ") ORDER BY table_name, column_name"
                ),
                params,
            )
        ).fetchall()
    await engine.dispose()

    for table, column in rows:
        print("%-36s %s" % (table, column))
    print("total: %d" % len(rows))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
