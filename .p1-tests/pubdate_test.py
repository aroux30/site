import asyncio, sys, io, uuid
from datetime import datetime, UTC
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, 'C:/Users/Administrator/Desktop/site/backend')
import app.main  # register all models
from sqlalchemy import select, delete
from app.core.database.session import _build_engine, async_sessionmaker
from app.modules.blog.domain.models import BlogPost, BlogPostStatus, PostVisibility, BlogPostRevision
from app.modules.blog.schemas.blog import BlogPostUpdate
from app.modules.blog.application.blog_service import BlogService
from app.modules.users.domain.models import User

PAST   = datetime(2024, 3, 15, 9, 0, tzinfo=UTC)
FUTURE = datetime(2030, 1, 1, 9, 0, tzinfo=UTC)

async def main():
    eng = _build_engine()
    S = async_sessionmaker(eng, expire_on_commit=False)
    ids = []
    async with S() as db:
        me = (await db.execute(select(User).where(User.is_superuser == True).limit(1))).scalars().first()
        if me is None:
            print('no superuser available'); return
        stale = (await db.execute(select(BlogPost).where(BlogPost.slug.like('pubdate-%')))).scalars().all()
        if stale:
            await db.execute(delete(BlogPostRevision).where(BlogPostRevision.post_id.in_([p.id for p in stale])))
            await db.execute(delete(BlogPost).where(BlogPost.id.in_([p.id for p in stale])))
            await db.commit()

        for i in range(2):
            pid = uuid.uuid4(); ids.append(pid)
            db.add(BlogPost(id=pid, title=f'pubdate-{i}', slug=f'pubdate-{i}-{uuid.uuid4().hex[:8]}',
                            content='x', excerpt=None, cover_image_url=None, author_id=me.id,
                            status=BlogPostStatus.PUBLISHED, published_at=datetime(2026,1,1,tzinfo=UTC),
                            visibility=PostVisibility.PUBLIC, is_featured=False, allow_comments=True,
                            post_format='standard', category_id=None))
        await db.commit()
        svc = BlogService(db)

        # 1. schema accepts a past date
        upd = BlogPostUpdate(published_at=PAST)
        print('1. schema accepts a past published_at:', upd.published_at == PAST)

        # 2. the service stores it
        r = await svc.update_post(ids[0], BlogPostUpdate(published_at=PAST), actor_id=me.id)
        got = (await db.execute(select(BlogPost).where(BlogPost.id == ids[0]))).scalar_one()
        print(f'2. stored past date: {got.published_at.isoformat()} == {PAST.isoformat()} -> {got.published_at == PAST}')

        # 3. publishing with no date falls back to now (unchanged behaviour)
        r2 = await svc.update_post(ids[1], BlogPostUpdate(status='draft'), actor_id=me.id)
        r3 = await svc.update_post(ids[1], BlogPostUpdate(status='published'), actor_id=me.id)
        got2 = (await db.execute(select(BlogPost).where(BlogPost.id == ids[1]))).scalar_one()
        print(f'3. publish without a date stamps now: {got2.published_at is not None}')

        # 4. an explicit past date is NOT overwritten by the publish branch
        got3 = (await db.execute(select(BlogPost).where(BlogPost.id == ids[0]))).scalar_one()
        r4 = await svc.update_post(ids[0], BlogPostUpdate(status='published'), actor_id=me.id)
        got4 = (await db.execute(select(BlogPost).where(BlogPost.id == ids[0]))).scalar_one()
        print(f'4. explicit past date survives a republish: {got4.published_at == PAST}')

        # 5. a future scheduled date is still the scheduling mechanism
        r5 = await svc.update_post(ids[1], BlogPostUpdate(scheduled_for=FUTURE), actor_id=me.id)
        got5 = (await db.execute(select(BlogPost).where(BlogPost.id == ids[1]))).scalar_one()
        print(f'5. scheduled_for stored separately: {got5.scheduled_for == FUTURE} | published_at untouched: {got5.published_at == got2.published_at}')

        await db.execute(delete(BlogPostRevision).where(BlogPostRevision.post_id.in_(ids)))
        await db.execute(delete(BlogPost).where(BlogPost.slug.like('pubdate-%')))
        await db.commit()
        print('6. test rows cleaned up')
    await eng.dispose()

asyncio.run(main())
