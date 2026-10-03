"""The uploaded-between date range, on both halves of a range that is easy to get wrong.

The filter is trivial to add and easy to make off by a day, which is the shape
of bug nobody notices: the operator asks for "this week" and gets everything
except the first morning, or everything plus next week. Both look like a working
filter.

So the boundaries are checked directly rather than by eyeballing a result:

  * `from` includes its own boundary instant and `to` includes its own. A
    half-open range drops the files uploaded at midnight, which is exactly when
    a nightly import runs and the files being hunted are.
  * an unset bound is not a bound. Passing `None` for `to` must not become
    "the beginning of time", which is what a naive `or` in the filter would do.
  * an inverted range returns nothing rather than everything. `from` after `to`
    is a mistake in the form, and answering it with the whole library is worse
    than answering it with nothing.

Options and rows go through the service's own writer, because the reader and
the writer both speak `site_options`.
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
from app.modules.media.application.media_service import MediaService
from app.modules.media.domain.models import MediaAsset
from app.modules.users.domain.models import User

TAG = "p1dates"
bad: list[str] = []


async def main() -> int:
    eng = _build_engine()
    Session = async_sessionmaker(eng, expire_on_commit=False)

    async with Session() as db:
        user = (await db.execute(
            select(User).where(User.is_superuser == True).limit(1))
        ).scalars().first()

        await db.execute(delete(MediaAsset).where(
            MediaAsset.file_name.like(TAG + "%")))
        await db.commit()

        def check(label, ok, detail=""):
            print(f"  {label}: {ok}")
            if not ok:
                bad.append(f"{label}: {detail}" if detail else label)

        # Four assets, one day apart, so a boundary that is off by anything at
        # all moves the result.
        #
        # The base is a fixed week in 2019 rather than "ten days ago": the
        # database is shared with every other live fixture on this machine, and
        # a recent window is full of their rows. The exact-set assertions below
        # then fail on other people's fixtures — a red gate for a reason that
        # has nothing to do with the filter. Nothing else writes 2019 rows.
        base = datetime(2019, 6, 3, 12, 0, 0, tzinfo=UTC)
        made = []
        for i in range(4):
            when = base + timedelta(days=i)
            a = MediaAsset(
                uploader_id=user.id,
                file_name=f"{TAG}-{i}-{uuid.uuid4().hex[:6]}.png",
                file_path=f"{TAG}/{i}.png",
                file_url=f"/uploads/{TAG}/{i}.png",
                file_size=1024, mime_type="image/png", width=100, height=100,
                created_at=when, updated_at=when,
            )
            db.add(a)
            made.append(a)
        await db.commit()
        ids = [a.id for a in made]

        async def only(*args, **kwargs):
            items, _ = await MediaService.list_assets(
                db, page_size=100, *args, **kwargs)
            return {a.id for a in items}

        def ours(got):
            """Intersect a result with this fixture's own rows.

            The database is shared with every other live fixture, so an
            unfiltered or loosely-bounded query legitimately returns their
            rows too. What this fixture is about is whether *our* four rows
            land inside or outside the range — the other rows are neither
            evidence for nor against.
            """
            return got & set(ids)

        # 1. a range covering the middle two returns exactly those two
        got = await only(created_from=base + timedelta(days=1),
                         created_to=base + timedelta(days=2))
        check("1. a range returns only what is inside it",
              ours(got) == set(ids[1:3]), f"{len(got)} rows")

        # 2. the boundaries are inclusive on both ends. A half-open range drops
        #    the first day's files, which is where a nightly import lands.
        got = await only(created_from=base + timedelta(days=1))
        check("2. 'from' includes its own boundary", ids[1] in got,
              "the boundary file was excluded")
        got = await only(created_to=base + timedelta(days=2))
        check("2b. 'to' includes its own boundary", ids[2] in got,
              "the boundary file was excluded")

        # 3. an unset bound is not a bound — no `to` means "everything after",
        #    not "everything".
        got = await only(created_from=base + timedelta(days=3))
        check("3. an unset 'to' means no upper bound",
              ours(got) == {ids[3]}, f"{len(got)} rows")

        got = await only(created_to=base)
        check("3b. an unset 'from' means no lower bound",
              ours(got) == {ids[0]}, f"{len(got)} rows")

        # 4. both unset means no date filtering at all
        got = await only()
        check("4. no bounds means no filtering", set(ids) <= got,
              f"{len(got)} rows")

        # 5. an inverted range returns nothing. Answering a backwards range with
        #    the whole library is the failure mode here, because it looks like
        #    the filter "did not apply".
        got = await only(created_from=base + timedelta(days=3),
                         created_to=base)
        check("5. an inverted range returns nothing",
              ours(got) == set(), f"{len(got)} rows")

        # 6. a range that matches nothing returns nothing, not everything
        got = await only(created_from=base + timedelta(days=90))
        check("6. a range past the end returns nothing", ours(got) == set(),
              f"{len(got)} rows")

        # 7. it composes with the other filters rather than replacing them.
        #    Attach one of our four to a post and ask for the unattached view
        #    over the same range: the attached one must drop out and the
        #    unattached ones must stay. (The original version detached an asset
        #    that was never attached and asserted about a different asset —
        #    it could not fail.)
        from app.modules.blog.domain.models import BlogPost

        post_id = (
            await db.execute(select(BlogPost.id).limit(1))
        ).scalars().first()
        if post_id is None:
            # Without a post to attach to, "composes with unattached" cannot
            # be tested at all. Report it instead of silently passing.
            check("7. it composes with the unattached filter", False,
                  "no blog post exists to attach to")
        else:
            await MediaService.attach_to_post(db, ids[0], post_id)
            got = await only(created_from=base,
                             created_to=base + timedelta(days=3),
                             unattached=True)
            check("7. it composes with the unattached filter",
                  ids[0] not in got and ids[1] in got,
                  f"{len(got)} rows")
            # Put it back so the rest of the fixture sees a clean state.
            await MediaService.attach_to_post(db, ids[0], None)

        # 8. through the endpoint, so the query string is parsed as the client
        #    sends it rather than as Python passes it.
        from httpx import ASGITransport, AsyncClient
        from app.core.security.jwt import create_access_token

        token = create_access_token(
            str(user.id), {"roles": ["super_admin"], "permissions": ["*"]})
        iso = (base + timedelta(days=1)).isoformat()
        iso_to = (base + timedelta(days=2)).isoformat()
        async with AsyncClient(transport=ASGITransport(app=app.main.app),
                               base_url="http://test") as client:
            # `params=`, not an f-string: the offset in an ISO instant is
            # `+00:00`, and a raw `+` in a query string is decoded as a space,
            # so the server sees `2019-06-04T12:00:00 00:00` and answers 422.
            # That failure belongs to the test, not the endpoint.
            #
            # Both bounds, not just `from`: an open-ended range matches every
            # later row in the shared database, and if that set outgrows one
            # page our 2019 rows fall off it — the assertion then fails for
            # the page size, not the filter. Bounded to the 2019 window, the
            # only rows it can return are the fixture's own.
            r = await client.get(
                "/api/v1/media",
                params={"created_from": iso, "created_to": iso_to},
                headers={"Authorization": f"Bearer {token}"})
            check("8. the endpoint accepts the range",
                  r.status_code == 200, f"status {r.status_code}")
            if r.status_code == 200:
                # JSON gives strings; `ids` holds UUIDs. `uuid in {str}` is
                # always False, which read as "the filter did not work" while
                # the filter was working — compare in one type.
                names = {i["id"] for i in r.json()["items"]}
                check("8b. and it filters",
                      str(ids[1]) in names and str(ids[0]) not in names,
                      f"{len(names)} rows")

            anon = await client.get(
                "/api/v1/media", params={"created_from": iso})
            check("8c. an anonymous caller is still refused",
                  anon.status_code in (401, 403), f"status {anon.status_code}")

        await db.execute(delete(MediaAsset).where(
            MediaAsset.file_name.like(TAG + "%")))
        await db.commit()

    await eng.dispose()
    if bad:
        print("\nDATE-FILTER GAPS:")
        for b in bad:
            print(f"  {b}")
        raise SystemExit(1)
    print("\nPASS: the date range is inclusive on both ends, treats a missing "
          "bound as no bound, and answers a backwards range with nothing.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))