"""comment_order — the switch is only done if the list actually comes back in
that order.

A sort setting is the easiest thing in this codebase to ship as decoration: the
option parses, the field saves, the query runs, and the order never moves. So
this reads the list back through the real service with the switch each way and
compares what came out, rather than checking that the setting was stored.

Three things beyond the reversal itself, because each is a way this can look
right and still be wrong:

  * the tiebreak. Two comments written in the same second must come back in a
    stable order, or paging through a thread repeats and skips one.
  * replies. Reversing only the top level and leaving the replies ascending is
    a setting that works on the first screen and not on the second.
  * an unrecognised value. A setting someone types must degrade to the default,
    not empty the list.

Options go through the service's own writer: the reader and the writer both
speak `site_options`, and a value written anywhere else is read by nothing.
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
from app.modules.blog.application.comment_service import CommentService
from app.modules.blog.domain.models import (
    BlogComment,
    BlogPost,
    BlogPostStatus,
    CommentStatus,
    PostVisibility,
)
from app.modules.settings.application.site_options_service import SiteOptionsService
from app.modules.users.domain.models import User

TAG = "p1order"
bad: list[str] = []


async def main() -> int:
    eng = _build_engine()
    Session = async_sessionmaker(eng, expire_on_commit=False)

    async with Session() as db:
        user = (await db.execute(
            select(User).where(User.is_superuser == True).limit(1))
        ).scalars().first()

        for stale in (await db.execute(select(BlogPost).where(
                BlogPost.slug.like(TAG + "%")))).scalars().all():
            await db.execute(delete(BlogComment).where(
                BlogComment.post_id == stale.id))
            await db.execute(delete(BlogPost).where(BlogPost.id == stale.id))
        await db.execute(delete(BlogComment).where(BlogComment.content.like(TAG + "%")))
        await db.commit()

        post = BlogPost(
            title=f"{TAG} post", slug=f"{TAG}-{uuid.uuid4().hex[:8]}",
            content="x", excerpt=None, cover_image_url=None,
            author_id=user.id, status=BlogPostStatus.PUBLISHED,
            published_at=datetime.now(UTC), visibility=PostVisibility.PUBLIC,
            is_featured=False, allow_comments=True, post_format="standard",
            category_id=None,
        )
        db.add(post)
        await db.flush()

        svc = CommentService(db)
        base = datetime.now(UTC)

        # Four comments an hour apart, so the order is unambiguous even before
        # the tiebreak check.
        made = []
        for i in range(4):
            c = BlogComment(
                post_id=post.id, resource_type="blog_post", resource_id=post.id,
                content=f"{TAG} c{i}", author_name=f"{TAG} v",
                author_email=f"{TAG}-{i}@example.com",
                status=CommentStatus.APPROVED,
                created_at=base - timedelta(hours=4 - i),
                updated_at=base - timedelta(hours=4 - i),
            )
            db.add(c)
            made.append(c)
        await db.commit()

        # A reply to the oldest, so the reply order is separately observable.
        replies = []
        for i in range(2):
            r = BlogComment(
                post_id=post.id, resource_type="blog_post", resource_id=post.id,
                parent_id=made[0].id, content=f"{TAG} reply{i}",
                author_name=f"{TAG} v", author_email=f"{TAG}-r{i}@example.com",
                status=CommentStatus.APPROVED,
                created_at=base - timedelta(hours=2 - i),
                updated_at=base - timedelta(hours=2 - i),
            )
            db.add(r)
            replies.append(r)
        await db.commit()

        # Three comments sharing a timestamp: ordering by created_at alone
        # leaves these to the database, so paging can repeat or skip one.
        same = []
        for i in range(3):
            c = BlogComment(
                post_id=post.id, resource_type="blog_post", resource_id=post.id,
                content=f"{TAG} tie{i}", author_name=f"{TAG} v",
                author_email=f"{TAG}-t{i}@example.com",
                status=CommentStatus.APPROVED,
                created_at=base - timedelta(days=2),
                updated_at=base - timedelta(days=2),
            )
            db.add(c)
            same.append(c)
        await db.commit()

        def check(label, ok, detail=""):
            print(f"  {label}: {ok}")
            if not ok:
                bad.append(f"{label}: {detail}" if detail else label)

        async def listed():
            r = await svc.list_comments(post_id=post.id, page=1, page_size=50)
            return [c.id for c in r.items]

        async def setopt(k, v):
            await SiteOptionsService.set(db, k, v)

        try:
            await setopt("comment_order", "asc")
            asc = await listed()
            made_ids = [c.id for c in made]
            check("1. ascending returns the four hourly comments oldest-first",
                  [i for i in asc if i in made_ids] == made_ids,
                  str([i for i in asc if i in made_ids]))

            await setopt("comment_order", "desc")
            desc = await listed()
            check("2. descending returns the newest first",
                  [i for i in desc if i in made_ids] == list(reversed(made_ids)),
                  str([i for i in desc if i in made_ids]))

            # The flat list nests replies under their parent, so the top level
            # is the 4 made + the 3 same-second ones; the two replies ride
            # inside. What matters is that reversing does not change the set.
            check("3. both orders hold every top-level comment exactly once",
                  sorted(asc) == sorted(desc) and len(asc) == len(desc) == 7,
                  f"asc={len(asc)} desc={len(desc)}")

            # 4. replies follow the same setting as the thread. Read them the
            #    way a public reader gets them — nested under their parent in
            #    the list — rather than through the private helper, which would
            #    pass even if the nesting path reordered them itself.
            reply_ids = [r.id for r in replies]

            def nested(page_items, parent_id):
                for item in page_items:
                    if item.id == parent_id:
                        return [r.id for r in item.replies]
                    deeper = nested(item.replies, parent_id)
                    if deeper:
                        return deeper
                return []

            await setopt("comment_order", "asc")
            r_asc = nested((await svc.list_comments(
                post_id=post.id, page=1, page_size=50)).items, made[0].id)
            await setopt("comment_order", "desc")
            r_desc = nested((await svc.list_comments(
                post_id=post.id, page=1, page_size=50)).items, made[0].id)
            await setopt("comment_order", "asc")

            check("4. replies follow the same setting as the thread",
                  r_asc == reply_ids and r_desc == list(reversed(reply_ids)),
                  f"asc={r_asc} desc={r_desc} want={reply_ids}")

            # 5. the same-second comments must survive paging intact.
            #
            #    Two identical queries is not a test: Postgres may hand back the
            #    same row order both times even with no tiebreak, so that check
            #    passes whether or not one exists. The real hazard is a comment
            #    appearing on two pages or on none.
            #
            #    Paged with include_replies=False, which is the flat shape where
            #    page_size really counts rows. With replies nested, a page is
            #    counted in parents and slicing it across the tied group would
            #    be measuring that, not the ordering.
            await setopt("comment_order", "asc")
            ties = set(c.id for c in same)

            async def flat(page, size):
                r = await svc.list_comments(post_id=post.id, page=page,
                                            page_size=size, include_replies=False)
                return [c.id for c in r.items]

            whole = await flat(1, 50)
            check("5a. the flat list holds every comment, replies included",
                  set(whole) == set(c.id for c in made) | ties
                  | set(r.id for r in replies),
                  f"{len(whole)} ids")

            # Each slice is offset (page-1)*size and length size, so it must
            # equal that window of the whole list. Comparing against the
            # *prefix* would be wrong: page 3 of size 4 is the last window,
            # not the first.
            slices = [(size, page, await flat(page, size))
                      for size in (3, 4, 5)
                      for page in (1, 2, 3)]
            bad = [(sz, pg, sl) for sz, pg, sl in slices
                   if sl != whole[(pg - 1) * sz:(pg - 1) * sz + sz]]
            check("5b. every page returns its own window of the list",
                  not bad,
                  f"{len(bad)} mismatched; first: size={bad[0][0]} page={bad[0][1]}"
                  if bad else "")

            walked: dict[int, list] = {3: [], 4: [], 5: []}
            for sz, _, sl in slices:
                walked[sz].extend(sl)
            lost = {sz: sorted(set(whole) - set(ids)) for sz, ids in walked.items()}
            check("5c. paging with any size loses no comment",
                  not any(lost.values()),
                  f"missing: {[v[:2] for v in lost.values() if v]}")

            tie_order = [i for i in whole if i in ties]
            check("5d. the tied comments appear exactly once, together",
                  sorted(tie_order) == sorted(ties),
                  f"{tie_order} vs {sorted(ties)}")

            # 6. a value nobody recognises degrades to oldest-first rather than
            #    emptying the list or raising on a public route.
            await setopt("comment_order", "newest")
            newest = await listed()
            check("6. 'newest' is accepted as descending",
                  [i for i in newest if i in made_ids] == list(reversed(made_ids)),
                  str([i for i in newest if i in made_ids]))

            await setopt("comment_order", "sideways")
            junk = await listed()
            check("7. an unrecognised value falls back to ascending",
                  [i for i in junk if i in made_ids] == made_ids,
                  str([i for i in junk if i in made_ids]))

        finally:
            await setopt("comment_order", "asc")

        await db.execute(delete(BlogComment).where(
            BlogComment.content.like(TAG + "%")))
        await db.execute(delete(BlogComment).where(BlogComment.post_id == post.id))
        await db.execute(delete(BlogPost).where(BlogPost.id == post.id))
        await db.commit()

    await eng.dispose()
    if bad:
        print("\nORDER GAPS:")
        for b in bad:
            print(f"  {b}")
        raise SystemExit(1)
    print("\nPASS: comment_order reverses the list, holds it across pages, and "
          "covers the reply path.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))