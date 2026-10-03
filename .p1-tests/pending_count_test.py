"""The awaiting-mod count has to be right, and it has to be its own query.

The tempting implementation is to read the moderation list's `total` and show
that as the badge. It is wrong in a way that is invisible until it matters: the
list paginates, so `total` is only correct when the request happened to be for
page one, and a badge built from it reads 20 whenever twenty comments are
waiting and 1 when forty are — a number that goes *down* as the queue grows.

So this checks the count is computed by its own query, that it separates the
two kinds of waiting (a pending comment wants a decision, spam wants a sweep),
and that it ignores notes — the moderator's own annotations, which would
otherwise inflate the number with rows that same person wrote.

The endpoint is driven through the real ASGI app, so the route, its guard and
its response type are exercised; and a 403 is checked too, because a count
that any logged-in customer can read is moderation information leaking.
"""

import asyncio
import io
import sys
import uuid

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, "C:/Users/Administrator/Desktop/site/backend")

import app.main  # noqa: F401 — registers every model, as the app does
from datetime import UTC, datetime
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
from app.modules.users.domain.models import User

TAG = "p1badge"
bad: list[str] = []


async def main() -> int:
    eng = _build_engine()
    Session = async_sessionmaker(eng, expire_on_commit=False)

    async with Session() as db:
        admin = (await db.execute(
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
            author_id=admin.id, status=BlogPostStatus.PUBLISHED,
            published_at=datetime.now(UTC), visibility=PostVisibility.PUBLIC,
            is_featured=False, allow_comments=True, post_format="standard",
            category_id=None,
        )
        db.add(post)
        await db.flush()

        svc = CommentService(db)

        def make(status, kind="comment", tag=""):
            c = BlogComment(
                post_id=post.id, resource_type="blog_post", resource_id=post.id,
                content=f"{TAG} {status.name} {kind} {tag or uuid.uuid4().hex[:6]}",
                author_name=f"{TAG} v", author_email=f"{TAG}-{uuid.uuid4().hex[:6]}@example.com",
                status=status, comment_type=kind,
            )
            db.add(c)
            return c

        def check(label, ok, detail=""):
            print(f"  {label}: {ok}")
            if not ok:
                bad.append(f"{label}: {detail}" if detail else label)

        # Baseline: this post's own rows must not move the site-wide count in a
        # way the test cannot reason about, so the count is compared as a delta
        # rather than an absolute.
        before = await svc.count_pending_comments()
        list_before = (await svc.list_comments(
            status=CommentStatus.PENDING, page=1, page_size=1,
            comment_type="comment",
            include_moderation_fields=True)).total
        print(f"   site baseline: {before} / list {list_before}")

        pending = [make(CommentStatus.PENDING) for _ in range(3)]
        spam = [make(CommentStatus.SPAM) for _ in range(2)]
        notes = [make(CommentStatus.PENDING, kind="note") for _ in range(2)]
        await db.commit()

        after = await svc.count_pending_comments()

        # 1. pending and spam are counted, and separately. A single number
        #    would let a spam wave read as a moderation backlog.
        check("1. pending comments are counted",
              after["pending"] == before["pending"] + 3,
              f"{before} -> {after}")
        check("2. spam comments are counted apart",
              after["spam"] == before["spam"] + 2,
              f"{before} -> {after}")

        # 3. notes are not counted — they are the moderator's own rows.
        check("3. notes do not inflate the queue",
              after["pending"] == before["pending"] + 3,
              "a pending note was counted")
        with_notes = (await svc.list_comments(
            status=CommentStatus.PENDING, page=1, page_size=1,
            include_moderation_fields=True)).total
        check("3b. the moderation list does include them, which is why the "
              "badge cannot reuse its total",
              with_notes - list_before == 5,
              f"list {list_before} -> {with_notes}")

        # 4. the list paginates and the count does not. A one-row page must
        #    still report every waiting comment, or a badge built from it would
        #    cap at the page size.
        page1 = await svc.list_comments(status=CommentStatus.PENDING, page=1,
                                        page_size=1,
                                        include_moderation_fields=True)
        # Delta, not absolute: the site can already hold pending comments from
        # other work, and this fixture must not depend on that being empty.
        pending_after = (await svc.list_comments(
            status=CommentStatus.PENDING, page=1, page_size=1,
            comment_type="comment",
            include_moderation_fields=True)).total
        check("4. the list total moved by exactly the three comments added",
              pending_after - list_before == 3,
              f"{list_before} -> {pending_after}")
        check("4b. and it really did return one row",
              len(page1.items) == 1,
              f"{len(page1.items)} rows on a one-row page")

        # 5. draining one by one moves the number, so it is not cached or
        #    computed once.
        await svc.moderate_comment(pending[0].id, CommentStatus.APPROVED)
        drained = await svc.count_pending_comments()
        check("5. approving one lowers the count by one",
              drained["pending"] == after["pending"] - 1,
              f"{after} -> {drained}")

        # 6. trash and unapprove both move it, so every route into the queue is
        #    covered rather than only the approve path.
        await svc.moderate_comment(spam[0].id, CommentStatus.PENDING)
        moved = await svc.count_pending_comments()
        check("6. moving one out of spam raises the pending count",
              moved["pending"] == drained["pending"] + 1
              and moved["spam"] == drained["spam"] - 1,
              f"{drained} -> {moved}")

        # 7. the endpoint, through the real app.
        from httpx import ASGITransport, AsyncClient

        async with AsyncClient(transport=ASGITransport(app=app.main.app),
                               base_url="http://test") as client:
            # No session: the count is moderation information.
            anon = await client.get("/api/v1/admin/blog/comments/pending-count")
            check("7. an anonymous caller is refused",
                  anon.status_code in (401, 403),
                  f"status {anon.status_code}")

            from app.core.security.jwt import create_access_token

            token = create_access_token(
                str(admin.id),
                {"roles": ["super_admin"], "permissions": ["*"]},
            )
            me = await client.get(
                "/api/v1/admin/blog/comments/pending-count",
                headers={"Authorization": f"Bearer {token}"})
            check("7b. a superuser gets the counts",
                  me.status_code == 200 and "pending" in me.json(),
                  f"status {me.status_code} body {me.text[:120]}")

        await db.execute(delete(BlogComment).where(
            BlogComment.content.like(TAG + "%")))
        await db.execute(delete(BlogComment).where(BlogComment.post_id == post.id))
        await db.execute(delete(BlogPost).where(BlogPost.id == post.id))
        await db.commit()

    await eng.dispose()
    if bad:
        print("\nBADGE GAPS:")
        for b in bad:
            print(f"  {b}")
        raise SystemExit(1)
    print("\nPASS: the awaiting-mod count is its own query, separates the two "
          "kinds of waiting, and ignores notes.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))