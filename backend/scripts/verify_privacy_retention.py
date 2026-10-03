"""Live check: expired privacy exports are purged, and by the scheduler.

P0 "حریم خصوصی: حذف خودکار داده‌های منقضی". The admin route existed and worked;
nothing called it, so an export that was requested and never collected kept its
full payload forever — the one case the retention window exists for. Worse, the
purge compared the type column against the enum's *value* while this project
stores the member NAME, so it had matched nothing even when run by hand.

Each step gets its own session on purpose. The service commits its own work, so
the session that called it can keep serving a pre-purge snapshot; and the probe
rows must outlive the reads, or "the payload is gone" is satisfied by the cleanup
deleting the row instead of by the purge clearing it.

    cd backend && PYTHONPATH=. python scripts/verify_privacy_retention.py
"""

from __future__ import annotations

import asyncio
import importlib
import io
import pkgutil
import sys
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import app.modules as _modules

for _m in pkgutil.walk_packages(_modules.__path__, "app.modules."):
    try:
        importlib.import_module(_m.name)
    except Exception:  # noqa: BLE001
        pass

from app.core.exceptions.handlers import NotFoundError, ValidationError
from app.modules.settings.application.privacy_request_service import (  # noqa: E402
    PrivacyRequestService,
)

TASK = "app.modules.settings.application.tasks.purge_expired_privacy_results"


def _database_url() -> str:
    for line in open(".env", encoding="utf-8"):
        if line.startswith("DATABASE_URL="):
            return line.split("=", 1)[1].strip().strip("\"'")
    raise SystemExit("DATABASE_URL not found in .env")


async def _cleanup(session, subject_id: str, row_ids: tuple[str, ...]) -> None:
    async with session() as db:
        await db.rollback()
        for rid in row_ids:
            await db.execute(
                text("DELETE FROM privacy_requests WHERE id = :id"), {"id": rid}
            )
        await db.execute(
            text("DELETE FROM users WHERE id = :uid"), {"uid": str(subject_id)}
        )
        await db.commit()
    print("removed the probe rows")


