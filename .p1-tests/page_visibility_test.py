"""Page cover, review status, private and password-protected pages."""
import asyncio, sys, io, uuid
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, 'C:/Users/Administrator/Desktop/site/backend')
import app.main
from sqlalchemy import select, delete
from app.core.database.session import _build_engine, async_sessionmaker
from app.modules.content.domain.models import CmsPage, PageStatus, PageVisibility
from app.modules.content.schemas.content import (
    CmsPageCreateRequest, CmsPageUpdateRequest,
)
from app.modules.content.application import cms_page_service as svc
from app.modules.users.domain.models import User

PREFIX = 'p1vis-'

async def main():
    eng = _build_engine(); S = async_sessionmaker(eng, expire_on_commit=False)
    async with S() as db:
        me = (await db.execute(select(User).where(User.is_superuser == True).limit(1))).scalars().first()
        stale = (await db.execute(select(CmsPage).where(CmsPage.slug.like(PREFIX + '%')))).scalars().all()
        for p in stale:
            await db.execute(delete(p))
        await db.commit()
        made = []

        async def make(**kw):
            r = await svc.create_page(
                db, CmsPageCreateRequest(slug=f'{PREFIX}{uuid.uuid4().hex[:8]}', **kw),
                author_id=me.id)
            made.append(uuid.UUID(str(r.id)))
            return r

        # 1. a cover image
        r1 = await make(title='t1', body_html='<p>x</p>', cover_image_url='/media/a.jpg')
        print(f'1. cover image saved: {r1.cover_image_url == "/media/a.jpg"}')

        # 2. the review status exists
        r2 = await make(title='t2', body_html='<p>x</p>', status=PageStatus.PENDING_REVIEW)
        print(f'2. pending_review stored: {str(r2.status).lower().endswith("pending_review") or r2.status == "pending_review"}')

        # 3. a review page is not served publicly
        leaks = []
        ok3 = False
        try:
            await svc.get_page_by_slug(db, r2.slug)
            print('3. pending_review served publicly (bad)')
        except Exception:
            ok3 = True
            print('3. pending_review not served: ok')
        leaks.append("pending_review served") if not ok3 else None

        # 4. a published page is
        r4 = await make(title='t4', body_html='<p>x</p>', status=PageStatus.PUBLISHED)
        got4 = await svc.get_page_by_slug(db, r4.slug)
        print(f'4. published served: {got4.id == r4.id}')

        # 5. private + published is NOT served — this is the field's whole job
        await svc.update_page(
            db, uuid.UUID(str(r4.id)),
            CmsPageUpdateRequest(visibility=PageVisibility.PRIVATE), editor_id=me.id)
        ok5 = False
        try:
            await svc.get_page_by_slug(db, r4.slug)
            print('5. private page served publicly (bad)')
        except Exception:
            ok5 = True
            print('5. private page not served: ok')
        leaks.append("private page served") if not ok5 else None

        # 6. but the admin can still read it
        admin_view = await svc.get_page_by_slug(db, r4.slug, only_published=False)
        print(f'6. admin can still read a private page: {admin_view.id == r4.id}')

        # 7. back to public and it is served again
        await svc.update_page(
            db, uuid.UUID(str(r4.id)),
            CmsPageUpdateRequest(visibility=PageVisibility.PUBLIC), editor_id=me.id)
        print(f'7. public again: {(await svc.get_page_by_slug(db, r4.slug)).id == r4.id}')

        # 8. a password is hashed, never returned
        r8 = await make(title='t8', body_html='<p>secret</p>', status=PageStatus.PUBLISHED,
                        visibility=PageVisibility.PASSWORD, visibility_password='hunter2')
        stored = (await db.execute(select(CmsPage).where(
            CmsPage.id == uuid.UUID(str(r8.id))))).scalar_one()
        # A printed assertion is not a gate: this fixture has to decide the
        # exit code, or removing the hashing still reports success. Counted
        # into `leaks` like the visibility cases.
        ok8 = (
            stored.visibility_password_hash is not None
            and "hunter2" not in (stored.visibility_password_hash or "")
            and len(stored.visibility_password_hash) > 20
        )
        print(f'8. password hashed in the database: {ok8}')
        print(f'   response reports a password is set: {r8.visibility_password_set is True}')
        # The hash must not be on the response object at all.
        printed = getattr(r8, "visibility_password_hash", None)
        ok8b = printed is None
        print(f'   response carries no hash field: {ok8b}')
        if not (ok8 and ok8b):
            leaks.append("password stored or returned in the clear")

        # 9. an unrelated save must not clear the password
        await svc.update_page(db, uuid.UUID(str(r8.id)),
                              CmsPageUpdateRequest(title='renamed'), editor_id=me.id)
        stored2 = (await db.execute(select(CmsPage).where(
            CmsPage.id == uuid.UUID(str(r8.id))))).scalar_one()
        print(f'9. a rename keeps the password: {stored2.visibility_password_hash is not None}')

        # 10. switching away from password drops it
        await svc.update_page(db, uuid.UUID(str(r8.id)),
                              CmsPageUpdateRequest(visibility=PageVisibility.PUBLIC), editor_id=me.id)
        stored3 = (await db.execute(select(CmsPage).where(
            CmsPage.id == uuid.UUID(str(r8.id))))).scalar_one()
        print(f'10. leaving password clears the hash: {stored3.visibility_password_hash is None}')

        for pid in made:
            await db.execute(delete(CmsPage).where(CmsPage.id == pid))
        await db.commit()
        print('11. cleaned up')
        if leaks:
            print(f'VISIBILITY LEAKS: {leaks}')
            raise SystemExit(1)
    await eng.dispose()

asyncio.run(main())
