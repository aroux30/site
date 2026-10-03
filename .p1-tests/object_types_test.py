"""object_types must be enforced, not decorative: a posts-only taxonomy cannot
be attached to a page, and an unknown type is rejected at the boundary."""
import asyncio, sys, io, uuid
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, 'C:/Users/Administrator/Desktop/site/backend')
import app.main
from sqlalchemy import delete, func, select
from app.core.database.session import _build_engine, async_sessionmaker
from app.modules.blog.domain.taxonomy_models import (
    CustomTaxonomy, CustomTaxonomyTerm, CmsPageTerm,
)
from app.modules.content.domain.models import CmsPage
from app.modules.blog.application.taxonomy_service import TaxonomyService
from app.modules.blog.api.wp_parity_routes import (
    admin_create_taxonomy, admin_create_taxonomy_term, admin_attach_page_terms,
)

PREFIX = 'p1obj-'

async def main():
    eng = _build_engine(); S = async_sessionmaker(eng, expire_on_commit=False)
    bad = 0
    async with S() as db:
        # clear leftovers
        for m, col in ((CustomTaxonomyTerm, CustomTaxonomyTerm.slug),
                       (CustomTaxonomy, CustomTaxonomy.slug)):
            old = (await db.execute(select(m.id).where(col.like(PREFIX + '%')))).scalars().all()
            if old:
                await db.execute(delete(CmsPageTerm).where(CmsPageTerm.term_id.in_(old)))
                await db.execute(delete(m).where(m.id.in_(old)))
        oldp = (await db.execute(select(CmsPage.id).where(CmsPage.slug.like(PREFIX + '%')))).scalars().all()
        if oldp:
            await db.execute(delete(CmsPageTerm).where(CmsPageTerm.page_id.in_(oldp)))
            await db.execute(delete(CmsPage).where(CmsPage.id.in_(oldp)))
        await db.commit()

        page = CmsPage(slug=f'{PREFIX}page-{uuid.uuid4().hex[:8]}', title='p', body_html='<p>x</p>')
        db.add(page)
        await db.flush()
        page_id = page.id

        tax = await admin_create_taxonomy(
            body={"name": f"{PREFIX}both", "hierarchical": False}, db=db, _=None)
        tax_id = uuid.UUID(str(tax["id"]))
        term = await admin_create_taxonomy_term(
            taxonomy_id=tax_id, body={"name": f"{PREFIX}term"}, db=db, _=None)
        term_id = uuid.UUID(str(term["id"]))
        await db.commit()
        print('0. page, taxonomy (both types) and term created')

        # 1. the default applies to both content types
        row = (await db.execute(select(CustomTaxonomy.object_types).where(
            CustomTaxonomy.id == tax_id))).scalar_one()
        print(f'1. default is both types: {sorted(row) == ["blog_post", "cms_page"]}')

        # 2. attaching to a page works when the taxonomy applies
        r2 = await admin_attach_page_terms(
            page_id=page_id, body={"term_ids": [str(term_id)]}, db=db,
            current_user={"sub": "x"}, _=None)
        print(f'2. attach to page: {r2["attached"] == 1}')

        # 3. the link is actually there
        n = (await db.execute(select(func.count()).select_from(CmsPageTerm).where(
            CmsPageTerm.page_id == page_id))).scalar_one()
        print(f'3. link stored: {n == 1}')

        # 4. narrow the taxonomy to posts only
        await TaxonomyService.update_taxonomy(
            db, tax_id, {"object_types": ["blog_post"]})
        row2 = (await db.execute(select(CustomTaxonomy.object_types).where(
            CustomTaxonomy.id == tax_id))).scalar_one()
        print(f'4. narrowed to posts only: {row2 == ["blog_post"]}')

        # 5. attaching that term to a page must now be refused — this is the
        #    whole point of the column
        ok5 = False
        try:
            await admin_attach_page_terms(
                page_id=page_id, body={"term_ids": [str(term_id)]}, db=db,
                current_user={"sub": "x"}, _=None)
            print('5. posts-only term attached to a page (bad)')
        except Exception as e:
            ok5 = True
            print(f'5. refused for a posts-only taxonomy: {type(e).__name__}')
        bad += 0 if ok5 else 1

        # 6. and the earlier link was left alone rather than half-written
        n2 = (await db.execute(select(func.count()).select_from(CmsPageTerm).where(
            CmsPageTerm.page_id == page_id))).scalar_one()
        print(f'6. nothing half-written: {n2 == 1}')

        # 7. an unknown type is rejected at the boundary
        ok7 = False
        try:
            await TaxonomyService.update_taxonomy(db, tax_id, {"object_types": ["page"]})
            print('7. unknown type ACCEPTED (bad)')
        except Exception as e:
            ok7 = True
            print(f'7. unknown type rejected: {type(e).__name__}')
        bad += 0 if ok7 else 1

        # 8. an empty list is rejected — "applies to nothing" is unreachable state
        ok8 = False
        try:
            await TaxonomyService.update_taxonomy(db, tax_id, {"object_types": []})
            print('8. empty list ACCEPTED (bad)')
        except Exception as e:
            ok8 = True
            print(f'8. empty list rejected: {type(e).__name__}')
        bad += 0 if ok8 else 1

        # 9. duplicates collapse
        r9 = await TaxonomyService.update_taxonomy(
            db, tax_id, {"object_types": ["blog_post", "blog_post", "cms_page"]})
        print(f'9. duplicates collapsed: {r9["object_types"] == ["blog_post", "cms_page"]}')

        # 10. an empty selection on a page clears its links
        await TaxonomyService.update_taxonomy(
            db, tax_id, {"object_types": ["blog_post", "cms_page"]})
        r10 = await admin_attach_page_terms(
            page_id=page_id, body={"term_ids": []}, db=db,
            current_user={"sub": "x"}, _=None)
        n3 = (await db.execute(select(func.count()).select_from(CmsPageTerm).where(
            CmsPageTerm.page_id == page_id))).scalar_one()
        print(f'10. empty attach clears: {n3 == 0}')

        # 11. a missing page is refused rather than storing links to nothing
        ok11 = False
        try:
            await admin_attach_page_terms(
                page_id=uuid.uuid4(), body={"term_ids": [str(term_id)]}, db=db,
                current_user={"sub": "x"}, _=None)
            print('11. missing page ACCEPTED (bad)')
        except Exception as e:
            ok11 = True
            print(f'11. missing page refused: {type(e).__name__}')
        bad += 0 if ok11 else 1

        await db.execute(delete(CmsPageTerm).where(
            CmsPageTerm.term_id == term_id))
        await db.execute(delete(CmsPage).where(CmsPage.id == page_id))
        await db.execute(delete(CustomTaxonomyTerm).where(CustomTaxonomyTerm.id == term_id))
        await db.execute(delete(CustomTaxonomy).where(CustomTaxonomy.id == tax_id))
        await db.commit()
        print('12. cleaned up')
        # A check that cannot fail cannot gate anything: a run where a
        # must-reject case was accepted has to exit non-zero, or every
        # negative test of it is theatre.
        if bad:
            print(f'REJECTION GAPS: {bad} case(s) that must be refused were accepted')
            raise SystemExit(1)
    await eng.dispose()

asyncio.run(main())
