"""Two comment options that only count as done if the server honours them.

  - ``comments_notify`` / ``moderation_notify``: a switch that is read and then
    ignored still *looks* implemented, because the mail still goes out and
    nothing fails. So each is tested both ways.
  - ``close_comments_days_old``: measured on the post, not the comment. The
    claim being made is that the conversation on this post is finished; a
    threshold that looked at the comment's age would let an old post collect
    replies forever, which is the thing the option exists to prevent.

Options are written through the service's own writer, because the reader and
the writer both speak `site_options` — writing a `site_settings` row by hand
puts the value in a table nothing reads and the guard silently keeps its
default.
"""
import asyncio, sys, io, uuid
from datetime import datetime, UTC, timedelta
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, 'C:/Users/Administrator/Desktop/site/backend')
import app.main
from sqlalchemy import select, delete
from app.core.database.session import _build_engine, async_sessionmaker
from app.modules.blog.domain.models import (
    BlogPost, BlogPostStatus, PostVisibility, BlogComment,
)
from app.modules.blog.schemas.blog import BlogCommentCreate
from app.modules.blog.application.comment_service import CommentService
from app.modules.content.domain.models import CmsPage, PageStatus
from app.modules.settings.application.site_options_service import SiteOptionsService
from app.modules.users.domain.models import User

TAG = 'p1opt'
bad: list[str] = []

# what the email path was asked to send
MAILS: list[dict] = []


