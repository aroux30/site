"""Page tree: a parent can be set, a cycle is refused, and sibling order sticks."""
import asyncio, sys, io, uuid
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, 'C:/Users/Administrator/Desktop/site/backend')
import app.main
from sqlalchemy import select, delete
from app.core.database.session import _build_engine, async_sessionmaker
from app.modules.content.domain.models import CmsPage
from app.modules.content.schemas.content import CmsPageCreateRequest, CmsPageUpdateRequest
from app.modules.content.application import cms_page_service as svc_mod
from app.modules.users.domain.models import User

async def main():
    eng = _build_engine(); S = async_sessionmaker(eng, expire_on_commit=False)
    made = []
    async with S() as db:
        me = (await db.execute(select(User).where(User.is_superuser == True).limit(1))).scalars().first()
        stale = (await db.execute(select(CmsPage).where(CmsPage.slug.like('p1tree-%')))).scalars().all()
        if stale:
            await db.execute(delete(CmsPage).where(CmsPage.id.in_([p.id for p in stale])))
            await db.commit()

        async def make(title):
            slug = f'p1tree-{title}-{uuid.uuid4().hex[:8]}'
            page = await svc_mod.create_page(
                db, CmsPageCreateRequest(title=title, slug=slug, body_html='<p>x</p>', locale='fa'),
                author_id=me.id)
            made.append(page.id)
            return page

        root = await make('root')
        child = await make('child')
        grand = await make('grand')

        # 1. set a parent
        r = await svc_mod.update_page(db, child.id, CmsPageUpdateRequest(parent_id=root.id), editor_id=me.id)
        print(f'1. parent set: {r.parent_id == root.id}')

        # 2. read back after a fresh query
        got = (await db.execute(select(CmsPage).where(CmsPage.id == child.id))).scalar_one()
        print(f'2. parent persisted in the database: {got.parent_id == root.id}')

        # 3. a grandchild under the child is fine
        r3 = await svc_mod.update_page(db, grand.id, CmsPageUpdateRequest(parent_id=child.id), editor_id=me.id)
        print(f'3. nested deeper (grandchild -> child): {r3.parent_id == child.id}')

        # 4. a cycle must be refused: making the root a child of its own grandchild
        try:
            await svc_mod.update_page(db, root.id, CmsPageUpdateRequest(parent_id=grand.id), editor_id=me.id)
            print('4. cycle ACCEPTED (bad)')
        except Exception as e:
            after = (await db.execute(select(CmsPage).where(CmsPage.id == root.id))).scalar_one()
            print(f'4. cycle refused: {type(e).__name__} | root still top-level: {after.parent_id is None}')

        # 5. a page cannot be its own parent
        try:
            await svc_mod.update_page(db, child.id, CmsPageUpdateRequest(parent_id=child.id), editor_id=me.id)
            print('5. self-parent ACCEPTED (bad)')
        except Exception as e:
            print(f'5. self-parent refused: {type(e).__name__}')

        # 6. sibling order sticks, and is independent of the parent
        await svc_mod.update_page(db, grand.id, CmsPageUpdateRequest(menu_order=42), editor_id=me.id)
        g2 = (await db.execute(select(CmsPage).where(CmsPage.id == grand.id))).scalar_one()
        print(f'6. menu_order stored: {g2.menu_order == 42}')

        # 7. clearing the parent works (null, not "")
        r7 = await svc_mod.update_page(db, grand.id, CmsPageUpdateRequest(parent_id=None), editor_id=me.id)
        g3 = (await db.execute(select(CmsPage).where(CmsPage.id == grand.id))).scalar_one()
        print(f'7. parent cleared to null: {g3.parent_id is None}')

        await db.execute(delete(CmsPage).where(CmsPage.id.in_(made)))
        await db.commit()
        print('8. test rows cleaned up')
    await eng.dispose()

asyncio.run(main())
