"""Live check: a departing user's content can be handed to a successor.

P0 "کاربران: حذف کاربر با واگذاری محتوا". Seven columns point at ``users`` with
``ON DELETE SET NULL``, so deleting an employee left every post, page, comment and
reusable block they wrote attributed to nobody.

Three properties, and the middle one is the reason this is not a parameter on an
existing function:

  1. the columns are discovered from the schema, so a module added tomorrow is
     covered — a hand-written list would leave its ``author_id`` out
  2. authorship moves, and an *action* record does not. Pointing
     ``order_status_history.changed_by`` at the successor would put a name on a
     refund that person never processed, and that is a falsified audit trail
  3. the count is read *before* the move, so the audit records what the account
     actually held rather than a re-read of an emptied set

    cd backend && PYTHONPATH=. python scripts/verify_content_reassignment.py
"""

from __future__ import annotations

import asyncio
import importlib
import io
import pkgutil
import sys
import uuid
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import app.modules as _modules

for _m in pkgutil.walk_packages(_modules.__path__, "app.modules."):
    try:
        importlib.import_module(_m.name)
    except Exception:  # noqa: BLE001
        pass

from app.modules.users.application import reassign_service  # noqa: E402

#: Columns that must never move, whatever they are called. Every one records an
#: action or an assignment, not authorship; moving them rewrites history.
MUST_NOT_MOVE = (
    ("order_status_history", "changed_by"),
    ("warehouse_transfers", "created_by"),
    ("refunds", "processed_by"),
    ("journal_entries", "created_by"),
    ("lead_inquiries", "owner_id"),
    ("support_tickets", "assigned_to"),
)

#: The ones a store's content actually lives in. Named separately from
#: MUST_NOT_MOVE so a missing one fails differently: these are missing coverage,
#: those are falsified history.
SHOULD_MOVE = (
    ("blog_posts", "author_id"),
    ("cms_pages", "author_id"),
    ("blog_comments", "author_id"),
    ("reusable_blocks", "author_id"),
)


def _database_url() -> str:
    for line in open(".env", encoding="utf-8"):
        if line.startswith("DATABASE_URL="):
            return line.split("=", 1)[1].strip().strip("\"'")
    raise SystemExit("DATABASE_URL not found in .env")


async def _user(db, email: str | None = None) -> str:
    uid = str(uuid.uuid4())
    await db.execute(
        text(
            "INSERT INTO users (id, phone, email, password_hash, is_active, "
            "is_verified, is_superuser, totp_enabled, created_at, updated_at) "
            "VALUES (:u, :p, :e, 'x', true, true, false, false, now(), now())"
        ),
        {"u": uid, "p": "9" + uuid.uuid4().hex[:9], "e": email},
    )
    return uid


async def _post(db, author: str) -> str:
    pid = str(uuid.uuid4())
    await db.execute(
        text(
            "INSERT INTO blog_posts (id, author_id, title, slug, content, status, "
            "created_at, updated_at) VALUES (:i, :a, 'probe', :s, 'body', "
            "'PUBLISHED', now(), now())"
        ),
        {"i": pid, "a": author, "s": "reassign-probe-" + uuid.uuid4().hex[:8]},
    )
    return pid


