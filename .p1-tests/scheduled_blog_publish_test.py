"""Scheduled blog publishing, end to end through the celery wrapper.

This path had no behavioural coverage at all, which is how its celery wrapper
went missing: beat kept naming a task that no longer existed, the worker kept
answering "Received unregistered task" every minute, and three presence gates
agreed with each other that everything was fine. Presence checks cannot see a
function that was never there.

So this drives the entry point beat actually calls — not the service method
directly — and asserts the whole chain: the task is registered under the name
beat schedules, it publishes a post whose time has come, it leaves a future one
alone, it clears the schedule so a second run cannot republish, and the
published date is when it went live rather than when it was due.

Run:  python ../.p1-tests/scheduled_blog_publish_test.py
"""

import asyncio
import io
import json
import sys
import uuid

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, "C:/Users/Administrator/Desktop/site/backend")

import app.main  # noqa: F401 — registers every model, as the app does
from datetime import UTC, datetime, timedelta

from app.core.database.session import _build_engine, async_sessionmaker
from app.modules.blog.application import tasks
from app.modules.blog.domain.models import BlogPost, BlogPostStatus
from app.modules.users.domain.models import User

TAG = "p1sched"
bad: list[str] = []


def check(label, ok, detail=""):
    print(f"  {label}: {ok}")
    if not ok:
        bad.append(f"{label}: {detail}" if detail else label)


def scheduled_task_names():
    """What celery can actually dispatch, read from its own registry."""
    from app.worker.celery_app import celery_app

    return set(celery_app.tasks)


def beat_task_names():
    import re
    from pathlib import Path

    ini = Path("app/worker/celery_app.py").read_text(encoding="utf-8")
    return set(re.findall(r'"task":\s*"([^"]+)"', ini))


def run_task(name):
    """Run the whole celery task in its own process, the way a worker does.

    asyncpg on Windows needs the loop that opened a connection to stay alive,
    so calling the task from another thread — or from inside this fixture's own
    loop — opens a socket that is torn down mid-query. The resulting error
    names event loops, not publishing. A worker is a separate process, so this
    is one too: it keeps the test about the task's behaviour.
    """
    import subprocess

    script = (
        "import sys, json;"
        "sys.path.insert(0, '.');"
        "import app.main;"
        "from app.modules.blog.application import tasks;"
        f"print(json.dumps({{'published': tasks.{name}()}}))"
    )
    out = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True,
        cwd="C:/Users/Administrator/Desktop/site/backend",
    )
    if out.returncode != 0:
        raise RuntimeError(f"task process failed: {out.stderr[-600:]}")
    for line in out.stdout.splitlines():
        if line.startswith("{"):
            return json.loads(line)["published"]
    raise RuntimeError(f"task produced no result: {out.stdout[-400:]}")


async def main() -> int:
    # --- 1. the registration, checked against beat's own list ----------------
    beat = beat_task_names()
    registered = scheduled_task_names()
    blog_beats = {t for t in beat if "blog.application.tasks" in t}
    check("1. beat schedules at least one blog task", bool(blog_beats),
          str(sorted(beat)[:3]))
    missing = sorted(blog_beats - registered)
    check(
        "2. every blog task beat names is registered",
        not missing,
        f"{missing} fire every minute and answer 'unregistered task' — the "
        f"posts they would publish stay drafts forever",
    )
    check(
        "2b. the wrapper this file drives is registered by that name",
        "app.modules.blog.application.tasks.publish_due_scheduled_posts"
        in registered,
    )

    # --- 2. the behaviour ---------------------------------------------------
    eng = _build_engine()
    Session = async_sessionmaker(eng, expire_on_commit=False)

    async with Session() as db:
        # Debris from a killed run.
        from sqlalchemy import delete, select

        for stale in (await db.execute(select(BlogPost).where(
                BlogPost.slug.like(TAG + "%")))).scalars().all():
            await db.delete(stale)
        await db.execute(delete(User).where(User.email.like(f"%{TAG}%")))
        await db.commit()

        user = User(
            phone=f"9{TAG[:6].replace('p', '3')}{abs(hash(TAG)) % 10000:04d}",
            email=f"{TAG}@example.test", password_hash="x", is_active=True,
        )
        db.add(user)
        await db.flush()

        def make_post(name, when):
            p = BlogPost(
                title=f"{TAG} {name}", slug=f"{TAG}-{name}",
                content=f"<p>{TAG} {name}</p>", author_id=user.id,
                status=BlogPostStatus.DRAFT, scheduled_for=when,
            )
            db.add(p)
            return p

        past = datetime.now(UTC) - timedelta(minutes=5)
        due = make_post("due", past)
        future = make_post("future", datetime.now(UTC) + timedelta(days=2))
        await db.commit()
        due_id, future_id = due.id, future.id

        # Drive the task function beat calls, not the service behind it. Calling
        # the service would pass even if the wrapper were the thing that broke.
        published = run_task("publish_due_scheduled_posts")
        check("3. the task publishes the due post", published == 1, str(published))

        # Another process wrote this row. `expire_on_commit=False` is required
        # for the service's post-commit reads, and it also means this session
        # will keep serving the pre-write copy — so the read is forced rather
        # than trusted.
        await db.refresh(await db.get(BlogPost, due_id))
        row = await db.get(BlogPost, due_id)
        check("3b. and the post really is published",
              row.status == BlogPostStatus.PUBLISHED, str(row.status))
        check("3c. its schedule is cleared, so a second run cannot republish",
              row.scheduled_for is None, str(row.scheduled_for))
        check(
            "3d. published_at is when it went live, not when it was due",
            row.published_at is not None
            and row.published_at > past + timedelta(minutes=1),
            f"{row.published_at} vs due {past} — a post that ran late must not "
            f"appear late-published in every newest-first ordering",
        )

        again = run_task("publish_due_scheduled_posts")
        check("4. running twice publishes nothing the second time", again == 0,
              str(again))

        await db.refresh(await db.get(BlogPost, future_id))
        untouched = await db.get(BlogPost, future_id)
        check("5. a post dated forward is left alone",
              untouched.status == BlogPostStatus.DRAFT
              and untouched.scheduled_for is not None,
              f"{untouched.status} / {untouched.scheduled_for}")

        # A post scheduled for a moment ago becomes due on the next tick — the
        # case the wrapper's absence actually broke.
        soon = make_post("soon", datetime.now(UTC) - timedelta(seconds=1))
        await db.commit()
        third = run_task("publish_due_scheduled_posts")
        check("6. the next tick picks up a newly-due post", third == 1, str(third))
        await db.refresh(await db.get(BlogPost, soon.id))
        check("6b. and publishes it",
              (await db.get(BlogPost, soon.id)).status == BlogPostStatus.PUBLISHED)

        # Delete in FK order, and re-query: the "soon" post was added after the
        # earlier commit, so a list captured before it existed would miss it and
        # the user delete would fail on the constraint.
        await db.flush()
        for p in (await db.execute(select(BlogPost).where(
                BlogPost.slug.like(TAG + "%")))).scalars().all():
            await db.delete(p)
        await db.flush()
        await db.delete(user)
        await db.commit()

    await eng.dispose()
    if bad:
        print("\nSCHEDULED BLOG PUBLISHING GAPS:")
        for b in bad:
            print(f"  {b}")
        raise SystemExit(1)
    print("\nPASS: beat's task names are all registered, a due post publishes "
          "exactly once with the time it actually went live, and a post dated "
          "forward waits for its tick.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))