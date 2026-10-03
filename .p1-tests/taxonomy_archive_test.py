"""A custom taxonomy's archive must list terms, and a term must list its posts.

Two things had to be built for this and only one was asked for:

  * `GET /blog/taxonomies/{slug}/terms` existed with no caller, so a store that
    registered "product type" had a vocabulary and no page.
  * there was no route returning the posts carrying one custom term, so the
    term page could only render the blog's recent posts under a heading that had
    nothing to do with them. A page that looks right and is not is worse than
    no page, so the second route is part of the same item.

The assertions that matter: a term returns **its own** posts and no others,
drafts stay out, and a term of a retired taxonomy is not reachable by guessing
its slug — the same two gates the term list applies.

Run:  python ../.p1-tests/taxonomy_archive_test.py
"""

import asyncio
import io
import sys
import uuid

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, "C:/Users/Administrator/Desktop/site/backend")

import app.main  # noqa: F401 — registers every model, as the app does
from datetime import UTC, datetime, timedelta
from sqlalchemy import delete, select

from app.core.database.session import _build_engine, async_sessionmaker
from app.modules.blog.domain.models import (
    BlogPost,
    BlogPostStatus,
    PostVisibility,
)
from app.modules.blog.domain.taxonomy_models import (
    BlogPostTerm,
    CustomTaxonomy,
    CustomTaxonomyTerm,
)
from app.modules.users.domain.models import User

TAG = "p1taxar"
bad: list[str] = []


async def main() -> int:
    eng = _build_engine()
    Session = async_sessionmaker(eng, expire_on_commit=False)

    from httpx import ASGITransport, AsyncClient

    async with Session() as db:
        user = (await db.execute(
            select(User).where(User.is_superuser == True).limit(1))
        ).scalars().first()

        # Debris from a killed run.
        for stale in (await db.execute(select(BlogPost).where(
                BlogPost.slug.like(TAG + "%")))).scalars().all():
            await db.execute(delete(BlogPostTerm).where(
                BlogPostTerm.post_id == stale.id))
            await db.execute(delete(BlogPost).where(BlogPost.id == stale.id))
        await db.execute(delete(CustomTaxonomy).where(
            CustomTaxonomy.slug.like(TAG + "%")))
        await db.commit()

        taxonomy = CustomTaxonomy(name=f"{TAG} taxonomy", slug=f"{TAG}-tax")
        taxonomy.is_active = True
        db.add(taxonomy)
        await db.flush()

        term_a = CustomTaxonomyTerm(taxonomy_id=taxonomy.id,
                                   name=f"{TAG} term a", slug=f"{TAG}-a")
        term_b = CustomTaxonomyTerm(taxonomy_id=taxonomy.id,
                                   name=f"{TAG} term b", slug=f"{TAG}-b")
        db.add_all([term_a, term_b])
        await db.flush()

        def post(slug_suffix: str, status=BlogPostStatus.PUBLISHED):
            p = BlogPost(
                title=f"{TAG} post {slug_suffix}", slug=f"{TAG}-{slug_suffix}",
                content="x", excerpt=None, cover_image_url=None,
                author_id=user.id, status=status,
                published_at=datetime.now(UTC) - timedelta(hours=1),
                visibility=PostVisibility.PUBLIC, is_featured=False,
                allow_comments=True, post_format="standard", category_id=None,
            )
            db.add(p)
            return p

        in_a = post("ina")
        in_b = post("inb")
        draft = post("draft", status=BlogPostStatus.DRAFT)
        # Flush first: the join rows need real ids, and the ORM assigns them
        # on flush rather than on construction.
        await db.flush()
        db.add_all([
            BlogPostTerm(post_id=in_a.id, term_id=term_a.id),
            BlogPostTerm(post_id=in_b.id, term_id=term_b.id),
            BlogPostTerm(post_id=draft.id, term_id=term_a.id),
        ])
        await db.commit()

        def check(label, ok, detail=""):
            print(f"  {label}: {ok}")
            if not ok:
                bad.append(f"{label}: {detail}" if detail else label)

        async with AsyncClient(
            transport=ASGITransport(app=app.main.app), base_url="http://test"
        ) as client:
            r = await client.get(f"/api/v1/blog/taxonomies/{TAG}-tax/terms")
            check("1. the terms route answers", r.status_code == 200,
                  f"status {r.status_code}")
            slugs = {t["slug"] for t in (r.json() if r.status_code == 200 else [])}
            check("1b. and lists both terms",
                  {f"{TAG}-a", f"{TAG}-b"} <= slugs, str(slugs))

            r = await client.get(
                f"/api/v1/blog/taxonomies/{TAG}-tax/terms/{TAG}-a/posts")
            check("2. the term's posts route answers", r.status_code == 200,
                  f"status {r.status_code}")
            payload = r.json() if r.status_code == 200 else {}
            ids = {str(p["id"]) for p in payload.get("items", [])}

            check("3. a term returns its own post", str(in_a.id) in ids, str(ids))
            check("3b. and only its own", str(in_b.id) not in ids, str(ids))
            check("3c. a draft stays out", str(draft.id) not in ids, str(ids))
            check("3d. and the total counts only what it returned",
                  payload.get("total") == len(payload.get("items", [])) == 1,
                  str(payload.get("total")))

            r = await client.get(
                f"/api/v1/blog/taxonomies/{TAG}-tax/terms/{TAG}-zzz/posts")
            check("4. a term that does not exist is a 404",
                  r.status_code == 404, f"status {r.status_code}")

            r = await client.get(
                f"/api/v1/blog/taxonomies/{TAG}-nope/terms")
            check("5. a taxonomy that does not exist returns no terms",
                  r.status_code != 200 or r.json() == [],
                  f"status {r.status_code}")

            # A retired taxonomy must not be reachable by slug. Without this
            # check a store that switches a taxonomy off still serves its whole
            # archive, which is the opposite of what the switch means.
            taxonomy.is_active = False
            await db.commit()
            r = await client.get(
                f"/api/v1/blog/taxonomies/{TAG}-tax/terms")
            check("6. a retired taxonomy serves nothing",
                  r.status_code == 404 or r.json() == [],
                  f"status {r.status_code}")
            taxonomy.is_active = True
            await db.commit()

        for p in (in_a, in_b, draft):
            await db.execute(delete(BlogPostTerm).where(
                BlogPostTerm.post_id == p.id))
            await db.execute(delete(BlogPost).where(BlogPost.id == p.id))
        await db.execute(delete(CustomTaxonomyTerm).where(
            CustomTaxonomyTerm.taxonomy_id == taxonomy.id))
        await db.execute(delete(CustomTaxonomy).where(
            CustomTaxonomy.id == taxonomy.id))
        await db.commit()

    await eng.dispose()
    if bad:
        print("\nTAXONOMY-ARCHIVE GAPS:")
        for b in bad:
            print(f"  {b}")
        raise SystemExit(1)
    print("\nPASS: a custom taxonomy lists its terms, a term lists exactly its "
          "published posts, and a retired taxonomy serves nothing.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))