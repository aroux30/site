"""Live slug checking: free, taken, reserved, and the editor's own slug."""
import asyncio, sys, io, uuid
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, 'C:/Users/Administrator/Desktop/site/backend')
import app.main
from sqlalchemy import select, delete
from app.core.database.session import _build_engine, async_sessionmaker
from app.modules.content.domain.models import CmsPage
from app.modules.content.schemas.content import CmsPageCreateRequest
from app.modules.content.application import cms_page_service as svc
from app.modules.users.domain.models import User

PREFIX = 'p1slug-'

async def main():
    eng = _build_engine(); S = async_sessionmaker(eng, expire_on_commit=False)
    bad: list[str] = []
    async with S() as db:
        me = (await db.execute(select(User).where(User.is_superuser == True).limit(1))).scalars().first()
        stale = (await db.execute(select(CmsPage).where(CmsPage.slug.like(PREFIX + '%')))).scalars().all()
        for p in stale:
            await db.execute(delete(p))
        await db.commit()
        made = []

        slug = f'{PREFIX}{uuid.uuid4().hex[:8]}'
        r = await svc.create_page(
            db, CmsPageCreateRequest(title='slug test', slug=slug, body_html='<p>x</p>'),
            author_id=me.id)
        made.append(uuid.UUID(str(r.id)))
        page_id = uuid.UUID(str(r.id))

        # 1. a free slug
        res1 = await svc.check_slug_available(db, f'{PREFIX}free')
        ok1 = res1['available'] and res1['reason'] is None
        print(f'1. a free slug is available: {ok1}')
        if not ok1:
            bad.append('a free slug reported unavailable')

        # 2. the slug this page already holds reads as taken to anyone else...
        res2 = await svc.check_slug_available(db, slug)
        ok2 = (not res2['available']) and res2['reason'] == 'taken'
        print(f'2. an existing slug reads taken: {ok2}')
        if not ok2:
            bad.append('a taken slug reported available')

        # 3. ...but not to the page that owns it, or every edit of a page would
        #    be blocked by its own unchanged slug
        res3 = await svc.check_slug_available(db, slug, exclude_id=page_id)
        ok3 = res3['available']
        print(f'3. excluded for the owning page: {ok3}')
        if not ok3:
            bad.append("a page's own slug reported taken to itself")

        # 4. a reserved store route
        reserved = next(iter(svc.RESERVED_SLUGS))
        res4 = await svc.check_slug_available(db, reserved)
        ok4 = (not res4['available']) and res4['reason'] == 'reserved'
        print(f'4. a reserved route is refused: {ok4}')
        if not ok4:
            bad.append('a reserved store route reported available')

        # 5. empty is not "available"
        res5 = await svc.check_slug_available(db, '   ')
        ok5 = (not res5['available']) and res5['reason'] == 'empty'
        print(f'5. blank is not available: {ok5}')
        if not ok5:
            bad.append('a blank slug reported available')

        # 6. the server still refuses a reserved slug on create
        ok6 = False
        try:
            await svc.create_page(
                db, CmsPageCreateRequest(title='bad', slug=reserved, body_html='<p>x</p>'),
                author_id=me.id)
            print('6. create accepted a reserved slug (bad)')
        except Exception:
            ok6 = True
            print('6. create refuses a reserved slug: ok')
        if not ok6:
            bad.append('create accepted a reserved slug')

        # 7. and a taken one is suffixed rather than rejected
        r7 = await svc.create_page(
            db, CmsPageCreateRequest(title='dup', slug=slug, body_html='<p>y</p>'),
            author_id=me.id)
        made.append(uuid.UUID(str(r7.id)))
        ok7 = r7.slug != slug and r7.slug.startswith(slug)
        print(f'7. a duplicate is suffixed, not rejected: {ok7}')
        if not ok7:
            bad.append('a duplicate slug was not suffixed')

        for pid in made:
            await db.execute(delete(CmsPage).where(CmsPage.id == pid))
        await db.commit()
        print('8. cleaned up')
        if bad:
            print(f'SLUG GUARD GAPS: {bad}')
            raise SystemExit(1)
        print('   (all checks above are counted; a printed True that is not true exits 1)')
    await eng.dispose()

asyncio.run(main())
