"""Media "attached to" — the column, the filter and the two halves of it.

`MediaAsset.post_id` has been on the model since the beginning with no writer,
no reader and no filter. That is worse than an absent feature: an operator
looking at a media row had a column to check and a blank in it, and the
"unattached" view could only ever have been "everything".

So this drives the real service and the real endpoint, and checks the two ways
this goes wrong while looking finished:

  * a filter that matches nothing. `post_id is None` written as `== None`
    returns an empty list, not an unattached list, and an empty library looks
    exactly like a correct one at a glance.
  * a contradictory filter silently resolved. Asking for one post's media *and*
    for media attached to nothing has no answer; returning one of the two
    readings would show an operator a list they did not ask for.

And the write side, because a filter over a column nothing writes is still an
empty list: attaching has to stick, detaching has to stick, and attaching to a
post that does not exist has to be refused rather than stored.
"""

import asyncio
import io
import sys
import uuid

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, "C:/Users/Administrator/Desktop/site/backend")

import app.main  # noqa: F401 — registers every model, as the app does
from datetime import UTC, datetime
from sqlalchemy import delete, select

from app.core.database.session import _build_engine, async_sessionmaker
from app.modules.blog.domain.models import BlogPost, BlogPostStatus, PostVisibility
from app.modules.media.application.media_service import MediaService
from app.modules.media.domain.models import MediaAsset
from app.modules.users.domain.models import User

TAG = "p1attach"
bad: list[str] = []


async def main() -> int:
    eng = _build_engine()
    Session = async_sessionmaker(eng, expire_on_commit=False)

    async with Session() as db:
        user = (await db.execute(
            select(User).where(User.is_superuser == True).limit(1))
        ).scalars().first()

        await db.execute(delete(MediaAsset).where(
            MediaAsset.file_name.like(TAG + "%")))
        for stale in (await db.execute(select(BlogPost).where(
                BlogPost.slug.like(TAG + "%")))).scalars().all():
            await db.execute(delete(BlogPost).where(BlogPost.id == stale.id))
        await db.commit()

        post = BlogPost(
            title=f"{TAG} post", slug=f"{TAG}-{uuid.uuid4().hex[:8]}",
            content="x", excerpt=None, cover_image_url=None,
            author_id=user.id, status=BlogPostStatus.PUBLISHED,
            published_at=datetime.now(UTC), visibility=PostVisibility.PUBLIC,
            is_featured=False, allow_comments=True, post_format="standard",
            category_id=None,
        )
        db.add(post)
        await db.flush()

        def make(name):
            a = MediaAsset(
                uploader_id=user.id, file_name=f"{TAG}-{name}-{uuid.uuid4().hex[:6]}.png",
                file_path=f"{TAG}/{name}.png",
                file_url=f"/uploads/{TAG}/{name}.png",
                file_size=1024, mime_type="image/png", width=100, height=100,
            )
            db.add(a)
            return a

        # three unattached, one that will be attached
        loose = [make(f"loose{i}") for i in range(3)]
        bound = make("bound")
        await db.commit()
        bound_id, loose_ids = bound.id, [a.id for a in loose]

        def check(label, ok, detail=""):
            print(f"  {label}: {ok}")
            if not ok:
                bad.append(f"{label}: {detail}" if detail else label)

        # 1. attaching writes the column
        await MediaService.attach_to_post(db, bound_id, post.id)
        await db.refresh(bound)
        check("1. attaching writes the column", bound.post_id == post.id,
              str(bound.post_id))

        # 2. the post filter finds it — and only it
        items, _ = await MediaService.list_assets(db, post_id=post.id, page_size=50)
        check("2. the post filter returns the attached asset",
              [a.id for a in items] == [bound_id], str([a.id for a in items]))

        # 3. the unattached filter finds the rest. The `== None` mistake this
        #    guards returns zero rows instead, which reads as "no unattached
        #    files" rather than as a broken comparison.
        items, _ = await MediaService.list_assets(db, unattached=True, page_size=50)
        got = {a.id for a in items}
        check("3. the unattached filter returns the loose assets",
              set(loose_ids) <= got, f"{len(got)} rows, want at least {len(loose_ids)}")
        check("3b. and not the attached one", bound_id not in got)

        # 4. the two filters together are a contradiction, refused rather than
        #    silently resolved to one of the readings
        try:
            await MediaService.list_assets(db, post_id=post.id, unattached=True)
            check("4. asking for both at once is refused", False, "no error raised")
        except ValueError:
            check("4. asking for both at once is refused", True)

        # 5. detaching sticks
        await MediaService.attach_to_post(db, bound_id, None)
        await db.refresh(bound)
        check("5. detaching clears the column", bound.post_id is None, str(bound.post_id))
        items, _ = await MediaService.list_assets(db, unattached=True, page_size=50)
        check("5b. and the file appears among the unattached",
              bound_id in {a.id for a in items})

        # 6. attaching to a post that does not exist is refused. Storing it
        #    would create exactly the dangling reference this column exists to
        #    prevent, and it would be invisible afterwards.
        ghost = uuid.uuid4()
        try:
            await MediaService.attach_to_post(db, bound_id, ghost)
            check("6. attaching to a missing post is refused", False, "no error raised")
        except Exception as exc:
            check("6. attaching to a missing post is refused",
                  type(exc).__name__ == "NotFoundError", type(exc).__name__)
        await db.refresh(bound)
        check("6b. and nothing was written", bound.post_id is None, str(bound.post_id))

        # 7. the response carries the column, or the filter and the write both
        #    work while the library shows a blank
        from app.modules.media.schemas.media import MediaAssetResponse

        resp = MediaAssetResponse.model_validate(bound)
        check("7. the response schema carries post_id", resp.post_id is None,
              str(resp.post_id))
        await MediaService.attach_to_post(db, bound_id, post.id)
        await db.refresh(bound)
        check("7b. and it round-trips a real value",
              MediaAssetResponse.model_validate(bound).post_id == post.id)

        # 8. the endpoint refuses the contradictory pair with a 400, not a
        #    list. A 500 here would read as a server fault the operator cannot
        #    act on.
        from httpx import ASGITransport, AsyncClient
        from app.core.security.jwt import create_access_token

        token = create_access_token(
            str(user.id), {"roles": ["super_admin"], "permissions": ["*"]})
        async with AsyncClient(transport=ASGITransport(app=app.main.app),
                               base_url="http://test") as client:
            both = await client.get(
                f"/api/v1/media?post_id={post.id}&unattached=true",
                headers={"Authorization": f"Bearer {token}"})
            check("8. the endpoint refuses the contradictory pair",
                  both.status_code == 400, f"status {both.status_code}")

            anon = await client.get(
                f"/api/v1/media?unattached=true")
            check("8b. and an anonymous caller is still refused",
                  anon.status_code in (401, 403), f"status {anon.status_code}")

        await db.execute(delete(MediaAsset).where(
            MediaAsset.file_name.like(TAG + "%")))
        await db.execute(delete(BlogPost).where(BlogPost.id == post.id))
        await db.commit()

    await eng.dispose()
    if bad:
        print("\nATTACH GAPS:")
        for b in bad:
            print(f"  {b}")
        raise SystemExit(1)
    print("\nPASS: assets can be attached, detached, filtered by post, and "
          "filtered as unattached.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))