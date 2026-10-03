"""Remove rows left behind by an interrupted P1 fixture run.

An interrupted run leaves test categories and posts behind, and a later run
then fails on the slug unique index — or, worse, trips a genuine pre-existing
bug (a lazy-load under async) and gets misread as a regression of the code
under test. Both happened here. Run this before a fixture test, not instead
of fixing the fixture.
"""
import asyncio, sys, io, uuid
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, 'C:/Users/Administrator/Desktop/site/backend')
import app.main
from sqlalchemy import select, delete, or_
from app.core.database.session import _build_engine, async_sessionmaker
from app.modules.blog.domain.models import BlogPost, BlogCategory, BlogPostRevision

# The fixture category's slug is 'bulk-test-x'; posts under it are the leftovers.
SLUG_PREFIXES = ('bulktest-%', 'pubdate-%', 'bulk-test-%')
CAT_SLUGS = ('bulk-test-x',)

async def main():
    eng = _build_engine()
    S = async_sessionmaker(eng, expire_on_commit=False)
    async with S() as db:
        posts = (await db.execute(
            select(BlogPost).where(or_(*[BlogPost.slug.like(p) for p in SLUG_PREFIXES]))
        )).scalars().all()
        if posts:
            await db.execute(delete(BlogPostRevision).where(
                BlogPostRevision.post_id.in_([p.id for p in posts])))
            await db.execute(delete(BlogPost).where(BlogPost.id.in_([p.id for p in posts])))
        cats = (await db.execute(
            select(BlogCategory).where(
                or_(BlogCategory.slug.like('bulk-test%'),
                    BlogCategory.name.like('BULK-TEST'))
            )
        )).scalars().all()
        if cats:
            await db.execute(delete(BlogCategory).where(
                BlogCategory.id.in_([c.id for c in cats])))
        await db.commit()
        print(f'cleaned {len(posts)} post(s), {len(cats)} category(ies)')
    await eng.dispose()

asyncio.run(main())
