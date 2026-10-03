"""A renamed post or page must keep answering at its old URL.

The slug history has been written on every rename since it was added. Nothing
read it. So changing a slug broke every link anybody had ever shared to that
post — the exact loss a rename is supposed to avoid, and the one thing the
history table exists to prevent.

Two things are checked that a "the redirect works" test would not catch:

  * **a redirect is not a bypass.** Following an old slug re-runs the *same*
    lookup, so a draft stays unreachable through its old URL. A fix that
    resolved the slug and returned the row directly would make every renamed
    draft public, which is worse than the 404 it replaced.
  * **a genuine miss is still a miss.** A slug that is not in the history has
    to 404, or the fallback has swallowed the real not-found case.

Run:  python ../.p1-tests/slug_redirect_test.py
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
from app.modules.blog.application.blog_service import BlogService
from app.modules.blog.application.slug_history_service import record_slug_change
from app.modules.blog.domain.models import BlogPost, BlogPostStatus, PostVisibility
from app.modules.content.application import cms_page_service
from app.modules.content.domain.models import CmsPage, PageStatus
from app.modules.users.domain.models import User

TAG = "p1slug"
bad: list[str] = []


async def main() -> int:
    eng = _build_engine()
    Session = async_sessionmaker(eng, expire_on_commit=False)

    async with Session() as db:
        user = (await db.execute(
            select(User).where(User.is_superuser == True).limit(1)
        )).scalars().first()

        for stale in (await db.execute(select(BlogPost).where(
                BlogPost.slug.like(TAG + "%")))).scalars().all():
            await db.execute(delete(BlogPost).where(BlogPost.id == stale.id))
        for stale in (await db.execute(select(CmsPage).where(
                CmsPage.slug.like(TAG + "%")))).scalars().all():
            await db.execute(delete(CmsPage).where(CmsPage.id == stale.id))
        await db.commit()

        def check(label, ok, detail=""):
            print(f"  {label}: {ok}")
            if not ok:
                bad.append(f"{label}: {detail}" if detail else label)

        blog = BlogService(db)


        # --- post -------------------------------------------------------
        old = f"{TAG}-old-{uuid.uuid4().hex[:6]}"
        new = f"{TAG}-new-{uuid.uuid4().hex[:6]}"
        post = BlogPost(
            title=f"{TAG} post", slug=new, content="x", excerpt=None,
            cover_image_url=None, author_id=user.id,
            status=BlogPostStatus.PUBLISHED, published_at=datetime.now(UTC),
            visibility=PostVisibility.PUBLIC, is_featured=False,
            allow_comments=True, post_format="standard", category_id=None,
        )
        db.add(post)
        await db.flush()
        await record_slug_change(
            db, resource_type="blog_post", resource_id=post.id,
            old_slug=old, new_slug=new,
        )
        await db.commit()

        got = await blog.get_post_by_slug(old)
        check("1. an old post slug still resolves", got.id == post.id,
              f"got {got.id}")

        got_new = await blog.get_post_by_slug(new)
        check("2. the current slug still resolves", got_new.id == post.id)

        # 3. a draft is not reachable through its old URL. The redirect re-runs
        #    the same query, so `only_published` still applies.
        draft = BlogPost(
            title=f"{TAG} draft", slug=f"{TAG}-draft-{uuid.uuid4().hex[:6]}",
            content="x", excerpt=None, cover_image_url=None, author_id=user.id,
            status=BlogPostStatus.DRAFT, published_at=None,
            visibility=PostVisibility.PUBLIC, is_featured=False,
            allow_comments=True, post_format="standard", category_id=None,
        )
        db.add(draft)
        await db.flush()
        draft_old = f"{TAG}-draft-old-{uuid.uuid4().hex[:6]}"
        await record_slug_change(
            db, resource_type="blog_post", resource_id=draft.id,
            old_slug=draft_old, new_slug=draft.slug,
        )
        await db.commit()
        refused = False
        try:
            await blog.get_post_by_slug(draft_old)
        except Exception as exc:
            refused = type(exc).__name__ == "NotFoundError"
        check("3. a renamed draft stays unreachable through its old slug",
              refused, "the redirect served a draft")

        # 4. a slug nobody ever used is still a 404 — the fallback must not
        #    have swallowed the real miss.
        missing = False
        try:
            await blog.get_post_by_slug(f"{TAG}-never-existed")
        except Exception as exc:
            missing = type(exc).__name__ == "NotFoundError"
        check("4. an unknown slug still 404s", missing)

        # --- page -------------------------------------------------------
        p_old = f"{TAG}-page-old-{uuid.uuid4().hex[:6]}"
        p_new = f"{TAG}-page-new-{uuid.uuid4().hex[:6]}"
        page = CmsPage(title=f"{TAG} page", slug=p_new, body_html="<p>x</p>")
        page.status = PageStatus.PUBLISHED
        page.published_at = datetime.now(UTC)
        db.add(page)
        await db.flush()
        await record_slug_change(
            db, resource_type="cms_page", resource_id=page.id,
            old_slug=p_old, new_slug=p_new,
        )
        await db.commit()

        got_page = await cms_page_service.get_page_by_slug(db, p_old)
        check("5. an old page slug still resolves", got_page.id == page.id,
              f"got {got_page.id}")

        # 6. and a post slug must not resolve to a page or vice versa
        crossed = False
        try:
            await cms_page_service.get_page_by_slug(db, old)
        except Exception as exc:
            crossed = type(exc).__name__ == "NotFoundError"
        check("6. a post's old slug does not resolve as a page", crossed)

        await db.execute(delete(BlogPost).where(
            BlogPost.id.in_([post.id, draft.id])))
        await db.execute(delete(CmsPage).where(CmsPage.id == page.id))
        await db.commit()

    await eng.dispose()
    if bad:
        print("\nSLUG-REDIRECT GAPS:")
        for b in bad:
            print(f"  {b}")
        raise SystemExit(1)
    print("\nPASS: renamed posts and pages keep answering at their old URL, "
          "and a redirect is not a way to reach a draft.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
