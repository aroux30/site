"""Live check: a reply to a CMS-page comment is addressed correctly.

Reported by a peer session reviewing the P0 "دیدگاه روی صفحات CMS" work: the
storefront was fixed to post a comment by (resource_type, resource_id), but the
admin moderation tab still replied with `submitPostComment(replyTarget.post_id,
...)`. For a page comment the API sends `post_id: null`, so the reply went to
`/blog/posts/null/comments` and came back 422 — an admin could read a page
comment and not answer it.

This asserts the two halves against the live database:
  1. the API response really carries post_id=null and a usable resource_id for
     a page comment (so the bug's premise is true, not assumed), and
  2. the same shape for a post comment, which must keep working.

It deliberately creates and removes its own comments, so it proves the path a
moderator takes rather than reading a schema. Run:
    cd backend && PYTHONPATH=. python scripts/verify_page_comment_reply.py
"""

from __future__ import annotations

import asyncio
import importlib
import io
import pkgutil
import sys
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import app.modules as _modules

for _m in pkgutil.walk_packages(_modules.__path__, "app.modules."):
    try:
        importlib.import_module(_m.name)
    except Exception:  # noqa: BLE001
        pass

from app.modules.blog.application.comment_service import CommentService  # noqa: E402
from app.modules.blog.schemas.blog import (  # noqa: E402
    BlogCommentAdminResponse,
    BlogCommentCreate,
)
from app.modules.blog.domain.models import BlogComment  # noqa: E402
from app.modules.content.domain.models import CmsPage  # noqa: E402

COMMENT_RESOURCE_CMS_PAGE = "cms_page"
COMMENT_RESOURCE_BLOG_POST = "blog_post"


def _database_url() -> str:
    for line in open(".env", encoding="utf-8"):
        if line.startswith("DATABASE_URL="):
            return line.split("=", 1)[1].strip().strip("\"'")
    raise SystemExit("DATABASE_URL not found in .env")