async def main() -> int:
    engine = create_async_engine(_database_url())
    session = async_sessionmaker(engine, expire_on_commit=False)
    failures: list[str] = []
    created: list[str] = []

    try:
        async with session() as db:
            cols = {c.table for c in await reassign_service.discover_authored_columns(db)}

            # 1. Coverage of the tables that hold a store's content.
            for table, column in SHOULD_MOVE:
                if table not in cols:
                    failures.append(
                        "%s.%s is not covered by the reassignment, so content written "
                        "there would become ownerless on delete" % (table, column)
                    )
            if not any("reassign" in f or "not covered" in f for f in failures):
                print("PASS: every content table that holds an author is covered")

            # 2. And exclusion of the action records. This is the half that fails
            #    silently: nothing breaks, the content moves, and an audit trail
            #    that named the wrong person looks exactly like one that does not.
            excluded = set(reassign_service.NOT_AUTHORSHIP_COLUMNS)
            for table, column in MUST_NOT_MOVE:
                found = any(
                    c.table == table and c.column == column
                    for c in await reassign_service.discover_authored_columns(db)
                )
                if found:
                    failures.append(
                        "%s.%s records who did something, not who wrote something, and "
                        "reassigning it would put a name on an action that person never "
                        "performed" % (table, column)
                    )
                elif (table, column) not in excluded and not any(
                    f in column for f in ("changed_by", "created_by", "processed_by")
                ):
                    # Not excluded by name and not caught by the fragments, which
                    # means it is protected only by not matching. Worth saying.
                    failures.append(
                        "%s.%s is excluded by accident — its name matches no "
                        "authorship fragment, so renaming the column would silently "
                        "start reassigning it" % (table, column)
                    )
            if not any("reassigning it would" in f or "by accident" in f for f in failures):
                print("PASS: action records are never reassigned")

            # 3. The real thing: two accounts, some content, one delete.
            departing = await _user(db, "departing.%s@example.invalid" % uuid.uuid4().hex[:8])
            heir = await _user(db, "heir.%s@example.invalid" % uuid.uuid4().hex[:8])
            created += [f"users:{departing}", f"users:{heir}"]
            p1 = await _post(db, departing)
            p2 = await _post(db, departing)
            created.append(f"blog_posts:{p1}")
            created.append(f"blog_posts:{p2}")
            await db.commit()

            owned = await reassign_service.count_authored_content(
                db, user_id=uuid.UUID(departing)
            )
            posts_owned = owned.get("blog_posts.author_id", 0)
            if posts_owned != 2:
                failures.append(
                    "the pre-delete count found %d post(s), expected 2 — so the "
                    "number the operator is shown before deciding would be wrong"
                    % posts_owned
                )
            else:
                print("PASS: the pre-delete count sees what the account owns")

            moved = await reassign_service.reassign_authored_content(
                db, from_user_id=uuid.UUID(departing), to_user_id=uuid.UUID(heir)
            )
            await db.commit()
            if moved.get("blog_posts.author_id") != 2:
                failures.append(
                    "the reassignment moved %s post(s), expected 2"
                    % moved.get("blog_posts.author_id")
                )
            else:
                print("PASS: the content moves to the named heir")

            after = await reassign_service.count_authored_content(
                db, user_id=uuid.UUID(departing)
            )
            if after.get("blog_posts.author_id"):
                failures.append(
                    "the departing user still owns %d post(s) after the reassignment"
                    % after["blog_posts.author_id"]
                )
            else:
                print("PASS: the departing user owns nothing afterwards")

            heir_count = await reassign_service.count_authored_content(
                db, user_id=uuid.UUID(heir)
            )
            if heir_count.get("blog_posts.author_id") != 2:
                failures.append(
                    "the heir holds %s post(s), expected 2"
                    % heir_count.get("blog_posts.author_id")
                )

            # 4. Reassigning to oneself must be refused. It moves every row and
            #    reports nothing, and an operator who picked the same person twice
            #    would conclude the tool is broken.
            try:
                await reassign_service.reassign_authored_content(
                    db,
                    from_user_id=uuid.UUID(heir),
                    to_user_id=uuid.UUID(heir),
                )
                failures.append(
                    "reassigning to the departing user themselves was allowed; it "
                    "moves every row and reports nothing"
                )
            except ValueError:
                print("PASS: reassigning to oneself is refused")

            # 5. The FK says SET NULL but some of those columns are NOT NULL, so
            #    the delete fails instead of orphaning. Worth stating plainly:
            #    it is the difference between "content silently becomes
            #    ownerless" and "the operator gets an error and reassigns first",
            #    and the second is safer. The store's behaviour should be known
            #    rather than discovered during an incident.
            nullable = (
                await db.execute(
                    text(
                        "SELECT is_nullable FROM information_schema.columns "
                        "WHERE table_name = 'blog_posts' AND column_name = 'author_id'"
                    )
                )
            ).scalar()
            if nullable == "NO":
                print(
                    "NOTE: blog_posts.author_id is NOT NULL, so a hard delete without "
                    "reassignment fails rather than orphaning the post"
                )
    finally:
        async with session() as db:
            await db.rollback()
            # Posts first. `blog_posts.author_id` is NOT NULL, so deleting a user
            # whose posts were not reassigned raises here rather than nulling —
            # which is itself the finding: the FK says SET NULL but the column
            # refuses it, so a hard delete fails instead of silently orphaning.
            # The probe users are deleted only after their posts are gone.
            for item in created:
                kind, _, ident = item.partition(":")
                if kind == "blog_posts":
                    await db.execute(
                        text("DELETE FROM blog_posts WHERE id = :i"), {"i": ident}
                    )
            for item in created:
                kind, _, ident = item.partition(":")
                if kind == "users":
                    await db.execute(
                        text("DELETE FROM users WHERE id = :i"), {"i": ident}
                    )
            await db.commit()
        print("removed the probe rows")
        await engine.dispose()

    for f in failures:
        print("FAIL: %s" % f)
    if failures:
        return 1
    print("")
    print("PASS: content follows the departing user to a named heir, and only content.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))