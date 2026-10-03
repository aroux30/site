"""Comment moderation: editing, unapprove, bulk, trash, search, and the admin fields."""
import asyncio, sys, io, uuid
from datetime import datetime, UTC
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, 'C:/Users/Administrator/Desktop/site/backend')
import app.main
from sqlalchemy import select, delete
from app.core.database.session import _build_engine, async_sessionmaker
from app.modules.blog.domain.models import BlogComment, BlogPost, BlogPostStatus, PostVisibility
from app.modules.blog.schemas.blog import BlogCommentUpdate
from app.modules.blog.application.comment_service import CommentService
from app.modules.users.domain.models import User

TAG = 'p1cmt'
bad: list[str] = []


async def main():
    eng = _build_engine()
    S = async_sessionmaker(eng, expire_on_commit=False)
    async with S() as db:
        me = (await db.execute(
            select(User).where(User.is_superuser == True).limit(1))).scalars().first()
        stale = (await db.execute(select(BlogComment).where(
            BlogComment.content.like(TAG + '%')))).scalars().all()
        if stale:
            await db.execute(delete(BlogComment).where(
                BlogComment.id.in_([c.id for c in stale])))
        stales_posts = (await db.execute(select(BlogPost).where(
            BlogPost.slug.like(TAG + '%')))).scalars().all()
        if stales_posts:
            await db.execute(delete(BlogComment).where(
                BlogComment.post_id.in_([p.id for p in stales_posts])))
            await db.execute(delete(BlogPost).where(
                BlogPost.id.in_([p.id for p in stales_posts])))
        await db.commit()
        svc = CommentService(db)

        post = BlogPost(title=TAG, slug=f'{TAG}-{uuid.uuid4().hex[:8]}', content='x',
                        excerpt=None, cover_image_url=None, author_id=me.id,
                        status=BlogPostStatus.PUBLISHED, published_at=datetime.now(UTC),
                        visibility=PostVisibility.PUBLIC, is_featured=False,
                        allow_comments=True, post_format='standard', category_id=None)
        db.add(post)
        await db.flush()
        made = []

        async def mk(content, **kw):
            c = BlogComment(
                post_id=post.id,
                # Comments are polymorphic and both columns are NOT NULL; a
                # fixture that sets only post_id is not a legacy row, it is an
                # invalid one.
                resource_type='blog_post',
                resource_id=post.id,
                author_name=kw.get('name', 'Ali'),
                author_email=kw.get('email', 'ali@example.com'),
                author_url=kw.get('url'), author_ip=kw.get('ip'),
                content=content, status=kw.get('status', 'approved'))
            db.add(c)
            await db.flush()
            made.append(c.id)
            return c

        await mk(f'{TAG} hello world')
        await mk(f'{TAG} buy now cheap', name='Sara', email='sara@example.com',
                 url='https://spam.example', ip='203.0.113.9')
        await mk(f'{TAG} third comment', name='Reza')
        await db.commit()

        # 1. the admin response carries the IP and the website
        listed = await svc.list_comments(post_id=post.id, status=None,
                                         include_moderation_fields=True,
                                         comment_type='comment')
        with_ip = [c for c in listed.items if c.author_ip]
        with_url = [c for c in listed.items if c.author_url]
        ok1 = len(with_ip) == 1 and len(with_url) == 1
        print(f'1. admin list carries the IP and the website: {ok1}')
        if not ok1:
            bad.append('admin response missing the IP or the website')

        # 2. the public list must carry neither
        public = await svc.list_comments(post_id=post.id, status=None,
                                         include_moderation_fields=False,
                                         comment_type='comment')
        leaked = [c for c in public.items
                  if getattr(c, 'author_ip', None) or getattr(c, 'author_email', None)]
        ok2 = not leaked
        print(f'2. the public list leaks no address: {ok2}')
        if not ok2:
            bad.append('the public comment list leaked an address')

        # 3. editing the body
        target = made[0]
        await svc.update_comment(target, BlogCommentUpdate(content=f'{TAG} edited body'))
        got = (await db.execute(
            select(BlogComment).where(BlogComment.id == target))).scalar_one()
        ok3 = got.content.endswith('edited body')
        print(f'3. the body can be edited: {ok3}')
        if not ok3:
            bad.append('editing the body did nothing')

        # 4. editing only the body must leave the author fields alone. This is
        #    the trap a model_dump without exclude_unset springs: the admin
        #    schema does not carry the email, so an unguarded dump sends None
        #    and erases the address that identifies the commenter.
        # Read the current value fresh, and expire the session first. The
        # instance loaded for test 3 is still in the identity map, so reading
        # it back would compare a stale attribute against itself and pass
        # whatever the service did.
        # Read through a second session: the instance in this one is the one
        # the service mutated, so comparing it against itself would pass
        # whatever the service did. `expire_all()` is not the way to refresh
        # here — it expires the lazily-loaded relationships and the next
        # attribute read raises MissingGreenlet outside a greenlet context.
        async def read_email() -> str | None:
            async with S() as fresh:
                row = (await fresh.execute(
                    select(BlogComment).where(BlogComment.id == target))).scalar_one()
                return row.author_email

        before_email = await read_email()
        await svc.update_comment(target, BlogCommentUpdate(content=f'{TAG} edited again'))
        after_email = await read_email()
        ok4 = after_email == before_email and before_email is not None
        print(f'4. an unrelated edit keeps the author email: {ok4}')
        if not ok4:
            bad.append('editing the body cleared the author email')

        # 5. the author fields themselves are editable
        await svc.update_comment(target, BlogCommentUpdate(author_name='Ali Rezaei'))
        got5 = (await db.execute(
            select(BlogComment).where(BlogComment.id == target))).scalar_one()
        ok5 = got5.author_name == 'Ali Rezaei'
        print(f'5. the author name is editable: {ok5}')
        if not ok5:
            bad.append('the author name was not editable')

        # 6. unapprove
        res6 = await svc.bulk_moderate([target], 'unapprove')
        got6 = (await db.execute(
            select(BlogComment).where(BlogComment.id == target))).scalar_one()
        ok6 = res6['ok'] == 1 and got6.status.value == 'pending'
        print(f'6. unapprove works: {ok6}')
        if not ok6:
            bad.append('unapprove did not move the comment to pending')

        # 7. trash is a state, not a deletion
        await svc.bulk_moderate([target], 'trash')
        alive = (await db.execute(
            select(BlogComment).where(BlogComment.id == target))).scalar_one()
        ok7 = alive is not None and alive.status.value == 'trash'
        print(f'7. trash keeps the row: {ok7}')
        if not ok7:
            bad.append('trash deleted the row instead of flagging it')

        # 8. restore brings it back to approved
        await svc.bulk_moderate([target], 'restore')
        back = (await db.execute(
            select(BlogComment).where(BlogComment.id == target))).scalar_one()
        ok8 = back.status.value == 'approved'
        print(f'8. restore returns it to approved: {ok8}')
        if not ok8:
            bad.append('restore did not approve the comment')

        # 9. search finds by body, name and email
        s_body = await svc.list_comments(post_id=post.id, status=None, search='buy now',
                                         include_moderation_fields=True, comment_type='comment')
        s_name = await svc.list_comments(post_id=post.id, status=None, search='Sara',
                                         include_moderation_fields=True, comment_type='comment')
        s_mail = await svc.list_comments(post_id=post.id, status=None, search='sara@',
                                         include_moderation_fields=True, comment_type='comment')
        ok9 = len(s_body.items) == 1 and len(s_name.items) == 1 and len(s_mail.items) == 1
        print(f'9. search by body/name/email: {ok9}')
        if not ok9:
            bad.append(
                f'search missed: body={len(s_body.items)} '
                f'name={len(s_name.items)} email={len(s_mail.items)}')

        # 10. a search that matches nothing returns nothing, not everything
        s_none = await svc.list_comments(post_id=post.id, status=None,
                                         search='zzzz-no-such-thing',
                                         include_moderation_fields=True, comment_type='comment')
        ok10 = len(s_none.items) == 0
        print(f'10. no match returns nothing: {ok10}')
        if not ok10:
            bad.append('a search with no match returned rows')

        # 11. the reported total follows the filter, not just the page
        s_all = await svc.list_comments(post_id=post.id, status=None,
                                        include_moderation_fields=True, comment_type='comment')
        ok11 = s_all.total > s_body.total
        print(f'11. the total follows the filter: {ok11} (all={s_all.total}, search={s_body.total})')
        if not ok11:
            bad.append('the reported total ignored the search')

        # 12. bulk reports each outcome and survives a missing id
        res12 = await svc.bulk_moderate([made[1], made[2], uuid.uuid4()], 'approve')
        ok12 = (res12['ok'] == 2 and res12['failed'] == 1
                and len(res12['results']) == 3)
        print(f'12. bulk survives a missing id and says so: {ok12}')
        if not ok12:
            bad.append(f'bulk outcome wrong: {res12}')

        # 13. bulk refuses an unknown action outright
        ok13 = False
        try:
            await svc.bulk_moderate([made[0]], 'detonate')
            print('13. an unknown action was ACCEPTED (bad)')
        except Exception as e:
            ok13 = True
            print(f'13. an unknown action is refused: {type(e).__name__}')
        if not ok13:
            bad.append('bulk accepted an unknown action')

        await db.execute(delete(BlogComment).where(BlogComment.id.in_(made)))
        await db.execute(delete(BlogPost).where(BlogPost.id == post.id))
        await db.commit()
        print('14. cleaned up')
        if bad:
            print(f'MODERATION GAPS: {bad}')
            raise SystemExit(1)
    await eng.dispose()


asyncio.run(main())