"""One-click moderation links — the moderator mail must actually be able to act.

A mail that *contains* an Approve link and a link that works are different
things, and the difference is invisible until somebody on a phone clicks it.
So this drives the whole path: mint a token, call the real endpoint through the
real app, and read the status back from the database.

Three failure shapes are covered, and each one has been a live bug somewhere in
this project's history:

  * a link that renders but does not act — the endpoint accepts the URL and
    quietly returns a page without changing anything.
  * a link that acts more than once — a GET that changes state is prefetched by
    mail clients, so a second hit must not re-apply or re-log.
  * a link that acts on the *wrong* thing — a token minted for approving must
    not work for trashing, and must not work on another comment. Without the
    binding, one leaked link is a general moderation capability.

Endpoint calls go through the ASGI app rather than the handler function, so the
route, its query-string parsing and its response type are all exercised. That
is the part a direct call would skip, and the part most likely to be wrong.
"""

import asyncio
import io
import sys
import time
import uuid
from datetime import UTC, datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, "C:/Users/Administrator/Desktop/site/backend")

import app.main  # noqa: F401 — registers every model, as the app does
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from app.core.database.session import _build_engine, async_sessionmaker
from app.modules.blog.application import comment_moderation_token as cmt
from app.modules.blog.domain.models import (
    BlogComment,
    BlogPost,
    BlogPostStatus,
    CommentStatus,
    PostVisibility,
)
from app.modules.users.domain.models import User

TAG = "p1act"
bad: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {label}: {ok}")
    if not ok:
        bad.append(f"{label}: {detail}" if detail else label)


