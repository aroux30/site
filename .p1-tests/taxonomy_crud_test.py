"""Taxonomy and term editing/deleting, including the cascade a delete implies."""
import asyncio, sys, io, uuid
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, 'C:/Users/Administrator/Desktop/site/backend')
import app.main
from sqlalchemy import select, delete
from app.core.database.session import _build_engine, async_sessionmaker
from app.modules.blog.domain.taxonomy_models import (
    CustomTaxonomy, CustomTaxonomyTerm, BlogPostTerm,
)
from app.modules.blog.application.taxonomy_service import TaxonomyService
from app.modules.blog.api.wp_parity_routes import (
    admin_create_taxonomy, admin_create_taxonomy_term,
)

PREFIX = 'p1crud-'

async def main():
    eng = _build_engine(); S = async_sessionmaker(eng, expire_on_commit=False)
    async with S() as db:
        # clear leftovers
        old_t = (await db.execute(select(CustomTaxonomyTerm.id).where(
            CustomTaxonomyTerm.slug.like(PREFIX + '%')))).scalars().all()
        old_x = (await db.execute(select(CustomTaxonomy.id).where(
            CustomTaxonomy.slug.like(PREFIX + '%')))).scalars().all()
        for tid in old_t:
            await db.execute(delete(BlogPostTerm).where(BlogPostTerm.term_id == tid))
        if old_t: await db.execute(delete(CustomTaxonomyTerm).where(CustomTaxonomyTerm.id.in_(old_t)))
        if old_x: await db.execute(delete(CustomTaxonomy).where(CustomTaxonomy.id.in_(old_x)))
        await db.commit()

        # Creation lives in the route handlers; the service only holds
        # update/delete. Calling the handlers exercises the path the UI takes.
        tax = await admin_create_taxonomy(
            body={"name": f"{PREFIX}tax", "hierarchical": True}, db=db, _=None)
        tax_id = uuid.UUID(str(tax["id"]))
        parent = await admin_create_taxonomy_term(
            taxonomy_id=tax_id, body={"name": f"{PREFIX}parent"}, db=db, _=None)
        child = await admin_create_taxonomy_term(
            taxonomy_id=tax_id,
            body={"name": f"{PREFIX}child", "parent_id": str(parent["id"])},
            db=db, _=None)
        parent_id = uuid.UUID(str(parent["id"])); child_id = uuid.UUID(str(child["id"]))
        print('0. taxonomy + parent/child created')

        # 1. rename the taxonomy
        r1 = await TaxonomyService.update_taxonomy(db, tax_id, {"name": f"{PREFIX}renamed"})
        print(f'1. taxonomy renamed: {r1["name"] == f"{PREFIX}renamed"}')

        # 2. a term can be renamed and described
        r2 = await TaxonomyService.update_term(db, child_id, {"name": f"{PREFIX}child2",
                                                  "description": "توضیح ترم"})
        print(f'2. term renamed + described: {r2["name"] == f"{PREFIX}child2" and r2["description"] == "توضیح ترم"}')

        # 3. re-parenting sticks
        r3 = await TaxonomyService.update_term(db, child_id, {"parent_id": None})
        print(f'3. re-parented to top level: {r3["parent_id"] is None}')

        # 4. renaming alone keeps the description
        r4 = await TaxonomyService.update_term(db, child_id, {"name": f"{PREFIX}child3"})
        print(f'4. rename keeps description: {r4["description"] == "توضیح ترم"}')

        # 5. deleting a term reports what it unlinked
        r5 = await TaxonomyService.delete_term(db, child_id)
        left = (await db.execute(select(CustomTaxonomyTerm).where(
            CustomTaxonomyTerm.id == child_id))).scalars().first()
        print(f'5. term deleted: {left is None} | reported: {r5}')

        # 6. deleting the taxonomy takes its terms with it
        r6 = await TaxonomyService.delete_taxonomy(db, tax_id)
        terms_left = (await db.execute(select(CustomTaxonomyTerm.id).where(
            CustomTaxonomyTerm.taxonomy_id == tax_id))).scalars().first()
        tax_left = (await db.execute(select(CustomTaxonomy.id).where(
            CustomTaxonomy.id == tax_id))).scalars().first()
        print(f'6. taxonomy deleted: {tax_left is None} | its terms too: {terms_left is None} | reported: {r6}')

        # cleanup anything left
        for tid in (await db.execute(select(CustomTaxonomyTerm.id).where(
                CustomTaxonomyTerm.slug.like(PREFIX + '%')))).scalars().all():
            await db.execute(delete(BlogPostTerm).where(BlogPostTerm.term_id == tid))
        await db.execute(delete(CustomTaxonomyTerm).where(
            CustomTaxonomyTerm.slug.like(PREFIX + '%')))
        await db.execute(delete(CustomTaxonomy).where(CustomTaxonomy.slug.like(PREFIX + '%')))
        await db.commit()
        print('7. cleaned up')
    await eng.dispose()

asyncio.run(main())
