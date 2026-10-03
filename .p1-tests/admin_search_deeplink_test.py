"""The admin bar's contextual link must actually filter the list it lands on.

`editTargetFor` sends `/admin/blog?search=<slug>` — the last segment of the
page the operator was on. Two things have to be true for that link to work, and
they were shipped apart:

  * the admin page reads `?search=` on mount; and
  * the search matches the **slug**, not only the title.

The second half was missing on the blog side, and it is the half that matters:
the link knows nothing about the post's title, only its URL. So the list came
back filtered-looking and empty, which reads as "this post does not exist" —
the opposite of what a "take me to this post" link should convey.

Pages already searched the slug; posts searched title, excerpt and content.

Run:  python ../.p1-tests/admin_search_deeplink_test.py
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
from app.modules.blog.domain.models import BlogPost, BlogPostStatus, PostVisibility
from app.modules.content.application.cms_page_service import list_pages
from app.modules.content.domain.models import CmsPage, PageStatus
from app.modules.users.domain.models import User

TAG = "p1deeplink"
bad: list[str] = []


async def main() -> int:
    eng = _build_engine()
    Session = async_sessionmaker(eng, expire_on_commit=False)

    async with Session() as db:
        user = (await db.execute(
            select(User).where(User.is_superuser == True).limit(1)
        )).scalars().first()

        await db.execute(delete(BlogPost).where(BlogPost.slug.like(TAG + "%")))
        await db.execute(delete(CmsPage).where(CmsPage.slug.like(TAG + "%")))
        await db.commit()

        def check(label, ok, detail=""):
            print(f"  {label}: {ok}")
            if not ok:
                bad.append(f"{label}: {detail}" if detail else label)

        post_slug = f"{TAG}-{uuid.uuid4().hex[:8]}"
        post = BlogPost(
            title=f"{TAG} عنوانی که هیچ شباهتی به نامک ندارد",
            slug=post_slug, content="متن نوشته",
            excerpt=None, cover_image_url=None, author_id=user.id,
            status=BlogPostStatus.PUBLISHED, published_at=datetime.now(UTC),
            visibility=PostVisibility.PUBLIC, is_featured=False,
            allow_comments=True, post_format="standard", category_id=None,
        )
        db.add(post)

        page_slug = f"{TAG}-{uuid.uuid4().hex[:8]}"
        page = CmsPage(title=f"{TAG} عنوان صفحه", slug=page_slug,
                        body_html="<p>x</p>")
        page.status = PageStatus.PUBLISHED
        page.published_at = datetime.now(UTC)
        db.add(page)
        await db.commit()

        # The admin bar sends the slug, so the search has to find it by slug.
        found = await BlogService(db).list_posts(search=post_slug, page=1)
        check("1. a post is found by its slug, which is what the link sends",
              any(p.id == post.id for p in found.items),
              f"{len(found.items)} results for {post_slug}")

        found_by_title = await BlogService(db).list_posts(
            search="عنوانی که", page=1)
        check("1b. the title search still works",
              any(p.id == post.id for p in found_by_title.items))

        # A paged response, like every other list here.
        page_result = await list_pages(db, search=page_slug)
        check("2. a page is found by its slug too",
              any(p.id == page.id for p in page_result.items),
              f"{page_result.total} results")

        # The realistic failure: a slug that matches nothing. The link must not
        # silently return everything, or the operator sees the whole library and
        # concludes the post was deleted.
        none = await BlogService(db).list_posts(
            search=f"{TAG}-definitely-not-here", page=1)
        check("3. a slug that matches nothing returns nothing",
              len(none.items) == 0, f"{len(none.items)} results")

        await db.execute(delete(BlogPost).where(BlogPost.id == post.id))
        await db.execute(delete(CmsPage).where(CmsPage.id == page.id))
        await db.commit()

    await eng.dispose()
    if bad:
        print("\nDEEPLINK GAPS:")
        for b in bad:
            print(f"  {b}")
        raise SystemExit(1)
    print("\nPASS: the contextual link's slug finds the post it names, and a "
          "slug that matches nothing returns nothing.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))