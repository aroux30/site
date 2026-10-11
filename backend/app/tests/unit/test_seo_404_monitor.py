"""The 404 monitor: recording is best-effort, counting is exact.

Rank Math parity (owner request 2026-10-09). The service contract:
- `record_miss` never raises — a monitoring failure must not turn a 404
  into a 500.
- One row per path; a repeat hit increments `hit_count` (upsert), so the
  table answers "what is broken" instead of flooding with duplicates.
- Bounds: path 500 chars, referrer 500, UA 300 — anything longer is
  truncated, not rejected.
"""

from __future__ import annotations

import inspect
import uuid

import pytest


def test_record_miss_swallows_errors():
    """The recorder must not raise even when the DB layer explodes.

    Negative test: remove the try/except in `record_miss` and a broken
    session (below) raises out of it — the 404 route would answer 500.
    """
    from app.modules.seo.application.notfound_service import record_miss

    class _Boom:
        async def execute(self, *a, **k):
            raise RuntimeError("db down")

        async def commit(self):
            raise RuntimeError("db down")

        async def rollback(self):
            pass

    import asyncio

    asyncio.get_event_loop_policy().new_event_loop().run_until_complete(
        record_miss(_Boom(), "/broken", referrer=None, user_agent=None)
    )  # must not raise


def test_record_miss_truncates_to_column_widths():
    """Source check: every value is bounded before it reaches the column.

    Negative test: drop a `[:MAX_*]` slice and a long UA would make
    PostgreSQL reject the row (and the recorder would swallow it silently).
    """
    from app.modules.seo.application import notfound_service

    src = inspect.getsource(notfound_service.record_miss)
    assert "MAX_PATH" in src
    assert "MAX_REFERRER" in src
    assert "MAX_UA" in src


def test_upsert_uses_on_conflict():
    """Source check: the write is an upsert, not an insert.

    Negative test: swap `on_conflict_do_update` for a plain insert and the
    second hit to one path raises a unique violation (swallowed, so the
    counter silently stops growing — the exact failure a counter must not
    have).
    """
    from app.modules.seo.application import notfound_service

    src = inspect.getsource(notfound_service.record_miss)
    assert "on_conflict_do_update" in src
    assert "Seo404Log.hit_count + 1" in src


async def test_roundtrip_record_and_summary():
    """Live DB: record a path twice, see one row with hit_count=2.

    Uses the shared test database; cleans up its own row.
    """
    from sqlalchemy import delete, select

    from app.core.database.session import async_session_factory, engine
    from app.modules.seo.application.notfound_service import record_miss, summary
    from app.modules.seo.domain.models import Seo404Log

    path = f"/pytest-404-{uuid.uuid4().hex[:8]}"
    async with async_session_factory() as db:
        try:
            await record_miss(db, path, referrer="https://example.com", user_agent="pytest")
            await record_miss(db, path, referrer=None, user_agent=None)
            row = (
                await db.execute(select(Seo404Log).where(Seo404Log.path == path))
            ).scalar_one()
            assert row.hit_count == 2
            # The latest hit's referrer replaces the old one (None here).
            assert row.referrer is None
            s = await summary(db)
            assert s["distinct_paths"] >= 1
        finally:
            await db.execute(delete(Seo404Log).where(Seo404Log.path == path))
            await db.commit()
    await engine.dispose()


def test_delete_route_uses_query_param_not_path():
    """The delete route must not be two path segments.

    `DELETE /admin/seo/{resource_type}/{resource_id}` is registered earlier
    and captures any two-segment path — `/admin/seo/404/<uuid>` was answered
    by the metadata handler (resource_type="404") and the row was never
    deleted, silently. The route is one segment + `miss_id` query.

    Negative test: change the path back to "/404/{miss_id}" and this fails.
    """
    from app.modules.seo.api import routes

    import inspect

    paths = {r.path: set(r.methods) for r in routes.admin_router.routes}
    # The DELETE must be a one-segment path. `/admin/seo/{resource_type}/
    # {resource_id}` (PUT + DELETE) is registered earlier and captures any
    # two-segment path whose second part parses as a UUID — the exact shape
    # a `DELETE /admin/seo/404/<uuid>` would have, and it would be answered
    # by the metadata handler instead.
    assert "/admin/seo/404" in paths
    assert "DELETE" in paths["/admin/seo/404"]

    # And the handler must read `miss_id` from the query string, which is
    # what makes the one-segment route carry the target row.
    src = inspect.getsource(routes.admin_delete_404)
    assert "Query" in src and "miss_id" in src