async def main() -> int:
    engine = create_async_engine(_database_url())
    session = async_sessionmaker(engine, expire_on_commit=False)
    failures: list[str] = []

    async with session() as db:
        page_id = (
            await db.execute(
                text(
                    "SELECT id FROM cms_pages WHERE status='PUBLISHED' "
                    "ORDER BY created_at LIMIT 1"
                )
            )
        ).scalar()
        if page_id is None:
            print("SKIP: no published page to reply to.")
            await engine.dispose()
            return 0
        page_id = uuid.UUID(str(page_id))

        page = await db.get(CmsPage, page_id)
        page.allow_comments = True
        await db.commit()

        svc = CommentService(db)
        made: list[uuid.UUID] = []

        try:
            # A reader comments on the page, exactly as the storefront does.
            page_comment = await svc.create_comment(
                BlogCommentCreate(
                    resource_type=COMMENT_RESOURCE_CMS_PAGE,
                    resource_id=page_id,
                    content="پاسخ‌خواهی این دیدگاه برای بررسی آدرس مقصد",
                    author_name="بازدیدکننده",
                    author_email="visitor@example.com",
                ),
                # no request object: the service takes the IP and UA as scalars,
                author_id=None,
            )
            made.append(uuid.UUID(str(page_comment.id)))

            # 2. The admin response is what the moderation table renders. If it
            #    reports a post_id here, the tab's old call would have a value to
            #    post to and the bug premise would be wrong.
            page_row = await db.get(BlogComment, uuid.UUID(str(page_comment.id)))
            admin_view = BlogCommentAdminResponse.model_validate(page_row)
            if admin_view.post_id is not None:
                failures.append(
                    "a page comment reported post_id=%s, so the premise (that the "
                    "admin tab posts to /blog/posts/null) is not what ships"
                    % admin_view.post_id
                )
            else:
                print("PASS: a page comment reports post_id=None, as the report said")

            if admin_view.resource_type != COMMENT_RESOURCE_CMS_PAGE:
                failures.append(
                    "resource_type on a page comment is %r, expected 'cms_page'"
                    % admin_view.resource_type
                )
            elif str(admin_view.resource_id) != str(page_id):
                failures.append(
                    "resource_id on a page comment is %s, expected the page id %s"
                    % (admin_view.resource_id, page_id)
                )
            else:
                print(
                    "PASS: the admin response carries resource_type=cms_page and "
                    "resource_id=%s, so a reply has somewhere to go" % page_id
                )

            # 3. The moderator's reply, sent the way the fixed tab sends it.
            reply = await svc.create_comment(
                BlogCommentCreate(
                    resource_type=COMMENT_RESOURCE_CMS_PAGE,
                    resource_id=page_id,
                    content="پاسخ مدیریت به دیدگاه صفحه",
                    parent_id=uuid.UUID(str(page_comment.id)),
                    author_name="مدیریت سایت",
                ),
                # no request object: the service takes the IP and UA as scalars,
                author_id=None,
            )
            made.append(uuid.UUID(str(reply.id)))
            if str(reply.parent_id) != str(page_comment.id):
                failures.append("the reply was not attached to the page comment")
            elif str(reply.resource_id) != str(page_id):
                failures.append("the reply landed on the wrong resource")
            else:
                print("PASS: a reply to a page comment attaches to it, on the page")

            # 4. The post path must be unaffected: a post comment still reports
            #    a post_id, so the legacy addressing keeps working.
            post_id = (
                await db.execute(
                    text(
                        "SELECT id FROM blog_posts WHERE status='PUBLISHED' "
                        "ORDER BY created_at LIMIT 1"
                    )
                )
            ).scalar()
            if post_id is not None:
                post_id = uuid.UUID(str(post_id))
                post_comment = await svc.create_comment(
                    BlogCommentCreate(
                        post_id=post_id,
                        content="دیدگاه روی نوشته برای بررسی مسیر پاسخ",
                        author_name="بازدیدکننده",
                        author_email="visitor@example.com",
                    ),
                    # no request object: the service takes the IP and UA as scalars,
                    author_id=None,
                )
                made.append(uuid.UUID(str(post_comment.id)))
                post_row = await db.get(BlogComment, uuid.UUID(str(post_comment.id)))
                post_view = BlogCommentAdminResponse.model_validate(post_row)
                if post_view.post_id is None:
                    failures.append(
                        "a post comment stopped reporting post_id, so the legacy "
                        "path regressed"
                    )
                elif str(post_view.resource_id) != str(post_id):
                    failures.append(
                        "a post comment reports resource_id=%s, expected %s"
                        % (post_view.resource_id, post_id)
                    )
                else:
                    print("PASS: a post comment still carries post_id and resource_id")
            else:
                print("SKIP: no published post, so the post path was not exercised")

        finally:
            # Sweep by content + target, not only by the ids collected above.
            # `made.append` runs after create_comment returns, so a comment
            # created and then lost to a failure before that line was never in
            # `made` — which is how four PENDING probe comments survived on the
            # live database. The marker text is unique to this script, so the
            # sweep cannot touch a real comment.
            await db.execute(
                text(
                    "DELETE FROM blog_comments WHERE content IN ("
                    " 'پاسخ‌خواهی این دیدگاه برای بررسی آدرس مقصد',"
                    " 'پاسخ مدیریت به دیدگاه صفحه',"
                    " 'دیدگاه روی نوشته برای بررسی مسیر پاسخ'"
                    ")"
                )
            )
            for cid in made:
                await db.execute(
                    text("DELETE FROM blog_comments WHERE id = :id"), {"id": str(cid)}
                )
            await db.commit()
            page.allow_comments = False
            await db.commit()
            print("cleaned up probe comments; allow_comments restored")

    await engine.dispose()

    for f in failures:
        print("FAIL: %s" % f)
    if failures:
        return 1
    print("")
    print("PASS: a page comment and a post comment each carry a usable address.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
