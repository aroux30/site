"""Term search must filter server-side without breaking the usage counts."""
import asyncio, sys, io, uuid
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, 'C:/Users/Administrator/Desktop/site/backend')
import app.main
from sqlalchemy import select, delete
from app.core.database.session import _build_engine, async_sessionmaker
from app.modules.blog.domain.taxonomy_models import CustomTaxonomy, CustomTaxonomyTerm
from app.modules.blog.api.wp_parity_routes import (
    admin_create_taxonomy, admin_create_taxonomy_term, admin_list_taxonomy_terms,
)

PREFIX = 'p1search-'

async def main():
    eng = _build_engine(); S = async_sessionmaker(eng, expire_on_commit=False)
    async with S() as db:
        old = (await db.execute(select(CustomTaxonomyTerm.id).where(
            CustomTaxonomyTerm.slug.like(PREFIX + '%')))).scalars().all()
        oldx = (await db.execute(select(CustomTaxonomy.id).where(
            CustomTaxonomy.slug.like(PREFIX + '%')))).scalars().all()
        if old: await db.execute(delete(CustomTaxonomyTerm).where(CustomTaxonomyTerm.id.in_(old)))
        if oldx: await db.execute(delete(CustomTaxonomy).where(CustomTaxonomy.id.in_(oldx)))
        await db.commit()

        tax = await admin_create_taxonomy(body={"name": f"{PREFIX}tax"}, db=db, _=None)
        tax_id = uuid.UUID(str(tax["id"]))
        made = {}
        # Names chosen so a search term matches one name, one slug and one
        # description — all three are supposed to be searched.
        for name, slug, desc in [
            (f"{PREFIX}قرمز", "p1search-red", "رنگ گرم"),
            (f"{PREFIX}آبی", "p1search-blue", "رنگ سرد"),
            (f"{PREFIX}سبز", "p1search-green", "رنگ طبیعی و گرم"),
        ]:
            t = await admin_create_taxonomy_term(
                taxonomy_id=tax_id,
                body={"name": name, "slug": slug, "description": desc}, db=db, _=None)
            made[slug] = uuid.UUID(str(t["id"]))
        await db.commit()
        print(f'0. {len(made)} terms created')

        async def names(search=None):
            rows = await admin_list_taxonomy_terms(
                taxonomy_id=tax_id, search=search, db=db, _=None)
            return [r["name"] for r in rows]

        # 1. no search returns everything
        all_names = await names()
        print(f'1. no search returns all: {len(all_names) == 3}')

        # 2. search by name
        got = await names("قرمز")
        print(f'2. search by name: {len(got) == 1 and "قرمز" in got[0]}')

        # 3. search by slug
        got3 = await names("blue")
        print(f'3. search by slug: {len(got3) == 1 and "آبی" in got3[0]}')

        # 4. search by description — "گرم" appears in two
        got4 = await names("گرم")
        print(f'4. search by description finds both: {len(got4) == 2}')

        # 5. a term that does not exist is an empty list, not everything
        got5 = await names("هیچ‌چیز-این‌طور")
        print(f'5. no match returns empty: {got5 == []}')

        # 6. an empty or whitespace search is not a filter
        print(f'6. blank search returns all: {len(await names("   ")) == 3}')

        # 7. every row still carries its usage count after filtering
        rows = await admin_list_taxonomy_terms(taxonomy_id=tax_id, search="گرم", db=db, _=None)
        print(f'7. usage count present on filtered rows: {all("post_count" in r for r in rows)}')

        # 8. the search is case-insensitive on latin slugs
        got8 = await names("BLUE")
        print(f'8. case-insensitive: {len(got8) == 1}')

        for tid in made.values():
            await db.execute(delete(CustomTaxonomyTerm).where(CustomTaxonomyTerm.id == tid))
        await db.execute(delete(CustomTaxonomy).where(CustomTaxonomy.id == tax_id))
        await db.commit()
        print('9. cleaned up')
    await eng.dispose()

asyncio.run(main())
