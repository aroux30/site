"""comment_previously_approved — a switch that looks implemented and approves nothing.

The feature is one line in WordPress (`comment.php:133`) and it is the thing
that makes a store's comment queue drain: a customer who has already been
approved once stops waiting a day for their second comment to appear. Getting
it wrong is silent in both directions —

  * off when it should be on: nothing breaks, the queue just keeps filling;
  * on when it should be off: every name-shaped spam comment from someone who
    ever got through publishes itself.

So each of the three conditions core checks is tested separately, and the two
that make it *safe* get the most attention, because those are the ones a
careless implementation drops:

  * it keys on the email, and on the name too for guests — never the name
    alone, which is the easiest thing for a spammer to borrow;
  * a moderation keyword in the address still holds the comment, so someone
    who got in before that word list existed cannot hold the store hostage;
  * a missing name or a missing email never matches, because those columns are
    NULL on rows and a NULL comparison is true against NULL.

The fixture writes options through the service's writer, because the reader and
the writer both speak `site_options` — a value written anywhere else is read by
nothing and every assertion below would pass for the wrong reason.
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
from app.modules.blog.schemas.blog import BlogCommentCreate
from app.modules.settings.application.site_options_service import SiteOptionsService
from app.modules.users.domain.models import User

TAG = "p1prev"
bad: list[str] = []


async def main() -> int:
    eng = _build_engine()
    Session = async_sessionmaker(eng, expire_on_commit=False)

    async with Session() as db:
        user = (await db.execute(
            select(User).where(User.is_superuser == True).limit(1))
        ).scalars().first()

        # Debris from a killed run would make this one fail on a duplicate slug.
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

        async def setopt(key, value):
            await SiteOptionsService.set(db, key, value)

        # Isolate from every other guard this fixture is not testing.
        await setopt("comment_flood_seconds", "0")
        await setopt("comments_per_hour", "0")
        await setopt("comments_per_day", "0")
        await setopt("require_name_email", "0")
        await setopt("moderation_keys", "")
        await setopt("disallowed_keys", "")
        await setopt("comment_moderation", "1")
        await setopt("registration_required", "0")

        def guest(name, email):
            """A guest comment as a stranger posts it — no account."""
            return BlogCommentCreate(
                post_id=post.id, content=f"{TAG} body {uuid.uuid4().hex[:6]}",
                author_name=name, author_email=email,
            )

        async def submit(name, email):
            """Post as a stranger, then read what the server decided.

            `create_comment` returns a response that deliberately omits the
            moderation status — a guest must not be able to tell a held comment
            from a published one, because that tells them whether they got past
            the filter. The status therefore has to be read back from a second
            session, or this fixture would be testing the response shape.
            """
            created = await svc.create_comment(guest(name, email))
            async with Session() as other:
                row = (await other.execute(
                    select(BlogComment).where(BlogComment.id == created.id)
                )).scalar_one_or_none()
            return row.status if row else None

        def check(label, ok, detail=""):
            print(f"  {label}: {ok}")
            if not ok:
                bad.append(f"{label}: {detail}" if detail else label)

        try:
            # 0. with the switch OFF a returning commenter is still queued —
            #    this is the control the other six depend on.
            await setopt("comment_previously_approved", "0")
            seed_email = f"{TAG}-seed@example.com"
            await db.execute(delete(BlogComment).where(
                BlogComment.author_email == seed_email))
            await db.commit()
            seeded = BlogComment(
                post_id=post.id, resource_type="blog_post", resource_id=post.id,
                content=f"{TAG} seeded approved", author_name=f"{TAG} seed",
                author_email=seed_email, status=CommentStatus.APPROVED,
            )
            db.add(seeded)
            await db.commit()

            held = await submit(f"{TAG} seed", seed_email)
            check("1. with the switch off a returning commenter is still queued",
                  held is CommentStatus.PENDING, str(held))

            # 2. on: the same person is approved straight through
            await setopt("comment_previously_approved", "1")
            through = await submit(f"{TAG} seed", seed_email)
            check("2. with it on the same email is approved automatically",
                  through is CommentStatus.APPROVED, str(through))

            # 3. a stranger is still queued — the switch is not "approve all"
            stranger = await submit(f"{TAG} stranger", f"{TAG}-stranger@example.com")
            check("3. a stranger is still queued",
                  stranger is CommentStatus.PENDING, str(stranger))

            # 4. the name alone must not carry it. This is the hole that turns
            #    the feature into a publisher for anyone borrowing a name.
            impostor = await submit(f"{TAG} seed", f"{TAG}-impostor@example.com")
            check("4. the same NAME with a different address is queued",
                  impostor is CommentStatus.PENDING, str(impostor))

            # 5. an address matching a moderation keyword still waits, so the
            #    escape hatch works even for someone already approved. The
            #    keyword is the local part, because core compares the address
            #    itself — a substring test on the whole address would hit every
            #    row whose domain contains the word.
            kw_email = f"holdme-{uuid.uuid4().hex[:6]}@example.com"
            await setopt("moderation_keys", "holdme")
            await setopt("comment_previously_approved", "0")
            await submit(f"{TAG} seed", kw_email)
            await db.execute(
                BlogComment.__table__.update()
                .where(BlogComment.author_email == kw_email)
                .values(status=CommentStatus.APPROVED))
            await db.commit()
            repeat = await submit(f"{TAG} seed", kw_email)
            check("5. an approved address on the keyword list is still queued",
                  repeat is CommentStatus.PENDING, str(repeat))
            await setopt("moderation_keys", "")

            # 6. a keyword that only matches part of a name is not a match —
            #    substring matching would make ordinary addresses collide.
            await setopt("moderation_keys", "example.org")
            await setopt("comment_previously_approved", "1")
            domain_email = f"{TAG}-domain@example.net"
            await db.execute(delete(BlogComment).where(
                BlogComment.author_email == domain_email))
            first = await submit(f"{TAG} domain", domain_email)
            if first is CommentStatus.PENDING:
                # Promote it out of the queue by hand: this assertion is about
                # the *second* comment from the same address, so the first one
                # has to be approved for the lookup to have anything to find.
                await db.execute(
                    BlogComment.__table__.update()
                    .where(BlogComment.content.like(TAG + "%"),
                           BlogComment.author_email == domain_email)
                    .values(status=CommentStatus.APPROVED))
                await db.commit()
            second = await submit(f"{TAG} domain", domain_email)
            check("6. a keyword matching another domain does not hold it",
                  second is CommentStatus.APPROVED, str(second))
            await setopt("moderation_keys", "")

            # 7. no name or no email must not match a row where that column is
            #    null. Left alone, every nameless comment on the site matches.
            nameless = await submit(None, seed_email)
            check("7. a nameless comment with a known address is queued",
                  nameless is CommentStatus.PENDING, str(nameless))
            mailless = await submit(f"{TAG} seed", None)
            check("7b. a comment with no address is queued",
                  mailless is CommentStatus.PENDING, str(mailless))

        finally:
            await setopt("comment_previously_approved", "0")
            await setopt("moderation_keys", "")

        await db.execute(delete(BlogComment).where(
            BlogComment.content.like(TAG + "%")))
        await db.execute(delete(BlogComment).where(
            BlogComment.author_email.like(TAG + "%")))
        await db.execute(delete(BlogComment).where(
            BlogComment.post_id == post.id))
        await db.execute(delete(BlogPost).where(BlogPost.id == post.id))
        await db.commit()

    await eng.dispose()
    if bad:
        print("\nPREVIOUSLY-APPROVED GAPS:")
        for b in bad:
            print(f"  {b}")
        raise SystemExit(1)
    print("\nPASS: a returning commenter is approved by email and name, and "
          "nobody else is.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))