async def main() -> int:
    engine = create_async_engine(_database_url())
    session = async_sessionmaker(engine, expire_on_commit=False)
    failures: list[str] = []

    subject_id = uuid.uuid4()
    expired_id = str(uuid.uuid4())
    live_id = str(uuid.uuid4())
    untouched_id = str(uuid.uuid4())
    row_ids = (expired_id, live_id, untouched_id)
    now = datetime.now(timezone.utc)

    try:
        async with session() as db:
            columns = {
                r[0]
                for r in (
                    await db.execute(
                        text(
                            "SELECT column_name FROM information_schema.columns "
                            "WHERE table_name = 'privacy_requests'"
                        )
                    )
                ).fetchall()
            }
            required = {
                "id",
                "user_id",
                "type",
                "status",
                "created_at",
                "result_payload",
                "result_expires_at",
            }
            missing = required - columns
            if missing:
                print(
                    "SKIP: privacy_requests is missing %s — nothing to purge."
                    % ", ".join(sorted(missing))
                )
                return 0

            # Precondition, and an assertion in its own right: a payload left
            # by an earlier run would be swept by this run and counted as its own
            # work, which is exactly what hides whether the purge is selective.
            async with session() as pre:
                dirty = (
                    await pre.execute(
                        text(
                            "SELECT count(*) FROM privacy_requests "
                            "WHERE result_payload IS NOT NULL "
                            "AND result_expires_at IS NOT NULL "
                            "AND result_expires_at <= now()"
                        )
                    )
                ).scalar()
            if dirty:
                failures.append(
                    "%d expired payload(s) were already in the table before this "
                    "run, so the sweep would credit itself with someone else's "
                    "cleanup and its selectivity could not be measured" % dirty
                )

            # user_id is NOT NULL and carries a foreign key, so the subject has
            # to exist first. An insert that omits either poisons the whole
            # transaction, and every later statement then reports the aborted
            # transaction instead of the real cause.
            await db.execute(
                text(
                    "INSERT INTO users (id, phone, is_active, is_verified, "
                    "is_superuser, totp_enabled, created_at, updated_at) "
                    "VALUES (:uid, :phone, true, true, false, false, now(), now())"
                ),
                {"uid": str(subject_id), "phone": "9" + uuid.uuid4().hex[:9]},
            )
            for rid in row_ids:
                await db.execute(
                    text(
                        "INSERT INTO privacy_requests "
                        "(id, user_id, type, status, created_at) "
                        "VALUES (:id, :uid, 'EXPORT', 'COMPLETED', now())"
                    ),
                    {"id": rid, "uid": str(subject_id)},
                )
            # Past its window, well inside it, and a third inside it that
            # nothing touches: collecting an export is *supposed* to empty its
            # payload, so the selectivity check cannot reuse the row it collected
            # from -- by then it is empty for a completely different reason.
            for rid, expires in (
                (expired_id, now - timedelta(days=1)),
                (live_id, now + timedelta(days=30)),
                (untouched_id, now + timedelta(days=30)),
            ):
                await db.execute(
                    text(
                        "UPDATE privacy_requests SET result_payload = :p, "
                        "result_expires_at = :e WHERE id = :id"
                    ),
                    {"id": rid, "p": '{"probe":1}', "e": expires},
                )
            await db.commit()

        # Its own session, like the scheduler's. The service commits its work,
        # so a read through the session that called it can show state this
        # session never saw.
        async with session() as db:
            purged = await PrivacyRequestService.purge_expired(db)
        if purged < 1:
            failures.append(
                "the purge cleared %d row(s); the one past its expiry is still "
                "there" % purged
            )
        else:
            print("PASS: the purge ran and reported %d row(s)" % purged)

        # The second clearing path: a subject collecting their own export. This
        # one assigns through the ORM attribute rather than a bulk UPDATE, so it
        # exercises the column's type instead of the service's UPDATE, and the
        # two can fail independently — which they did.
        async with session() as db:
            try:
                await PrivacyRequestService.get_result(
                    db, user_id=subject_id, request_id=uuid.UUID(expired_id)
                )
                failures.append(
                    "reading an export past its expiry returned a payload instead "
                    "of refusing it"
                )
            except NotFoundError:
                print("PASS: an expired export cannot be collected")
            except ValidationError as exc:
                failures.append(
                    "collecting an expired export raised %r, which is a different "
                    "problem from the one being checked" % exc
                )

        # The on-read clear has to actually clear. `get_result` refuses an
        # expired export on its own check, so it never reaches the assignment
        # that empties the column -- which means the ORM path that writes JSON
        # null instead of SQL NULL would never be reached by the test above.
        # Clearing a live export is what exercises it, so do that instead.
        async with session() as db:
            try:
                await PrivacyRequestService.get_result(
                    db, user_id=subject_id, request_id=uuid.UUID(live_id)
                )
                print("PASS: a live export can be collected")
            except Exception as exc:  # noqa: BLE001
                failures.append(
                    "collecting an export inside its window raised %r, so a subject "
                    "cannot download their own data" % exc
                )

        async with session() as check_read:
            left_after_read = (
                await check_read.execute(
                    text(
                        "SELECT count(*) FROM privacy_requests "
                        "WHERE id = :id AND result_payload IS NOT NULL"
                    ),
                    {"id": live_id},
                )
            ).scalar()
        if left_after_read:
            failures.append(
                "the export kept its payload after the subject downloaded it, so "
                "the copy is never actually released"
            )
        else:
            print("PASS: collecting it releases the stored copy")

        # Still a third session, and before the cleanup: a probe deleted first
        # would make every read below pass for the wrong reason.
        async with session() as check:
            left_expired = (
                await check.execute(
                    text(
                        "SELECT count(*) FROM privacy_requests "
                        "WHERE id = :id AND result_payload IS NOT NULL"
                    ),
                    {"id": expired_id},
                )
            ).scalar()
            left_live = (
                await check.execute(
                    text(
                        "SELECT count(*) FROM privacy_requests "
                        "WHERE id = :id AND result_payload IS NOT NULL"
                    ),
                    {"id": untouched_id},
                )
            ).scalar()
            # Table-wide, not per-probe: the sweep is the whole point of the gap,
            # so an expired payload left anywhere after the purge means retention
            # is not reaching everything — the bug in a form one row never shows.
            stragglers = (
                await check.execute(
                    text(
                        "SELECT count(*) FROM privacy_requests "
                        "WHERE result_payload IS NOT NULL "
                        "AND result_expires_at IS NOT NULL "
                        "AND result_expires_at <= now()"
                    )
                )
            ).scalar()

        if left_expired:
            failures.append("the expired row still carries its payload")
        else:
            print("PASS: its payload is gone, not just counted")

        if not left_live:
            failures.append(
                "the purge deleted an export still inside its retention window, "
                "which is the opposite of what retention means"
            )
        else:
            print("PASS: an export inside its window is untouched")

        if stragglers:
            failures.append(
                "%d expired export payload(s) still sit in the table after the "
                "purge, so retention is not reaching everything" % stragglers
            )
        else:
            print("PASS: no expired payload is left anywhere in the table")

        # The purge only matters if something dispatches it.
        from app.worker.celery_app import celery_app

        # Finalize first, exactly as a worker start does: autodiscover runs
        # inside finalize(), so checking `tasks` before it reports everything as
        # unregistered — which reads as "nothing is scheduled" when in fact
        # everything is.
        celery_app.loader.import_default_modules()
        celery_app.finalize(auto=True)

        if TASK not in set(celery_app.tasks):
            failures.append("the purge task is not registered, so nothing dispatches it")
        else:
            scheduled = {
                e.get("task")
                for e in (celery_app.conf.beat_schedule or {}).values()
                if isinstance(e, dict)
            }
            if TASK not in scheduled:
                failures.append(
                    "the purge is registered but never scheduled, so expired "
                    "payloads accumulate exactly as before"
                )
            else:
                print("PASS: the purge is registered and on the beat")
    finally:
        await _cleanup(session, subject_id, row_ids)
        await engine.dispose()

    for f in failures:
        print("FAIL: %s" % f)
    if failures:
        return 1
    print("")
    print("PASS: retention purges what has expired, keeps what has not, and runs.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
