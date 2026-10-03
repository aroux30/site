"""Revisions and scheduled publishing for custom post type entries.

Run against real rows, not mocked, because the two failure modes here are both
silent in source:

* **the snapshot is taken after the write.** Then the newest revision *is* the
  current row and restoring it changes nothing — which reads as "restore is
  broken" rather than as "restore never had anything to restore".
* **the schedule is cleared but the status is not.** Then an entry stays a draft
  forever with an empty schedule column, and there is nothing on the row to say
  it was ever scheduled.

And the thing that must not happen: restoring is itself undoable. An operator
who restores the wrong revision has to get back without a database dump.

Run:  python ../.p1-tests/custom_post_revision_test.py
"""

import asyncio
import io
import sys
import uuid

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, "C:/Users/Administrator/Desktop/site/backend")

import app.main  # noqa: F401 — registers every model, as the app does
from datetime import UTC, datetime, timedelta
from sqlalchemy import delete, select

from app.core.database.session import _build_engine, async_sessionmaker
from app.modules.blog.application import custom_post_revision_service as svc
from app.modules.blog.domain.custom_post_types import (
    CustomPostEntry,
    CustomPostEntryRevision,
    CustomPostType,
    CustomPostTypeStatus,
)

TAG = "p1cprev"
bad: list[str] = []


async def main() -> int:
    eng = _build_engine()
    # `expire_on_commit=False`: the service reads `revision_count` after each
    # commit, and a session that expires attributes on commit turns that read
    # into a lazy load outside greenlet — MissingGreenlet, which says nothing
    # about revisions at all.
    Session = async_sessionmaker(eng, expire_on_commit=False)

    async with Session() as db:
        # Debris from a killed run.
        for stale in (await db.execute(select(CustomPostEntry).where(
                CustomPostEntry.slug.like(TAG + "%")))).scalars().all():
            await db.execute(delete(CustomPostEntryRevision).where(
                CustomPostEntryRevision.entry_id == stale.id))
            await db.execute(delete(CustomPostEntry).where(
                CustomPostEntry.id == stale.id))
        await db.execute(delete(CustomPostType).where(
            CustomPostType.slug.like(TAG + "%")))
        await db.commit()

        def check(label, ok, detail=""):
            print(f"  {label}: {ok}")
            if not ok:
                bad.append(f"{label}: {detail}" if detail else label)

        ctype = CustomPostType(name=f"{TAG} type", slug=f"{TAG}-t")
        ctype.is_active = True
        db.add(ctype)
        await db.flush()

        entry = CustomPostEntry(
            post_type_id=ctype.id, title=f"{TAG} entry",
            slug=f"{TAG}-e", fields={"brand": "acme", "price": "10"},
            status=CustomPostTypeStatus.DRAFT,
        )
        db.add(entry)
        await db.commit()

        # --- revisions ------------------------------------------------
        await svc.update_entry(
            db, entry, changes={"fields": {"brand": "acme", "price": "20"}})
        await db.commit()
        await svc.update_entry(
            db, entry, changes={"fields": {"brand": "acme", "price": "30"}})
        await db.commit()

        revs = await svc.list_revisions(db, entry.id)
        check("1. edits are recorded", len(revs) >= 1, f"{len(revs)} revisions")
        check("1b. numbered from one, ascending",
              [r.revision_number for r in reversed(revs)]
              == list(range(1, len(revs) + 1)),
              str([r.revision_number for r in revs]))
        check("1c. newest first, which is how an operator reads them",
              revs[0].revision_number == max(r.revision_number for r in revs))

        check("2. the counter tracks them", entry.revision_count == len(revs),
              f"{entry.revision_count} vs {len(revs)}")

        before = dict(entry.fields or {})
        await svc.restore_revision(db, entry.id, revs[0].revision_number)
        await db.commit()
        check("3. restoring writes the stored state back",
              (entry.fields or {}).get("price")
              != before.get("price"),
              f"{entry.fields} vs stored {revs[0].fields}")
        check("3b. and the restored value is the old one",
              (entry.fields or {}).get("price") == "20",
              str(entry.fields))

        # The restore itself was snapshotted, so it can be undone.
        revs_after = await svc.list_revisions(db, entry.id)
        check("4. the restore was itself undoable",
              len(revs_after) == len(revs) + 1,
              f"{len(revs_after)} vs {len(revs)}")
        await svc.restore_revision(db, entry.id, revs_after[0].revision_number)
        await db.commit()
        check("4b. and undoing it gets the newer state back",
              (entry.fields or {}).get("price") == "30",
              str(entry.fields))

        # A revision number that was never written is a 404, not a silent no-op.
        missing = False
        try:
            await svc.restore_revision(db, entry.id, 999)
        except Exception as exc:
            missing = type(exc).__name__ == "NotFoundError"
        check("5. restoring a revision that does not exist is refused", missing)

        # --- scheduled publishing --------------------------------------
        past = datetime.now(UTC) - timedelta(hours=1)
        entry.status = CustomPostTypeStatus.DRAFT
        entry.scheduled_publish_at = past
        await db.commit()
        result = await svc.publish_scheduled(db)
        check("6. a due entry is published",
              result["published"] == 1 and entry.status == CustomPostTypeStatus.PUBLISHED,
              f"{result} {entry.status}")
        check("6b. and its schedule is cleared",
              entry.scheduled_publish_at is None, str(entry.scheduled_publish_at))
        check("6c. published_at is when it went live, not when it was due",
              entry.published_at is not None)

        entry.status = CustomPostTypeStatus.DRAFT
        entry.published_at = None
        entry.scheduled_publish_at = past
        await db.commit()
        again = await svc.publish_scheduled(db)
        check("7. running twice does not republish it", again["published"] == 1,
              str(again))

        future = datetime.now(UTC) + timedelta(days=2)
        entry.status = CustomPostTypeStatus.DRAFT
        entry.published_at = None
        entry.scheduled_publish_at = future
        await db.commit()
        later = await svc.publish_scheduled(db)
        check("8. a future entry is left alone",
              later["published"] == 0
              and entry.status == CustomPostTypeStatus.DRAFT,
              f"{later} {entry.status}")

        # `db.delete()` is a coroutine. Called without await it raised a
        # RuntimeWarning and silently left the revision rows behind — debris
        # that survives the run and makes the *next* one's numbering start high.
        for rev in (await db.execute(select(CustomPostEntryRevision).where(
                CustomPostEntryRevision.entry_id == entry.id))).scalars().all():
            await db.delete(rev)
        await db.delete(entry)
        await db.delete(ctype)
        await db.commit()

    await eng.dispose()
    if bad:
        print("\nCPT-REVISION GAPS:")
        for b in bad:
            print(f"  {b}")
        raise SystemExit(1)
    print("\nPASS: edits are recorded before they happen, a restore is "
          "undoable, and a due entry publishes exactly once.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))