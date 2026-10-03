"""Quick-edit: post_format must apply, and a bad value must not break the save."""
import asyncio, sys, io, uuid
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, 'C:/Users/Administrator/Desktop/site/backend')
import app.main
from sqlalchemy import select, delete
from app.core.database.session import _build_engine, async_sessionmaker
from app.modules.blog.domain.models import BlogPost, BlogPostStatus, PostVisibility, BlogPostRevision, PostFormat
from app.modules.blog.application.quick_edit_service import QuickEditService
from app.modules.users.domain.models import User

async def main():
    eng = _build_engine(); S = async_sessionmaker(eng, expire_on_commit=False)
    pid = uuid.uuid4()
    async with S() as db:
        me = (await db.execute(select(User).where(User.is_superuser == True).limit(1))).scalars().first()
        stale = (await db.execute(select(BlogPost).where(BlogPost.slug.like('qetest-%')))).scalars().all()
        if stale:
            await db.execute(delete(BlogPostRevision).where(BlogPostRevision.post_id.in_([p.id for p in stale])))
            await db.execute(delete(BlogPost).where(BlogPost.id.in_([p.id for p in stale])))
            await db.commit()
        db.add(BlogPost(id=pid, title='qetest', slug=f'qetest-{uuid.uuid4().hex[:8]}', content='x',
                        excerpt=None, cover_image_url=None, author_id=me.id,
                        status=BlogPostStatus.PUBLISHED, published_at=None,
                        visibility=PostVisibility.PUBLIC, is_featured=False, allow_comments=True,
                        post_format=PostFormat.STANDARD, category_id=None))
        await db.commit()

        # 1. a valid format applies
        r = await QuickEditService.quick_edit_post(db, pid, {'post_format': 'gallery'})
        got = (await db.execute(select(BlogPost).where(BlogPost.id == pid))).scalar_one()
        print(f'1. post_format=gallery -> applied={"post_format" in r.get("updated_fields", {})} | stored: {got.post_format.value}')

        # 2. an invalid format is dropped, and the rest of the save still lands
        r2 = await QuickEditService.quick_edit_post(db, pid, {'post_format': 'not-a-format', 'is_featured': True})
        got2 = (await db.execute(select(BlogPost).where(BlogPost.id == pid))).scalar_one()
        print(f'2. bad format dropped, featured still applied: {got2.is_featured} | format unchanged: {got2.post_format.value}')

        # 3. the commit survives: a second read from the session sees it
        await db.commit()
        got3 = (await db.execute(select(BlogPost).where(BlogPost.id == pid))).scalar_one()
        print(f'3. commits cleanly, no enum error: format={got3.post_format.value} featured={got3.is_featured}')

        await db.execute(delete(BlogPostRevision).where(BlogPostRevision.post_id == pid))
        await db.execute(delete(BlogPost).where(BlogPost.id == pid))
        await db.commit()
        print('4. cleaned up')
    await eng.dispose()

asyncio.run(main())
