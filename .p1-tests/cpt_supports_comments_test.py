"""A custom post type's `supports_comments` must decide whether comments work.

The flag was stored, serialised into the API response, and never read. So the
admin checkbox did nothing: turning it on left the content type exactly as it
was, and an operator had no way to know which they were looking at.

The failure is silent in both directions, so both are checked:

  * on, and the comment is accepted — the case the checkbox promises;
  * off, and the comment is refused — the case where not consulting the flag
    would let anyone comment on a type the operator closed.

And the dispatch: before this, any resource type that was not a page fell
through to the blog-post branch and failed on a post id that does not exist.
So a comment on a CPT produced an error about the wrong thing, and the fixture
checks the error is about comments rather than about a missing post.
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
from app.modules.blog.domain.custom_post_types import CustomPostEntry, CustomPostType
from app.modules.blog.domain.models import BlogComment
from app.modules.blog.schemas.blog import BlogCommentCreate
from app.modules.users.domain.models import User

TAG = "p1supports"
bad: list[str] = []


async def main() -> int:
    eng = _build_engine()
    Session = async_sessionmaker(eng, expire_on_commit=False)

    async with Session() as db:
        user = (await db.execute(
            select(User).where(User.is_superuser == True).limit(1))
        ).scalars().first()

        slug = f"{TAG}-{uuid.uuid4().hex[:8]}"
        await db.execute(delete(CustomPostEntry).where(
            CustomPostEntry.slug.like(f"{TAG}%")))
        await db.execute(delete(CustomPostType).where(
            CustomPostType.slug == slug))
        await db.execute(delete(BlogComment).where(
            BlogComment.content.like(f"{TAG}%")))
        await db.commit()

        ctype = CustomPostType(
            name=f"{TAG} type", slug=slug,
            supports_comments=False, is_active=True,
        )
        db.add(ctype)
        await db.flush()

        entry = CustomPostEntry(
            post_type_id=ctype.id, title=f"{TAG} entry",
            slug=f"{slug}-e", status="published",
            fields={},
        )
        db.add(entry)
        await db.flush()

        svc = CommentService(db)

        def check(label, ok, detail=""):
            print(f"  {label}: {ok}")
            if not ok:
                bad.append(f"{label}: {detail}" if detail else label)

        def payload():
            return BlogCommentCreate(
                resource_type="content_entry", resource_id=entry.id,
                content=f"{TAG} body {uuid.uuid4().hex[:6]}",
                author_name=f"{TAG} v", author_email=f"{TAG}@example.com",
            )

        # 1. the flag off: the comment is refused
        refused = None
        try:
            await svc.create_comment(payload())
        except Exception as exc:
            refused = str(exc)
        check("1. comments off: refused", refused is not None)
        check("1b. and the reason is about comments, not a missing post",
              refused is not None and "دیدگاه" in refused,
              str(refused))

        # 2. the flag on: the comment goes through
        ctype.supports_comments = True
        await db.commit()
        made = await svc.create_comment(payload())
        check("2. comments on: accepted", made is not None)

        # 3. and turning it back off takes effect immediately — the flag is
        #    read per request, not cached at boot
        ctype.supports_comments = False
        await db.commit()
        refused2 = None
        try:
            await svc.create_comment(payload())
        except Exception as exc:
            refused2 = str(exc)
        check("3. turning it off again takes effect", refused2 is not None,
              str(refused2))

        await db.execute(delete(BlogComment).where(
            BlogComment.content.like(f"{TAG}%")))
        await db.execute(delete(CustomPostEntry).where(
            CustomPostEntry.id == entry.id))
        await db.execute(delete(CustomPostType).where(
            CustomPostType.id == ctype.id))
        await db.commit()

    await eng.dispose()
    if bad:
        print("\nSUPPORTS-COMMENTS GAPS:")
        for b in bad:
            print(f"  {b}")
        raise SystemExit(1)
    print("\nPASS: a content type's supports_comments flag decides whether "
          "comments are accepted, in both directions.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))