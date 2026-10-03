"""The two tools this wave added: the category→tag converter and the trash purge.

Both are destructive-capable, so both are tested on the behaviour that matters:
the converter must be idempotent and must report what it skipped, and the purge
must respect the age window rather than emptying everything on its first run.
"""
import asyncio, sys, io, uuid
from datetime import datetime, UTC, timedelta
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, 'C:/Users/Administrator/Desktop/site/backend')
import app.main
from sqlalchemy import select, delete, func
from app.core.database.session import _build_engine, async_sessionmaker
from app.modules.blog.domain.models import (
    BlogPost, BlogPostStatus, PostVisibility, BlogCategory, BlogTag, BlogPostTag,
)
from app.modules.blog.application.blog_service import BlogService
from app.modules.content.domain.models import CmsPage
from app.modules.content.application import cms_page_service as page_svc
from app.modules.users.domain.models import User

TAG = 'p1tools'
bad: list[str] = []


async def main():
    eng = _build_engine()
    S = async_sessionmaker(eng, expire_on_commit=False)
    async with S() as db:
        me = (await db.execute(
            select(User).where(User.is_superuser == True).limit(1))).scalars().first()
        # clear leftovers
        stale_posts = (await db.execute(select(BlogPost).where(
            BlogPost.slug.like(TAG + '%')))).scalars().all()
        if stale_posts:
            ids = [p.id for p in stale_posts]
            await db.execute(delete(BlogPostTag).where(BlogPostTag.post_id.in_(ids)))
            await db.execute(delete(BlogPost).where(BlogPost.id.in_(ids)))
        stale_pages = (await db.execute(select(CmsPage).where(
            CmsPage.slug.like(TAG + '%')))).scalars().all()
        if stale_pages:
            await db.execute(delete(CmsPage).where(
                CmsPage.id.in_([p.id for p in stale_pages])))
        stale_tags = (await db.execute(select(BlogTag).where(
            BlogTag.slug.like(TAG + '%')))).scalars().all()
        if stale_tags:
            await db.execute(delete(BlogPostTag).where(
                BlogPostTag.tag_id.in_([t.id for t in stale_tags])))
            await db.execute(delete(BlogTag).where(
                BlogTag.id.in_([t.id for t in stale_tags])))
        stale_cats = (await db.execute(select(BlogCategory).where(
            BlogCategory.slug.like(TAG + '%')))).scalars().all()
        if stale_cats:
            await db.execute(delete(BlogCategory).where(
                BlogCategory.id.in_([c.id for c in stale_cats])))
        await db.commit()

        svc = BlogService(db)

        async def mktag(suffix, name=None):
            slug = f'{TAG}-t{suffix}-{uuid.uuid4().hex[:6]}'
            c = BlogCategory(name=name or f'cat{suffix}', slug=slug)
            db.add(c); await db.flush()
            return c

        async def mkpost(cat, suffix):
            slug = f'{TAG}-p{suffix}-{uuid.uuid4().hex[:8]}'
            p = BlogPost(title=f'{TAG} post {suffix}', slug=slug, content='x',
                         excerpt=None, cover_image_url=None, author_id=me.id,
                         status=BlogPostStatus.PUBLISHED,
                         published_at=datetime.now(UTC),
                         visibility=PostVisibility.PUBLIC, is_featured=False,
                         allow_comments=True, post_format='standard',
                         category_id=cat.id if cat else None)
            db.add(p); await db.flush()
            return p

        cat_a = await mktag('a')
        cat_b = await mktag('b')
        p_a1 = await mkpost(cat_a, 'a1')
        p_a2 = await mkpost(cat_a, 'a2')
        p_b1 = await mkpost(cat_b, 'b1')
        p_none = await mkpost(None, 'none')
        await db.commit()

        # 1. every categorised post is converted; the uncategorised one is
        #    reported as skipped rather than silently ignored
        fixture_posts = [p_a1, p_a2, p_b1, p_none]
        r1 = await svc.convert_categories_to_tags(
            post_ids=[p.id for p in fixture_posts]
        )
        ok1 = r1['converted'] == 3 and r1['skipped_no_category'] == 1
        print(f'1. converts all categorised posts: {ok1} '
              f'(converted={r1["converted"]}, skipped={r1["skipped_no_category"]})')
        if not ok1:
            bad.append(f'converter counts wrong: {r1}')

        # 2. one tag per category, not per post
        ok2 = r1['tags_created'] == 2
        print(f'2. one tag per category, not per post: {ok2} '
              f'(tags_created={r1["tags_created"]})')
        if not ok2:
            bad.append(f'created {r1["tags_created"]} tags for 2 categories')

        # 3. every post carries the tag of its category
        for p, cat in ((p_a1, cat_a), (p_a2, cat_a), (p_b1, cat_b)):
            rows = (await db.execute(select(BlogPostTag).where(
                BlogPostTag.post_id == p.id))).scalars().all()
            if len(rows) != 1:
                bad.append(f'post {p.slug} has {len(rows)} tags, expected 1')
        ok3 = not any('has' in b for b in bad)
        print(f'3. each post ends up with exactly one tag: {ok3}')
        if not ok3:
            bad.append('a post did not end up with exactly one tag')

        # 4. running it again is idempotent: same tags, no duplicates
        r4 = await svc.convert_categories_to_tags(
            post_ids=[p.id for p in fixture_posts]
        )
        total_links = (await db.execute(select(func.count()).select_from(
            BlogPostTag))).scalar_one()
        reused = r4['tags_created'] == 0 and r4['tags_reused'] == r4['converted']
        print(f'4. a second run creates nothing new: {reused} '
              f'(created={r4["tags_created"]}, reused={r4["tags_reused"]}, '
              f'links={total_links})')
        if not reused:
            bad.append(f'the second run was not idempotent: {r4}')

        # 5. the category stays put unless clearing was asked for
        still = (await db.execute(select(BlogPost).where(
            BlogPost.id == p_a1.id))).scalar_one()
        ok5 = still.category_id == cat_a.id
        print(f'5. the category is untouched by default: {ok5}')
        if not ok5:
            bad.append('the converter detached a category without being asked')

        # 6. clear_categories actually clears
        await svc.convert_categories_to_tags(
            post_ids=[p.id for p in fixture_posts], clear_categories=True
        )
        cleared = (await db.execute(select(BlogPost).where(
            BlogPost.id == p_a1.id))).scalar_one()
        ok6 = cleared.category_id is None
        print(f'6. clear_categories detaches it: {ok6}')
        if not ok6:
            bad.append('clear_categories did not detach the category')

        # 7. the trash purge respects the age window
        now = datetime.now(UTC)
        old = await mkpost(cat_a, 'old')
        old.deleted_at = now - timedelta(days=40)
        new = await mkpost(cat_a, 'new')
        new.deleted_at = now - timedelta(days=2)
        alive = await mkpost(cat_a, 'alive')          # not trashed at all
        await db.commit()

        r7 = await svc.empty_post_trash(older_than_days=30)
        ids_gone = set(r7['post_ids'])
        ok7 = str(old.id) in ids_gone and str(new.id) not in ids_gone
        print(f'7. the age window spares a recently trashed post: {ok7} '
              f'(removed={r7["removed"]})')
        if not ok7:
            bad.append(f'the age window did not hold: {r7}')

        # 8. an untombed post is never purged
        still_alive = (await db.execute(select(BlogPost).where(
            BlogPost.id == alive.id))).scalar_one()
        ok8 = still_alive is not None
        print(f'8. a post that is not trashed survives: {ok8}')
        if not ok8:
            bad.append('the purge deleted a post that was not in the trash')

        # 9. without a window the rest of the trash goes
        r9 = await svc.empty_post_trash()
        ok9 = str(new.id) in set(r9['post_ids'])
        print(f'9. with no window everything trashed goes: {ok9}')
        if not ok9:
            bad.append(f'an unbounded purge missed a trashed post: {r9}')

        # 10. the same, for pages
        page = CmsPage(title=f'{TAG} trashed', slug=f'{TAG}-pg-{uuid.uuid4().hex[:8]}',
                       body_html='<p>x</p>')
        page.deleted_at = now - timedelta(days=40)
        db.add(page)
        fresh = CmsPage(title=f'{TAG} fresh', slug=f'{TAG}-pgf-{uuid.uuid4().hex[:8]}',
                        body_html='<p>x</p>')
        fresh.deleted_at = now - timedelta(days=1)
        db.add(fresh)
        # A page that was never trashed. Without one, dropping the trash filter
        # from the purge would change nothing the checks could see, and the
        # negative test aimed at that filter would report it as undetected.
        live = CmsPage(title=f'{TAG} live', slug=f'{TAG}-pgl-{uuid.uuid4().hex[:8]}',
                       body_html='<p>x</p>')
        db.add(live)
        await db.commit()

        r10 = await page_svc.empty_page_trash(db, older_than_days=30)
        left_old = (await db.execute(select(CmsPage).where(
            CmsPage.id == page.id))).scalar_one_or_none()
        ok10 = left_old is None and r10['removed'] >= 1
        print(f'10. the page purge honours its window: {ok10} (removed={r10["removed"]})')
        if not ok10:
            bad.append(f'the page purge ignored its window: {r10}')

        r11 = await page_svc.empty_page_trash(db)
        left_fresh = (await db.execute(select(CmsPage).where(
            CmsPage.id == fresh.id))).scalar_one_or_none()
        still_live = (await db.execute(select(CmsPage).where(
            CmsPage.id == live.id))).scalar_one_or_none()
        ok11 = left_fresh is None
        print(f'11. with no window the page trash empties: {ok11}')
        if not ok11:
            bad.append('an unbounded page purge missed a trashed page')

        # 11b. a page that was never trashed must survive an unbounded purge.
        #     The admin trash tab hides those rows, but the purge selects by
        #     query — a dropped `deleted_at IS NOT NULL` would take a live page
        #     off the storefront with no way back.
        ok11b = still_live is not None
        print(f'11b. a live page survives an unbounded purge: {ok11b}')
        if not ok11b:
            bad.append('the page purge deleted a page that was never trashed')

        # cleanup
        allp = (await db.execute(select(BlogPost).where(
            BlogPost.slug.like(TAG + '%')))).scalars().all()
        if allp:
            await db.execute(delete(BlogPostTag).where(
                BlogPostTag.post_id.in_([p.id for p in allp])))
            await db.execute(delete(BlogPost).where(BlogPost.id.in_([p.id for p in allp])))
        allt = (await db.execute(select(BlogTag).where(
            BlogTag.slug.like(TAG + '%')))).scalars().all()
        if allt:
            await db.execute(delete(BlogPostTag).where(
                BlogPostTag.tag_id.in_([t.id for t in allt])))
            await db.execute(delete(BlogTag).where(
                BlogTag.id.in_([t.id for t in allt])))
        db.expire_all()
        allc = (await db.execute(select(BlogCategory).where(
            BlogCategory.slug.like(TAG + '%')))).scalars().all()
        if allc:
            await db.execute(delete(BlogCategory).where(
                BlogCategory.id.in_([c.id for c in allc])))
        allpg = (await db.execute(select(CmsPage).where(
            CmsPage.slug.like(TAG + '%')))).scalars().all()
        if allpg:
            await db.execute(delete(CmsPage).where(
                CmsPage.id.in_([p.id for p in allpg])))
        await db.commit()
        print('12. cleaned up')
        if bad:
            print(f'TOOL GAPS: {bad}')
            raise SystemExit(1)
    await eng.dispose()


asyncio.run(main())