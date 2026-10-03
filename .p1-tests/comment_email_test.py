"""Comment emails: the author mail carries Reply-To, the commenter's does not.

The send is captured rather than performed — SMTP is not available in a test
and the point is the envelope, not delivery. What matters:

  * the author mail goes out with `Reply-To` = the commenter's own address, so
    "reply" in a mail client reaches the commenter;
  * the "your comment is live" mail has no Reply-To, because it is addressed to
    the commenter — pointing it back at themselves would make reply mail them;
  * neither fires without an address. No address, no guess.
"""
import asyncio, sys, io, uuid, types
from datetime import datetime, UTC
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, 'C:/Users/Administrator/Desktop/site/backend')
import app.main
from sqlalchemy import delete, select
from app.core.database.session import _build_engine, async_sessionmaker
from app.modules.blog.domain.models import (
    BlogPost, BlogPostStatus, PostVisibility, BlogComment, CommentStatus,
)
from app.modules.users.domain.models import User
from app.modules.notifications.application import email_service as es

TAG = 'p1email'
bad: list[str] = []

# what the code under test handed to the mail service
SENT: list[dict] = []


async def fake_send_email(db, *, recipient, subject, html_body, text_body,
                          template=None, notification_id=None, config=None,
                          attachments=None, reply_to=None):
    SENT.append({
        "to": recipient, "subject": subject, "template": template,
        "reply_to": reply_to, "html": html_body, "text": text_body,
    })
    return True, None


def main_block():
    async def run():
        from app.modules.blog.application.comment_email_service import (
            CommentEmailService,
        )
        from app.modules.blog.schemas.blog import BlogCommentUpdate
        from app.modules.blog.application.comment_service import CommentService

        eng = _build_engine()
        S = async_sessionmaker(eng, expire_on_commit=False)
        async with S() as db:
            author = (await db.execute(
                select(User).where(User.is_superuser == True).limit(1))).scalars().first()
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
            await db.commit()

            post = BlogPost(title=f'{TAG} post', slug=f'{TAG}-{uuid.uuid4().hex[:8]}',
                            content='x', excerpt=None, cover_image_url=None,
                            author_id=author.id, status=BlogPostStatus.PUBLISHED,
                            published_at=datetime.now(UTC),
                            visibility=PostVisibility.PUBLIC, is_featured=False,
                            allow_comments=True, post_format='standard',
                            category_id=None)
            db.add(post); await db.commit()

            svc = CommentEmailService(db)
            # Deliberately explicit: the seeded superuser carries no email, and
            # a test that reads it would silently exercise the "no address"
            # path instead of the author-mail path it claims to check.
            admin_email = 'author@example.com'
            commenter = 'commenter@example.com'

            # 1. the author mail carries Reply-To = the commenter
            SENT.clear()
            sent = await svc.notify_post_author(
                post_title='راهنمای سایز', post_slug=post.slug,
                comment_content='سایزها درست نیست',
                comment_status='در انتظار بررسی',
                comment_author_name='Sara', comment_author_email=commenter,
                author_email=admin_email, is_pending=True, admin_url='https://shop.test')
            one = SENT[0] if SENT else {}
            ok1 = sent and one.get('to') == admin_email and one.get('reply_to') == commenter
            print(f'1. the author mail carries Reply-To = the commenter: {ok1}')
            if not ok1:
                bad.append(f'author mail envelope wrong: {one}')

            # 2. and it is the comment_new template, rendered
            ok2 = one.get('template') == 'comment_new' and 'سایزها درست نیست' in (one.get('html') or '')
            print(f'2. rendered from the comment_new template: {ok2}')
            if not ok2:
                bad.append(f'author mail body wrong: {one.get("template")}')

            # 3. the "your comment is live" mail has no Reply-To
            SENT.clear()
            sent3 = await svc.notify_commenter_approved(
                comment_author_name='Sara', comment_author_email=commenter,
                post_title='راهنمای سایز', post_slug=post.slug,
                comment_content='عالی بود', site_url='https://shop.test')
            three = SENT[0] if SENT else {}
            ok3 = sent3 and three.get('to') == commenter and three.get('reply_to') is None
            print(f'3. the commenter mail has no Reply-To: {ok3}')
            if not ok3:
                bad.append(f'commenter mail envelope wrong: {three}')

            # 4. no address, no mail — in either direction
            SENT.clear()
            r4a = await svc.notify_post_author(
                post_title='t', post_slug=post.slug, comment_content='c',
                comment_status='s', comment_author_name='Sara',
                comment_author_email=commenter, author_email=None,
                is_pending=False, admin_url='')
            r4b = await svc.notify_commenter_approved(
                comment_author_name='Sara', comment_author_email=None,
                post_title='t', post_slug=post.slug, comment_content='c',
                site_url='')
            ok4 = (not r4a and not r4b) and not SENT
            print(f'4. no address means no mail, and no guess: {ok4}')
            if not ok4:
                bad.append(f'a mail went out without an address: {SENT}')

            # 5. a broken mail service never reaches the caller
            async def boom(*a, **k):
                raise RuntimeError('SMTP is down')

            original = es.send_email
            es.send_email = boom
            try:
                r5 = await svc.notify_post_author(
                    post_title='t', post_slug=post.slug, comment_content='c',
                    comment_status='s', comment_author_name='Sara',
                    comment_author_email=commenter, author_email=admin_email,
                    is_pending=False, admin_url='')
            finally:
                es.send_email = original
            ok5 = r5 is False
            print(f'5. a failed send returns False instead of raising: {ok5}')
            if not ok5:
                bad.append('a failed send raised out of the notification')

            rows = (await db.execute(select(BlogComment).where(
                BlogComment.content.like(TAG + '%')))).scalars().all()
            if rows:
                await db.execute(delete(BlogComment).where(
                    BlogComment.id.in_([c.id for c in rows])))
            await db.execute(delete(BlogPost).where(BlogPost.id == post.id))
            await db.commit()
            print('6. cleaned up')
        await eng.dispose()

        if bad:
            print(f'EMAIL GAPS: {bad}')
            raise SystemExit(1)

    asyncio.run(run())


# Patch the attribute on the module the service resolves at call time.
es.send_email = fake_send_email
main_block()
print('PASS: the comment email envelope is right')