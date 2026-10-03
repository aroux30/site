"""Comment guards: require_name_email, the hourly ceiling, the daily ceiling.

Each is a site option that only counts as implemented if the *server* refuses
what the option says to refuse — a form hint is not enforcement, because the
API is the same endpoint the form posts to. So every case here drives the real
create path with the option set, and with it cleared.
"""
import asyncio, sys, io, uuid
from datetime import datetime, UTC, timedelta
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, 'C:/Users/Administrator/Desktop/site/backend')
import app.main
from sqlalchemy import delete, select
from app.core.database.session import _build_engine, async_sessionmaker
from app.modules.blog.domain.models import (
    BlogPost, BlogPostStatus, PostVisibility, BlogComment,
)
from app.modules.blog.schemas.blog import BlogCommentCreate
from app.modules.blog.application.comment_service import CommentService
from app.modules.users.domain.models import User

TAG = 'p1guard'
bad: list[str] = []


async def set_option(db, key: str, value: str) -> None:
    """Write an option through the service's own writer.

    The reader and the writer both speak `site_options` (option_key /
    option_value). Hand-writing a `site_settings` row put the value in a table
    nothing reads, so the guard silently kept its default and the test looked
    like a broken guard rather than a broken fixture.
    """
    from app.modules.settings.application.site_options_service import SiteOptionsService

    await SiteOptionsService.set(db, key, value)


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

        async def mkpost(suffix):
            p = BlogPost(title=f'{TAG} {suffix}', slug=f'{TAG}-{suffix}-{uuid.uuid4().hex[:8]}',
                         content='x', excerpt=None, cover_image_url=None, author_id=me.id,
                         status=BlogPostStatus.PUBLISHED, published_at=datetime.now(UTC),
                         visibility=PostVisibility.PUBLIC, is_featured=False,
                         allow_comments=True, post_format='standard', category_id=None)
            db.add(p); await db.flush(); return p

        async def guest(name=None, email=None, ip=None, n=0):
            """A guest comment, with the flood check and every other guard
            satisfied so only the one under test can refuse it."""
            return await svc.create_comment(
                BlogCommentCreate(
                    post_id=post.id,
                    content=f'{TAG} guest {n}',
                    author_name=name,
                    author_email=email,
                ),
                author_ip=ip,
            )

        # Every rate check needs an address with no comment history: the
        # ceilings count *every* comment from the address, so reusing one would
        # measure the earlier cases rather than the ceiling. A fresh /24 per
        # scenario keeps them independent and readable.
        counter = {'n': 0}

        def fresh_ip() -> str:
            counter['n'] += 1
            return f'198.51.100.{counter["n"]}'

        # --- require_name_email -------------------------------------------
        post = await mkpost('main')
        await set_option(db, 'require_name_email', '1')
        await set_option(db, 'comment_flood_seconds', '0')   # isolate this guard
        await set_option(db, 'comments_per_hour', '0')
        await set_option(db, 'comments_per_day', '0')

        refused = False
        try:
            await guest(ip=fresh_ip(), n=1)
            print('1. a nameless guest comment was accepted (bad)')
        except Exception:
            refused = True
            print('1. a nameless guest comment is refused: ok')
        if not refused:
            bad.append('require_name_email let a nameless guest comment through')

        refused2 = False
        try:
            await guest(name='Ali', email=None, ip=fresh_ip(), n=2)
            print('2. an email-less guest comment was accepted (bad)')
        except Exception:
            refused2 = True
            print('2. an email-less guest comment is refused: ok')
        if not refused2:
            bad.append('require_name_email let an email-less comment through')

        # a complete guest still gets in — the flag must not block everyone
        ok = await guest(name='Sara', email='sara@example.com', ip=fresh_ip(), n=3)
        ok3 = ok is not None
        print(f'3. a complete guest comment still gets through: {ok3}')
        if not ok3:
            bad.append('require_name_email blocked a complete guest comment')

        # cleared, the loose form works again
        await set_option(db, 'require_name_email', '0')
        ok4 = await guest(ip=fresh_ip(), n=4)
        ok4 = ok4 is not None
        print(f'4. with the flag off a loose guest comment is fine: {ok4}')
        if not ok4:
            bad.append('require_name_email stayed on after being cleared')

        # a signed-in commenter is exempt — they already have both
        await set_option(db, 'require_name_email', '1')
        signed = await svc.create_comment(
            BlogCommentCreate(post_id=post.id, content=f'{TAG} signed in'),
            author_id=me.id,
        )
        ok5 = signed is not None
        print(f'5. a signed-in commenter is exempt: {ok5}')
        if not ok5:
            bad.append('require_name_email blocked a signed-in commenter')
        await set_option(db, 'require_name_email', '0')

        # --- rate ceilings --------------------------------------------------
        ip = fresh_ip()
        await set_option(db, 'comments_per_hour', '3')
        await set_option(db, 'comments_per_day', '0')
        await set_option(db, 'comment_flood_seconds', '0')  # isolate the ceiling
        made = 0
        hit = False
        for i in range(6):
            try:
                await guest(name='Bot', email='bot@example.com', ip=ip, n=100 + i)
                made += 1
            except Exception:
                hit = True
                break
        ok6 = made == 3 and hit
        print(f'6. the hourly ceiling holds at 3: {ok6} (accepted {made} then refused)')
        if not ok6:
            bad.append(f'the hourly ceiling let {made} through, expected 3')

        # a different address is unaffected
        other = await guest(name='Other', email='other@example.com',
                            ip=fresh_ip(), n=200)
        ok7 = other is not None
        print(f'7. another address is unaffected: {ok7}')
        if not ok7:
            bad.append('the hourly ceiling leaked to another address')

        # the daily ceiling, on top
        await set_option(db, 'comments_per_hour', '0')
        await set_option(db, 'comments_per_day', '2')
        ip2 = fresh_ip()
        made2 = 0
        hit2 = False
        for i in range(5):
            try:
                await guest(name='Bot2', email='bot2@example.com', ip=ip2, n=300 + i)
                made2 += 1
            except Exception:
                hit2 = True
                break
        ok8 = made2 == 2 and hit2
        print(f'8. the daily ceiling holds at 2: {ok8} (accepted {made2} then refused)')
        if not ok8:
            bad.append(f'the daily ceiling let {made2} through, expected 2')

        # 0 disables each one
        await set_option(db, 'comments_per_day', '0')
        for i in range(4):
            await guest(name='Bot3', email='bot3@example.com', ip=ip2, n=400 + i)
        ok9 = True
        print(f'9. a ceiling of 0 disables the check: {ok9}')
        if not ok9:
            bad.append('a ceiling of 0 still refused')

        # cleanup
        await set_option(db, 'comment_flood_seconds', '15')
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
        await db.commit()
        print('10. cleaned up')
        if bad:
            print(f'GUARD GAPS: {bad}')
            raise SystemExit(1)
    await eng.dispose()


asyncio.run(main())