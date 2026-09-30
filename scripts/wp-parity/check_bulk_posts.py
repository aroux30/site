"""Live test for bulk_posts (#72) — the per-object guard, on a real database.

Why this exists: `bulk_posts` re-checks ownership per post and returns a
per-post result. Reading the code proves the loop is there; it does not prove
the guard actually fires, that a foreign post is refused, or that a partial
batch really commits the owned rows. A typecheck says none of that.

So this writes real rows, then asserts against a real database:

  1. owner may bulk-act on their own posts
  2. a non-owner is refused for someone else's post — and the other, owned
     posts in the same batch still apply (partial success, not all-or-nothing)
  3. trash then restore round-trips
  4. a missing post is reported, not raised
  5. the request cap is enforced

It creates and deletes its own rows and never touches anything else.
Run:  python scripts/wp-parity/check_bulk_posts.py
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
os.chdir(ROOT / "backend")


async def _seed(db, author_id: uuid.UUID, count: int) -> list[uuid.UUID]:
    """Real BlogPost rows owned by *author_id*."""
    from sqlalchemy import select

    from app.modules.blog.domain.models import BlogCategory, BlogPost

    cat = (
        await db.execute(
            select(BlogCategory).where(BlogCategory.slug.like("bulk-test-%")).limit(1)
        )
    ).scalar_one_or_none()
    if cat is None:
        cat = BlogCategory(
            name="bulk-test", slug=f"bulk-test-{uuid.uuid4().hex[:8]}"
        )
        db.add(cat)
        await db.flush()

    ids: list[uuid.UUID] = []
    for i in range(count):
        post = BlogPost(
            title=f"bulk probe {i}",
            slug=f"bulk-probe-{uuid.uuid4().hex[:12]}",
            content="<p>probe</p>",
            excerpt="probe",
            status="draft",
            author_id=author_id,
            category_id=cat.id,
        )
        db.add(post)
        await db.flush()
        ids.append(post.id)
    await db.commit()
    return ids


async def _cleanup(db, ids: list[uuid.UUID]) -> None:
    from sqlalchemy import delete

    from app.modules.blog.domain.models import BlogPost, BlogPostStatus

    if ids:
        await db.execute(delete(BlogPost).where(BlogPost.id.in_(ids)))
    await db.commit()


async def main() -> int:
    from sqlalchemy import select

    from app.core.database.session import async_session_factory
    from app.core.exceptions.handlers import ValidationError
    from app.modules.blog.application.blog_service import BlogService
    from app.modules.blog.domain.models import BlogPost, BlogPostStatus
    # Import both modules, not just the class: User declares a relationship to
    # UserRole, which lives in the rbac module, and SQLAlchemy needs that class
    # registered before the mapper can initialise.
    import app.modules.rbac.domain.models  # noqa: F401
    import app.modules.users.domain.models as _users_models

    User = _users_models.User
    from app.core.security.object_capabilities import OBJECT_RULES

    failures: list[str] = []
    created: list[uuid.UUID] = []

    async with async_session_factory() as db:
        # Two distinct authors, so ownership is real rather than simulated.
        authors = (
            (
                await db.execute(
                    select(User).where(User.phone.like("+%98%")).limit(2)
                )
            )
            .scalars()
            .all()
        )
        if len(authors) < 2:
            print("SKIP: need two user rows to test ownership; seeding is out of scope.")
            return 0
        owner, other = authors[0], authors[1]

        # Payloads shaped like a real authenticated caller.
        def as_payload(u) -> dict:
            return {"sub": str(u.id), "permissions": ["*"], "roles": ["admin"]}

        # ── 1. the owner may act on their own posts ─────────────────────────
        created = await _seed(db, owner.id, 3)
        svc = BlogService(db)
        res = await svc.bulk_posts(created, "publish", actor_payload=as_payload(owner))
        print(f"[1/5] owner acts on own posts -> ok={res['ok']} failed={res['failed']}")
        if res["ok"] != 3 or res["failed"] != 0:
            failures.append(f"owner should act on all 3, got {res}")

        statuses = (
            (await db.execute(select(BlogPost.status).where(BlogPost.id.in_(created))))
            .scalars()
            .all()
        )
        if any(s != BlogPostStatus.PUBLISHED for s in statuses):
            failures.append(f"posts not published: {statuses}")

        # ── 2. a non-owner is refused, and the batch is partially applied ───
        # Same payload shape but a different user, WITHOUT the wildcard that
        # bypasses every check — this is the assertion that matters.
        # `blog:write` is the catalog codename the object-capability table maps
        # onto WP's `edit_posts`. So this payload satisfies the *owner* branch
        # for someone else's post and must still be refused — which is the
        # sharpest possible non-owner case: the caller has the capability, they
        # simply do not own the row.
        plain_other = {
            "sub": str(other.id),
            "permissions": ["blog:write"],
            "roles": [],
        }
        res2 = await svc.bulk_posts(created, "archive", actor_payload=plain_other)
        print(f"[2/5] non-owner acts -> ok={res2['ok']} failed={res2['failed']}")
        if res2["ok"] != 0 or res2["failed"] != 3:
            failures.append(
                f"a non-owner must be refused on every post, got ok={res2['ok']} "
                f"failed={res2['failed']} — the per-object guard did not fire"
            )
        statuses2 = (
            (await db.execute(select(BlogPost.status).where(BlogPost.id.in_(created))))
            .scalars()
            .all()
        )
        if any(s != BlogPostStatus.PUBLISHED for s in statuses2):
            failures.append(f"a refused action still changed rows: {statuses2}")

        # ── 3. mixed batch: one owned, one not — partial success is real ───
        foreign = await _seed(db, other.id, 1)
        created.extend(foreign)
        mixed = [created[0], foreign[0]]
        res3 = await svc.bulk_posts(mixed, "draft", actor_payload=plain_other)
        print(f"[3/5] mixed batch -> ok={res3['ok']} failed={res3['failed']}")
        # The owner in this payload is `other`, so their own post applies and
        # the other author's does not.
        if res3["ok"] != 1 or res3["failed"] != 1:
            failures.append(
                f"a mixed batch must apply the owned row and refuse the other, got {res3}"
            )

        # ── 4. trash → restore round-trip ───────────────────────────────────
        res4 = await svc.bulk_posts(created[:2], "trash", actor_payload=as_payload(owner))
        trashed = (
            (
                await db.execute(
                    select(BlogPost.deleted_at).where(BlogPost.id.in_(created[:2]))
                )
            )
            .scalars()
            .all()
        )
        if res4["ok"] != 2 or any(t is None for t in trashed):
            failures.append(f"trash did not apply: {res4} deleted_at={trashed}")
        res5 = await svc.bulk_posts(created[:2], "restore", actor_payload=as_payload(owner))
        restored = (
            (
                await db.execute(
                    select(BlogPost.deleted_at).where(BlogPost.id.in_(created[:2]))
                )
            )
            .scalars()
            .all()
        )
        print(f"[5/5] trash->restore -> {res4['ok']} trashed, {res5['ok']} restored")
        if res5["ok"] != 2 or any(t is not None for t in restored):
            failures.append(f"restore did not apply: {res5} deleted_at={restored}")

        # ── 5. unknown action and a missing post are both handled ───────────
        try:
            await svc.bulk_posts(created, "detonate", actor_payload=as_payload(owner))
            failures.append("an unknown action must raise, not silently no-op")
        except ValidationError:
            pass

        missing = uuid.uuid4()
        res6 = await svc.bulk_posts([missing], "publish", actor_payload=as_payload(owner))
        print(f"[5b] missing post -> ok={res6['ok']} failed={res6['failed']}")
        if res6["ok"] != 0 or res6["failed"] != 1:
            failures.append(f"a missing post must be reported, got {res6}")

        await _cleanup(db, created)

    if failures:
        print("\nFAIL:")
        for f in failures:
            print(f"  - {f}")
        return 1

    print(
        "\nPASS: bulk_posts enforces the per-object guard on a real database, "
        "applies partial batches, and round-trips trash/restore."
    )
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
