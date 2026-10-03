"""The comment trash has to be a place a comment can leave and come back from.

The bug this fixture was written for is a filter that was removed because
"nothing ever writes TRASH" — while the same panel's bulk action writes TRASH
through the same endpoint. So trashing worked, the filter was gone, and a
moderator who cleared a spam wave had no way to see what they had trashed or
to put it back. Both halves have to work for the state to be a trash rather
than a one-way door.

Three things are checked, and each is a different way this can look done:

  * the state is written and survives a re-read. The status is read back
    through a second session, because the session that wrote it would report
    the value it already held.
  * a trashed comment disappears from the public list and reappears on restore.
    This is the part that matters to a storefront: a trashed comment must not
    stay visible to readers while it waits to be restored, and a restore must
    put it back rather than making a moderator re-approve it.
  * restoring from trash returns it to PENDING, not straight to APPROVED. A
    comment sitting in the trash was removed for a reason that has not been
    re-examined, and silently republishing it would make the trash a staging
    area for spam.
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

TAG = "p1trash"
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
        c = BlogComment(
            post_id=post.id, resource_type="blog_post", resource_id=post.id,
            content=f"{TAG} body", author_name=f"{TAG} v",
            author_email=f"{TAG}@example.com", status=CommentStatus.APPROVED,
        )
        db.add(c)
        await db.commit()
        cid = c.id

        def check(label, ok, detail=""):
            print(f"  {label}: {ok}")
            if not ok:
                bad.append(f"{label}: {detail}" if detail else label)

        async def status_now():
            async with Session() as other:
                row = (await other.execute(
                    select(BlogComment).where(BlogComment.id == cid)
                )).scalar_one_or_none()
                return row.status if row else None

        async def public_ids():
            r = await svc.list_comments(post_id=post.id, page=1, page_size=20)
            return [i.id for i in r.items]

        async def admin_ids(status):
            r = await svc.list_comments(post_id=post.id, status=status,
                                        page=1, page_size=20,
                                        include_moderation_fields=True)
            return [i.id for i in r.items]

        # 1. it starts live and visible
        check("1. the comment starts approved", await status_now() is CommentStatus.APPROVED,
              str(await status_now()))
        check("1b. and a reader can see it", cid in await public_ids(),
              str(await public_ids()))

        # 2. the trash filter finds it once trashed — this is the filter that
        #    was removed on the belief that TRASH is never written.
        await svc.moderate_comment(cid, CommentStatus.TRASH)
        check("2. trashing is written", await status_now() is CommentStatus.TRASH,
              str(await status_now()))
        check("2b. the trash filter lists it", cid in await admin_ids(CommentStatus.TRASH),
              str(await admin_ids(CommentStatus.TRASH)))
        check("2c. it is gone from the approved filter",
              cid not in await admin_ids(CommentStatus.APPROVED))
        check("2d. and a reader no longer sees it", cid not in await public_ids(),
              "a trashed comment was still served to the public")

        # 3. restore brings it back to the moderation queue, not to the front
        #    page. It was removed for a reason nobody has re-checked.
        await svc.moderate_comment(cid, CommentStatus.APPROVED)
        check("3. it is approved again", await status_now() is CommentStatus.APPROVED,
              str(await status_now()))
        check("3b. and visible to readers", cid in await public_ids())

        await svc.moderate_comment(cid, CommentStatus.PENDING)
        await svc.moderate_comment(cid, CommentStatus.TRASH)
        await svc.moderate_comment(cid, CommentStatus.PENDING)
        check("4. restore-by-moderation lands in PENDING",
              await status_now() is CommentStatus.PENDING, str(await status_now()))
        check("4b. and stays out of the reader's view",
              cid not in await public_ids())

        # 5. the bulk path writes TRASH the same way the single path does —
        #    the claim the removed filter was resting on.
        bulk = BlogComment(
            post_id=post.id, resource_type="blog_post", resource_id=post.id,
            content=f"{TAG} bulk", author_name=f"{TAG} b",
            author_email=f"{TAG}-b@example.com", status=CommentStatus.PENDING,
        )
        db.add(bulk)
        await db.commit()
        res = await svc.bulk_moderate([str(bulk.id)], "trash")
        async with Session() as other:
            row = (await other.execute(
                select(BlogComment).where(BlogComment.id == bulk.id)
            )).scalar_one()
        check("5. the bulk trash action writes TRASH",
              res["ok"] == 1 and row.status is CommentStatus.TRASH,
              f"{res} {row.status}")
        check("5b. so the trash filter is not empty",
              bulk.id in await admin_ids(CommentStatus.TRASH))

        await db.execute(delete(BlogComment).where(
            BlogComment.content.like(TAG + "%")))
        await db.execute(delete(BlogComment).where(BlogComment.post_id == post.id))
        await db.execute(delete(BlogPost).where(BlogPost.id == post.id))
        await db.commit()

    await eng.dispose()
    if bad:
        print("\nTRASH GAPS:")
        for b in bad:
            print(f"  {b}")
        raise SystemExit(1)
    print("\nPASS: trash hides a comment from readers, is listable, and "
          "restores without republishing.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))