async def main():
    eng = _build_engine()
    S = async_sessionmaker(eng, expire_on_commit=False)
    async with S() as db:
        user = (await db.execute(
            select(User).where(User.is_superuser == True).limit(1))).scalars().first()
        # With no address on file the notification path correctly sends nothing,
        # so a test that reads the seeded admin would measure the no-address
        # guard instead of the switch it means to check.
        if not (user.email or "").strip():
            user.email = f'{TAG}-author-{uuid.uuid4().hex[:8]}@example.com'
            await db.commit()
        stale = (await db.execute(select(BlogComment).where(
            BlogComment.content.like(TAG + '%')))).scalars().all()
        if stale:
            await db.execute(delete(BlogComment).where(
                BlogComment.id.in_([c.id for c in stale])))
        sp = (await db.execute(select(BlogPost).where(
            BlogPost.slug.like(TAG + '%')))).scalars().all()
        if sp:
            await db.execute(delete(BlogComment).where(
                BlogComment.post_id.in_([p.id for p in sp])))
            await db.execute(delete(BlogPost).where(
                BlogPost.id.in_([p.id for p in sp])))
        spg = (await db.execute(select(CmsPage).where(
            CmsPage.slug.like(TAG + '%')))).scalars().all()
        for g in spg:
            await db.execute(delete(BlogComment).where(
                BlogComment.resource_id == g.id))
            await db.execute(delete(CmsPage).where(CmsPage.id == g.id))
        await db.commit()

        svc = CommentService(db)

        async def setopt(k, v):
            await SiteOptionsService.set(db, k, v)

        async def mkpost(suffix, published_at):
            p = BlogPost(title=f'{TAG} {suffix}',
                         slug=f'{TAG}-{suffix}-{uuid.uuid4().hex[:8]}',
                         content='x', excerpt=None, cover_image_url=None,
                         author_id=user.id, status=BlogPostStatus.PUBLISHED,
                         published_at=published_at, visibility=PostVisibility.PUBLIC,
                         is_featured=False, allow_comments=True,
                         post_format='standard', category_id=None)
            db.add(p); await db.flush(); return p

        # capture the email decisions the service makes
        from app.modules.blog.application import comment_email_service as ces

        real = ces.CommentEmailService.notify_post_author
        calls: list[dict] = []

        async def capture(self, **kw):
            # Only a call that carries an address reaches the wire; the real
            # method returns False without one. Recording it as a "mail sent"
            # would let a switch that changed nothing still look like it worked.
            if kw.get('author_email'):
                calls.append(kw)
            return bool(kw.get('author_email'))

        ces.CommentEmailService.notify_post_author = capture

        try:
            await setopt('moderation_notify', '1')
        # isolate from the guards set in the previous wave's fixture
            await setopt('comment_flood_seconds', '0')
            await setopt('comments_per_hour', '0')
            await setopt('comments_per_day', '0')
            await setopt('require_name_email', '0')

            fresh_post = await mkpost('fresh', datetime.now(UTC))

            # 1. comments_notify on: the author mail is attempted
            await setopt('comments_notify', '1')
            approved_post = await mkpost('approved', datetime.now(UTC))
            calls.clear()
            await svc.create_comment(
                BlogCommentCreate(post_id=approved_post.id, content=f'{TAG} n1'),
                author_id=user.id)
            ok1 = (len(calls) == 1
                   and calls[0]['author_email'] == user.email)
            print(f'1. with comments_notify on the author mail is attempted: {ok1}')
            if not ok1:
                bad.append(f'comments_notify=1 produced no author mail: {calls}')

            # 2. comments_notify off: no mail, and the comment still stores.
            #    On an approved comment, because WordPress keeps the two paths
            #    apart — moderation_notify only fires for a *held* comment, so
            #    a pending one would be answered by the moderation address and
            #    the switch under test would never be read on its own.
            await setopt('comments_notify', '0')
            await setopt('moderation_notify', '0')
            calls.clear()
            c2 = await svc.create_comment(
                BlogCommentCreate(post_id=approved_post.id, content=f'{TAG} n2'),
                author_id=user.id)
            ok2 = not calls and c2 is not None
            print(f'2. with it off no mail goes out and the comment stores: {ok2}')
            if not ok2:
                bad.append(f'comments_notify=0 still addressed a mail: {calls}')

            # 3. moderation_notify only matters for a held comment
            await setopt('comments_notify', '1')
            await setopt('moderation_notify', '0')
            held_post = await mkpost('held', datetime.now(UTC))
            calls.clear()
            await svc.create_comment(
                BlogCommentCreate(post_id=held_post.id, content=f'{TAG} n3'),
                author_id=user.id)
            ok3 = (len(calls) == 1
                   and calls[0].get('is_pending') is True
                   and calls[0]['author_email'] == user.email)
            print(f'3. a held comment is held with moderation_notify off: {ok3}')
            if not ok3:
                bad.append(f'the held comment did not report itself pending: {calls}')

            # 4. close_comments_days_old: off by default
            await setopt('close_comments_days_old', '0')
            old_post = await mkpost('old', datetime.now(UTC) - timedelta(days=400))
            ok4 = True
            try:
                await svc.create_comment(
                    BlogCommentCreate(post_id=old_post.id, content=f'{TAG} old ok'),
                    author_id=user.id)
            except Exception:
                ok4 = False
            print(f'4. a 400-day-old post still accepts comments when off: {ok4}')
            if not ok4:
                bad.append('close_comments_days_old=0 still refused a comment')

            # 5. on: an old post refuses
            await setopt('close_comments_days_old', '30')
            refused = False
            try:
                await svc.create_comment(
                    BlogCommentCreate(post_id=old_post.id, content=f'{TAG} old no'),
                    author_id=user.id)
            except Exception:
                refused = True
            ok5 = refused
            print(f'5. with it on, an old post refuses: {ok5}')
            if not ok5:
                bad.append('close_comments_days_old=30 did not refuse an old post')

            # 6. and a young post is unaffected — the threshold is on age, not
            #    on "has comments"
            young = await mkpost('young', datetime.now(UTC))
            ok6 = True
            try:
                await svc.create_comment(
                    BlogCommentCreate(post_id=young.id, content=f'{TAG} young'),
                    author_id=user.id)
            except Exception:
                ok6 = False
            print(f'6. a young post is unaffected by the threshold: {ok6}')
            if not ok6:
                bad.append('the age limit refused a young post')

            # 7. a page is covered too — otherwise the rule has a hole in it,
            #    because the oldest thread is usually on a page
            page = CmsPage(title=f'{TAG} old page',
                            slug=f'{TAG}-pg-{uuid.uuid4().hex[:8]}',
                            body_html='<p>x</p>')
            page.published_at = datetime.now(UTC) - timedelta(days=400)
            page.status = PageStatus.PUBLISHED
            page.allow_comments = True
            db.add(page); await db.flush()
            refused7 = False
            try:
                await svc.create_comment(
                    BlogCommentCreate(resource_type='cms_page', resource_id=page.id,
                                      content=f'{TAG} page no'),
                    author_id=user.id)
            except Exception:
                refused7 = True
            ok7 = refused7
            print(f'7. an old page refuses as well: {ok7}')
            if not ok7:
                bad.append('the age limit does not cover pages')

            # 8. a page with comments closed by the operator still refuses
            #    regardless of age
            fresh_page = CmsPage(title=f'{TAG} off page',
                                 slug=f'{TAG}-pgo-{uuid.uuid4().hex[:8]}',
                                 body_html='<p>x</p>')
            fresh_page.status = PageStatus.PUBLISHED
            fresh_page.allow_comments = False
            db.add(fresh_page); await db.flush()
            refused8 = False
            try:
                await svc.create_comment(
                    BlogCommentCreate(resource_type='cms_page', resource_id=fresh_page.id,
                                      content=f'{TAG} page off'),
                    author_id=user.id)
            except Exception:
                refused8 = True
            ok8 = refused8
            print(f'8. a page with comments off refuses regardless of age: {ok8}')
            if not ok8:
                bad.append('allow_comments=False was not honoured on a young page')

            await setopt('close_comments_days_old', '0')
            await setopt('comments_notify', '1')
            await setopt('moderation_notify', '1')
        finally:
            ces.CommentEmailService.notify_post_author = real
            # The rate ceilings and the flood window were switched off so the
            # auto-close checks are not racing a limiter. Leaving them off
            # broke the *next* fixture to run: comment_guards_test posts
            # comments, and with comments_per_hour at 0 every one of them was
            # refused with "more than 0 comments this hour". A fixture that
            # does not put the site's settings back is a fixture that changes
            # the meaning of the tests after it, which is how a real
            # regression gets misread as flakiness.
            # Restored from DEFAULT_OPTIONS rather than written literally, so a
            # change to a default cannot leave this fixture restoring a stale
            # value — which is the same class of drift, one level down.
            from app.modules.settings.application.default_options import DEFAULTS
            for key in ('comment_flood_seconds', 'comments_per_hour',
                         'comments_per_day', 'require_name_email'):
                await setopt(key, str(DEFAULTS.get(key, '0')))

        rows = (await db.execute(select(BlogComment).where(
            BlogComment.content.like(TAG + '%')))).scalars().all()
        if rows:
            await db.execute(delete(BlogComment).where(
                BlogComment.id.in_([c.id for c in rows])))
        posts = (await db.execute(select(BlogPost).where(
            BlogPost.slug.like(TAG + '%')))).scalars().all()
        if posts:
            await db.execute(delete(BlogPost).where(
                BlogPost.id.in_([p.id for p in posts])))
        pages = (await db.execute(select(CmsPage).where(
            CmsPage.slug.like(TAG + '%')))).scalars().all()
        for g in pages:
            await db.execute(delete(CmsPage).where(CmsPage.id == g.id))
        await db.commit()
        print('9. cleaned up')
        if bad:
            print(f'OPTION GAPS: {bad}')
            raise SystemExit(1)
    await eng.dispose()


asyncio.run(main())