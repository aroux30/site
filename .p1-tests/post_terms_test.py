"""Attaching custom terms to a post must replace, not accumulate, the set."""
import asyncio, sys, io, uuid
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, 'C:/Users/Administrator/Desktop/site/backend')
import app.main
from sqlalchemy import select, delete, func
from app.core.database.session import _build_engine, async_sessionmaker
from app.modules.blog.domain.models import (
    BlogPost, BlogPostStatus, PostVisibility, BlogPostRevision,
)
from app.modules.blog.domain.taxonomy_models import (
    BlogPostTerm, CustomTaxonomy, CustomTaxonomyTerm,
)
from app.modules.blog.api.wp_parity_routes import admin_attach_post_terms
from app.modules.users.domain.models import User

PREFIX = 'p1attach-'


async def main():
    eng = _build_engine()
    S = async_sessionmaker(eng, expire_on_commit=False)
    async with S() as db:
        me = (await db.execute(
            select(User).where(User.is_superuser == True).limit(1))).scalars().first()
        payload = {"sub": str(me.id), "roles": ["super_admin"],
                   "permissions": ["*"], "is_superuser": True}

        # Clear anything an interrupted earlier run left behind. Done first and
        # committed on its own, so the ids collected below are only the rows this
        # run creates — mixing the two is how a fixture ends up deleting its own
        # data and then wondering why the route says "not found".
        old_posts = (await db.execute(
            select(BlogPost.id).where(BlogPost.slug.like(PREFIX + '%')))).scalars().all()
        old_terms = (await db.execute(
            select(CustomTaxonomyTerm.id).where(
                CustomTaxonomyTerm.slug.like(PREFIX + '%')))).scalars().all()
        old_tax = (await db.execute(
            select(CustomTaxonomy.id).where(
                CustomTaxonomy.slug.like(PREFIX + '%')))).scalars().all()
        for pid in old_posts:
            await db.execute(delete(BlogPostTerm).where(BlogPostTerm.post_id == pid))
        for tid in old_terms:
            await db.execute(delete(BlogPostTerm).where(BlogPostTerm.term_id == tid))
        if old_posts:
            await db.execute(delete(BlogPostRevision).where(
                BlogPostRevision.post_id.in_(old_posts)))
            await db.execute(delete(BlogPost).where(BlogPost.id.in_(old_posts)))
        if old_terms:
            await db.execute(delete(CustomTaxonomyTerm).where(
                CustomTaxonomyTerm.id.in_(old_terms)))
        if old_tax:
            await db.execute(delete(CustomTaxonomy).where(
                CustomTaxonomy.id.in_(old_tax)))
        await db.commit()

        taxonomy_id = uuid.uuid4()
        db.add(CustomTaxonomy(id=taxonomy_id, name=f'{PREFIX}tax',
                              slug=f'{PREFIX}tax-{uuid.uuid4().hex[:8]}',
                              description=None, hierarchical=False))
        post_ids, tag_ids = [], []
        for i in range(3):
            pid = uuid.uuid4(); post_ids.append(pid)
            db.add(BlogPost(id=pid, title=f'{PREFIX}post{i}',
                            slug=f'{PREFIX}post{i}-{uuid.uuid4().hex[:8]}',
                            content='x', excerpt=None, cover_image_url=None,
                            author_id=me.id, status=BlogPostStatus.PUBLISHED,
                            published_at=None, visibility=PostVisibility.PUBLIC,
                            is_featured=False, allow_comments=True,
                            post_format='standard', category_id=None))
        for i in range(3):
            tid = uuid.uuid4(); tag_ids.append(tid)
            db.add(CustomTaxonomyTerm(id=tid, taxonomy_id=taxonomy_id,
                                      name=f'{PREFIX}term{i}',
                                      slug=f'{PREFIX}term{i}-{uuid.uuid4().hex[:8]}',
                                      description=None, parent_id=None, position=i))
        await db.flush()
        await db.commit()

        for pid in post_ids:
            assert await db.get(BlogPost, pid) is not None, f'fixture post {pid} missing'
        print(f'0. fixture rows visible: {len(post_ids)} posts, {len(tag_ids)} terms')

        async def attach(pid, term_ids):
            # The handler takes post_id as uuid.UUID and term ids as strings.
            return await admin_attach_post_terms(
                post_id=uuid.UUID(str(pid)),
                body={"term_ids": [str(t) for t in term_ids]},
                db=db, current_user=payload, _=None,
            )

        async def terms_of(pid):
            rows = (await db.execute(
                select(BlogPostTerm).where(BlogPostTerm.post_id == pid))).scalars().all()
            return sorted(t.term_id for t in rows)

        # 1. attach two terms
        r1 = await attach(post_ids[0], [tag_ids[0], tag_ids[1]])
        got1 = await terms_of(post_ids[0])
        print(f'1. two terms attached: {r1["attached"] == 2} | stored {len(got1)}')

        # 2. re-attaching REPLACES the set. This is the documented behaviour and
        #    the reason the route is owner-gated: it deletes before inserting.
        await attach(post_ids[0], [tag_ids[2]])
        got2 = await terms_of(post_ids[0])
        print(f'2. re-attach replaces: {got2 == [tag_ids[2]]} (was {len(got1)}, now {len(got2)})')

        # 3. an empty list clears them
        await attach(post_ids[0], [])
        print(f'3. empty list clears: {await terms_of(post_ids[0]) == []}')

        # 4. duplicate ids in one request are stored once
        await attach(post_ids[1], [tag_ids[0], tag_ids[0], tag_ids[1]])
        got4 = await terms_of(post_ids[1])
        print(f'4. duplicates stored once: {len(got4) == 2}')

        # 5. terms are per post
        await attach(post_ids[1], [tag_ids[0]])
        print(f'5. a post keeps only its own: {len(await terms_of(post_ids[1])) == 1}')

        # 6. the link table matches what was asked for overall
        total = (await db.execute(
            select(func.count()).select_from(BlogPostTerm))).scalar_one()
        print(f'6. total link rows: {total} (expected 1 — post0 cleared, post1 keeps one)')

        await db.execute(delete(BlogPostTerm).where(BlogPostTerm.post_id.in_(post_ids)))
        await db.execute(delete(CustomTaxonomyTerm).where(
            CustomTaxonomyTerm.id.in_(tag_ids)))
        await db.execute(delete(CustomTaxonomy).where(CustomTaxonomy.id == taxonomy_id))
        await db.execute(delete(BlogPostRevision).where(
            BlogPostRevision.post_id.in_(post_ids)))
        await db.execute(delete(BlogPost).where(BlogPost.id.in_(post_ids)))
        await db.commit()
        print('7. cleaned up')
    await eng.dispose()


asyncio.run(main())
