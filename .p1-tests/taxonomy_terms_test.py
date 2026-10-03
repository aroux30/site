"""Term editing: slug, description, parent and order, and the 'unchanged' trap."""
import asyncio, sys, io, uuid
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, 'C:/Users/Administrator/Desktop/site/backend')
import app.main
from sqlalchemy import select, delete
from app.core.database.session import _build_engine, async_sessionmaker
from app.modules.blog.domain.models import BlogCategory, BlogTag
from app.modules.blog.schemas.blog import (
    BlogCategoryUpdate, BlogTagUpdate, BlogCategoryCreate, BlogTagCreate,
)
from app.modules.blog.application.blog_service import BlogService
from app.modules.users.domain.models import User

async def main():
    eng = _build_engine(); S = async_sessionmaker(eng, expire_on_commit=False)
    made_cat, made_tag = [], []
    async with S() as db:
        me = (await db.execute(select(User).where(User.is_superuser == True).limit(1))).scalars().first()
        tag = 'p1term'
        # clear leftovers from an interrupted run
        for model, made in ((BlogCategory, made_cat), (BlogTag, made_tag)):
            stale = (await db.execute(select(model).where(model.slug.like(tag + '%')))).scalars().all()
            for s in stale:
                made.append(s.id)
                await db.delete(s)
            await db.commit()
        svc = BlogService(db)

        async def mkcat(name):
            c = await svc.create_category(BlogCategoryCreate(name=name, slug=f'{tag}-{name}-{uuid.uuid4().hex[:6]}'))
            made_cat.append(c.id); return c
        async def mktag(name):
            t = await svc.create_tag(BlogTagCreate(name=name, slug=f'{tag}-{name}-{uuid.uuid4().hex[:6]}'))
            made_tag.append(t.id); return t

        root = await mkcat('root')
        child = await mkcat('child')

        # 1. a tag can be described
        tg = await mktag('plain')
        r1 = await svc.update_tag(tg.id, BlogTagUpdate(description='برچسب برای اخبار تستی'))
        print(f'1. tag description saved: {r1.description == "برچسب برای اخبار تستی"}')

        # 2. renaming alone must NOT clear the description
        r2 = await svc.update_tag(tg.id, BlogTagUpdate(name='تغییرنام'))
        got = (await db.execute(select(BlogTag).where(BlogTag.id == tg.id))).scalar_one()
        print(f'2. rename keeps description: {got.description == "برچسب برای اخبار تستی"}')

        # 3. sending the description explicitly can clear it
        r3 = await svc.update_tag(tg.id, BlogTagUpdate(description=None))
        got3 = (await db.execute(select(BlogTag).where(BlogTag.id == tg.id))).scalar_one()
        print(f'3. explicit null clears it: {got3.description is None}')

        # 4. a blank string clears rather than storing whitespace
        r4 = await svc.update_tag(tg.id, BlogTagUpdate(description='   '))
        got4 = (await db.execute(select(BlogTag).where(BlogTag.id == tg.id))).scalar_one()
        print(f'4. blank string stored as null: {got4.description is None}')

        # 5. a category takes a parent and an order
        r5 = await svc.update_category(child.id, BlogCategoryUpdate(parent_id=root.id, position=7))
        print(f'5. category parent + position: {r5.parent_id == root.id and r5.position == 7}')

        # 6. re-parenting alone keeps the description
        r6a = await svc.update_category(child.id, BlogCategoryUpdate(description='توضیح دسته'))
        r6 = await svc.update_category(child.id, BlogCategoryUpdate(parent_id=None))
        got6 = (await db.execute(select(BlogCategory).where(BlogCategory.id == child.id))).scalar_one()
        print(f'6. re-parenting keeps the description: {got6.description == "توضیح دسته"} | now top-level: {got6.parent_id is None}')

        # 7. a category cycle is refused.
        #    child must be nested under root again first: test 6 detached it, and
        #    pointing root at a page that is not its descendant is a legal move,
        #    so testing it there would pass for the wrong reason.
        await svc.update_category(child.id, BlogCategoryUpdate(parent_id=root.id))
        try:
            await svc.update_category(root.id, BlogCategoryUpdate(parent_id=child.id))
            print('7. cycle ACCEPTED (bad)')
        except Exception as e:
            after = (await db.execute(select(BlogCategory).where(BlogCategory.id == root.id))).scalar_one()
            child2 = (await db.execute(select(BlogCategory).where(BlogCategory.id == child.id))).scalar_one()
            print(f'7. cycle refused: {type(e).__name__} | root untouched: {after.parent_id is None} '
                  f'| child still under root: {child2.parent_id == root.id}')

        await db.execute(delete(BlogCategory).where(BlogCategory.id.in_(made_cat)))
        await db.execute(delete(BlogTag).where(BlogTag.id.in_(made_tag)))
        await db.commit()
        print('8. cleaned up')
    await eng.dispose()

asyncio.run(main())