async def main() -> int:
    eng = _build_engine()
    Session = async_sessionmaker(eng, expire_on_commit=False)

    async with Session() as db:
        user = (await db.execute(
            select(User).where(User.is_superuser == True).limit(1))
        ).scalars().first()

        # Debris from a killed run would make this one fail on a duplicate slug
        # instead of checking anything.
        for stale in (await db.execute(select(BlogPost).where(
                BlogPost.slug.like(TAG + "%")))).scalars().all():
            await db.execute(delete(BlogComment).where(
                BlogComment.post_id == stale.id))
            await db.execute(delete(BlogPost).where(BlogPost.id == stale.id))
        await db.execute(delete(BlogComment).where(BlogComment.content.like(TAG + "%")))
        await db.commit()

        post = BlogPost(
            title=f"{TAG} post",
            slug=f"{TAG}-{uuid.uuid4().hex[:8]}",
            content="x", excerpt=None, cover_image_url=None,
            author_id=user.id, status=BlogPostStatus.PUBLISHED,
            published_at=datetime.now(UTC),
            visibility=PostVisibility.PUBLIC, is_featured=False,
            allow_comments=True, post_format="standard", category_id=None,
        )
        db.add(post)
        await db.flush()

        def new_comment():
            c = BlogComment(
                post_id=post.id,
                # Polymorphic: both columns are NOT NULL, so a post comment
                # carries its post id in each.
                resource_type="blog_post", resource_id=post.id,
                content=f"{TAG} body",
                author_name=f"{TAG} visitor", author_email=f"{TAG}@example.com",
                status=CommentStatus.PENDING,
            )
            db.add(c)
            return c

        async def status_of(comment_id):
            """Read the status through a fresh session.

            The same session would hand back the object it already holds, so a
            write that never happened would still read as the new value.
            """
            async with Session() as other:
                row = (await other.execute(
                    select(BlogComment).where(BlogComment.id == comment_id)
                )).scalar_one_or_none()
                return row.status if row else None

        transport = ASGITransport(app=app.main.app)
        async with AsyncClient(transport=transport,
                               base_url="http://test") as client:

            # 1. the approve link acts
            c1 = new_comment()
            await db.commit()
            url = cmt.build_action_url(c1.id, "approve", "https://shop.test")
            r = await client.get(url)
            check("1. an approve link returns a page", r.status_code == 200,
                  f"status {r.status_code}")
            check("1b. it says the comment was approved",
                  "تأیید شد" in r.text, r.text[:160])
            check("1c. the comment is actually APPROVED",
                  await status_of(c1.id) is CommentStatus.APPROVED,
                  str(await status_of(c1.id)))

            # 2. a second click must not act again. A GET that changes state is
            #    prefetched by mail clients, so this is not hypothetical.
            r2 = await client.get(url)
            check("2. the same link a second time is refused",
                  "دیگر معتبر نیست" in r2.text, r2.text[:160])
            check("2b. and it does not report success",
                  "تأیید شد" not in r2.text, r2.text[:160])

            # 3. a link cannot be reused for a different action
            c3 = new_comment()
            await db.commit()
            approve_token = cmt.mint_token(c3.id, "approve")
            r3 = await client.get(
                f"http://test/api/v1/blog/comment-action/trash/{c3.id}"
                f"?token={approve_token}"
            )
            check("3. an approve token cannot be spent on trash",
                  "دیگر معتبر نیست" in r3.text, r3.text[:160])
            check("3b. the comment is untouched",
                  await status_of(c3.id) is CommentStatus.PENDING,
                  str(await status_of(c3.id)))

            # 4. a link cannot be pointed at another comment
            c4 = new_comment()
            await db.commit()
            other_token = cmt.mint_token(c1.id, "approve")
            r4 = await client.get(
                f"http://test/api/v1/blog/comment-action/approve/{c4.id}"
                f"?token={other_token}"
            )
            check("4. a token is bound to its own comment",
                  "دیگر معتبر نیست" in r4.text, r4.text[:160])
            check("4b. the other comment is untouched",
                  await status_of(c4.id) is CommentStatus.PENDING,
                  str(await status_of(c4.id)))

            # 5. a tampered signature is refused
            c5 = new_comment()
            await db.commit()
            good = cmt.mint_token(c5.id, "approve")
            head, _, sig = good.partition(".")
            tampered = f"{head}.{'A' * len(sig)}"
            r5 = await client.get(
                f"http://test/api/v1/blog/comment-action/approve/{c5.id}?token={tampered}"
            )
            check("5. a forged signature is refused",
                  "دیگر معتبر نیست" in r5.text, r5.text[:160])

            # 6. an expired link is refused — a moderation token is not a session
            c6 = new_comment()
            await db.commit()
            expired = cmt.mint_token(
                c6.id, "approve", now=time.time() - cmt.TOKEN_TTL_SECONDS - 60)
            r6 = await client.get(
                f"http://test/api/v1/blog/comment-action/approve/{c6.id}?token={expired}"
            )
            check("6. an expired link is refused",
                  "دیگر معتبر نیست" in r6.text, r6.text[:160])
            check("6b. the comment is untouched",
                  await status_of(c6.id) is CommentStatus.PENDING,
                  str(await status_of(c6.id)))

            # 7. an unknown action is refused rather than guessed at
            c7 = new_comment()
            await db.commit()
            r7 = await client.get(
                f"http://test/api/v1/blog/comment-action/delete/{c7.id}"
                f"?token={cmt.mint_token(c7.id, 'approve')}"
            )
            check("7. an action with no link behind it is refused",
                  "دیگر معتبر نیست" in r7.text, r7.text[:160])
            check("7b. and the comment survives",
                  await status_of(c7.id) is CommentStatus.PENDING,
                  str(await status_of(c7.id)))

            # 8. spam and trash links both reach their own status
            c8, c9 = new_comment(), new_comment()
            await db.commit()
            await client.get(cmt.build_action_url(c8.id, "spam", "https://shop.test"))
            await client.get(cmt.build_action_url(c9.id, "trash", "https://shop.test"))
            check("8. the spam link marks SPAM",
                  await status_of(c8.id) is CommentStatus.SPAM,
                  str(await status_of(c8.id)))
            check("8b. the trash link marks TRASH",
                  await status_of(c9.id) is CommentStatus.TRASH,
                  str(await status_of(c9.id)))

        # cleanup
        for stale in (await db.execute(select(BlogComment).where(
                BlogComment.content.like(TAG + "%")))).scalars().all():
            await db.execute(delete(BlogComment).where(BlogComment.id == stale.id))
        await db.execute(delete(BlogComment).where(BlogComment.post_id == post.id))
        await db.execute(delete(BlogPost).where(BlogPost.id == post.id))
        await db.commit()

    await eng.dispose()
    if bad:
        print("\nACTION GAPS:")
        for b in bad:
            print(f"  {b}")
        raise SystemExit(1)
    print("\nPASS: one-click moderation links act once, only on their own "
          "comment, and only while unexpired.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))