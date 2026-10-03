"""Live check: the cms_page comment gate, and that opting in flips it.

Gap: docs/store-relevant-cms-gaps-2026-10-01.md, P0 "کامنت: دیدگاه روی صفحات
CMS". The backend accepted comments on a page resource, but `CmsPage` had no
column to say whether a given page wanted them — so any published page took a
thread whether its editor wanted one or not.

This runs against the real database on purpose. A unit test with a mocked
session would pass even if the migration had never created the column, which is
exactly the class of bug this gap list keeps turning up: a field that exists in
a schema, a model and a form, and nowhere else.

    cd backend && PYTHONPATH=. python scripts/verify_page_comment_gate.py
"""

from __future__ import annotations

import asyncio
import importlib
import io
import pkgutil
import sys
import uuid

# Windows consoles default to cp1252 and cannot print the Persian messages this
# script echoes, so a passing run would die with a UnicodeEncodeError that
# looks like a failure of the thing under test.
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# Import every model's module so SQLAlchemy can resolve string-based
# relationship targets; importing CommentService alone leaves UserRole unmapped
# and the first query dies with InvalidRequestError.
import app.modules as _modules

for _m in pkgutil.walk_packages(_modules.__path__, "app.modules."):
    try:
        importlib.import_module(_m.name)
    except Exception:  # noqa: BLE001 - a module that cannot import is not our subject
        pass

from app.core.exceptions.handlers import NotFoundError, ValidationError  # noqa: E402
from app.modules.blog.application.comment_service import CommentService  # noqa: E402
from app.modules.content.domain.models import CmsPage  # noqa: E402


def _database_url() -> str:
    for line in open(".env", encoding="utf-8"):
        if line.startswith("DATABASE_URL="):
            return line.split("=", 1)[1].strip().strip("\"'")
    raise SystemExit("DATABASE_URL not found in .env")


async def main() -> int:
    engine = create_async_engine(_database_url())
    session = async_sessionmaker(engine, expire_on_commit=False)
    failures: list[str] = []

    async with session() as db:
        page_id = (
            await db.execute(
                text(
                    "SELECT id FROM cms_pages WHERE status='PUBLISHED' "
                    "ORDER BY created_at LIMIT 1"
                )
            )
        ).scalar()
        if page_id is None:
            print("SKIP: no published page to test the gate against.")
            print("      Create and publish a CMS page, then run this again.")
            await engine.dispose()
            return 0

        page = await db.get(CmsPage, uuid.UUID(str(page_id)))
        print("page: %s | allow_comments=%s" % (page.slug, page.allow_comments))
        svc = CommentService(db)

        # 1. The default must refuse. A page is a static document until its
        #    editor says otherwise.
        page.allow_comments = False
        await db.commit()
        try:
            await svc._ensure_page_accepts_comments(page.id)
            failures.append("a page with allow_comments=False still accepted a comment")
        except ValidationError as exc:
            print("PASS: refused while allow_comments is False -> %s" % exc)

        # 2. Opting in must open the gate, or the admin checkbox does nothing.
        page.allow_comments = True
        await db.commit()
        try:
            await svc._ensure_page_accepts_comments(page.id)
            print("PASS: opened once the editor opted the page in")
        except Exception as exc:  # noqa: BLE001
            failures.append("an opted-in page was still refused: %s: %s" % (type(exc).__name__, exc))

        # 3. A missing page must 404, never fall through the gate.
        try:
            await svc._ensure_page_accepts_comments(uuid.uuid4())
            failures.append("a page that does not exist passed the comment gate")
        except NotFoundError:
            print("PASS: a missing page 404s instead of passing the gate")

        page.allow_comments = False
        await db.commit()
        print("restored allow_comments=False")

    await engine.dispose()

    for f in failures:
        print("FAIL: %s" % f)
    if failures:
        return 1
    print("")
    print("PASS: the cms_page comment gate matches the column it is driven by.")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(asyncio.run(main()))
