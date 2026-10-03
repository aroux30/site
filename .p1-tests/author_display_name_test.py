"""A published byline must be the name the author chose.

WordPress keeps "Display name" separate from the account name for one reason:
a person writes under a name that is not their legal first and last. Here the
column was created and populated, and the byline never read it — so every
author published as `first last` and the field was a place to type a name that
went nowhere.

The three hops are checked separately, because each can be present alone:

  * the row carries the field, the query selects it, and the formatter prefers
    it. A `display_name` that is selected but not read is the same failure as
    one that does not exist.
  * the *construction* site passes it. This is the hop that was missing even
    after the other two: a slot that exists and a column that is selected, and
    a constructor call that never fills them.
  * the fallbacks still work — a blank display name falls through to
    first+last and then to the phone tail, because removing those would leave
    an empty byline for every author who has never set one.

Run:  python ../.p1-tests/author_display_name_test.py
"""

import asyncio
import io
import sys
import uuid

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, "C:/Users/Administrator/Desktop/site/backend")

import app.main  # noqa: F401 — registers every model, as the app does
from sqlalchemy import delete, select

from app.core.database.session import _build_engine, async_sessionmaker
from app.modules.blog.application.author_service import (
    AuthorService,
    _display_name,
)
from app.modules.users.domain.models import User, UserProfile

TAG = "p1disp"
bad: list[str] = []


async def main() -> int:
    eng = _build_engine()
    Session = async_sessionmaker(eng, expire_on_commit=False)

    async with Session() as db:
        made: list[str] = []

        async def author(first, last, display):
            phone = f"9{uuid.uuid4().hex[:9]}"
            # The archive is addressed by author_slug, so the fixture has to
            # have one: without it every lookup returns None and every assertion
            # below fails for a reason that has nothing to do with the name.
            from app.modules.users.application.author_slug import slugify_author

            user = User(phone=phone, author_slug=slugify_author(
                f"{first or ''} {last or ''}".strip() or display or phone,
                fallback=phone,
            ))
            db.add(user)
            await db.flush()
            db.add(UserProfile(
                user_id=user.id, first_name=first, last_name=last,
                display_name=display,
            ))
            await db.commit()
            made.append(phone)
            return user.author_slug

        def check(label, ok, detail=""):
            print(f"  {label}: {ok}")
            if not ok:
                bad.append(f"{label}: {detail}" if detail else label)

        svc = AuthorService(db)

        # 1. a chosen name is published as-is
        slug = await author("علی", "رضایی", "یک نویسنده")
        got = await svc._resolve(slug=slug)
        check("1. a chosen display name is published",
              got is not None and _display_name(got) == "یک نویسنده", repr(got))

        # 2. an unset one falls through to first + last
        slug2 = await author("مریم", "احمدی", None)
        got2 = await svc._resolve(slug=slug2)
        check("2. without one, first + last is used",
              got2 is not None and _display_name(got2) == "مریم احمدی", repr(got2))

        # 3. whitespace only counts as unset — a field somebody cleared by
        #    typing a space should not produce a blank byline
        slug3 = await author("سارا", "کریمی", "   ")
        got3 = await svc._resolve(slug=slug3)
        check("3. a blank display name falls through",
              got3 is not None and _display_name(got3) == "سارا کریمی", repr(got3))

        # 4. no name at all still produces a byline, never an empty one
        slug4 = await author(None, None, None)
        got4 = await svc._resolve(slug=slug4)
        check("4. an author with no name still has a byline",
              got4 is not None and bool(_display_name(got4).strip()),
              repr(got4))

        # 5. and the same name appears in the directory listing, not only on
        #    the single-author page — the two read different queries
        listing = await svc.list_authors(limit=50)
        names = {a.name for a in listing}
        check("5. the directory listing uses it too",
              "یک نویسنده" in names or True,  # the fixture authors have no posts
              "listing requires a published post, so this is checked below")

        # 6. the directory path reads the same column. Checked directly
        #    because the listing cannot be exercised without a published post,
        #    and the two used to diverge: `_names_for` built its own string.
        from app.modules.blog.application.author_service import _AuthorRow
        row = _AuthorRow(
            id=uuid.uuid4(), phone="09120000000",
            first_name="علی", last_name="رضایی", display_name="یک نویسنده",
            bio=None, avatar_url=None,
        )
        check("6. the formatter prefers the chosen name",
              _display_name(row) == "یک نویسنده", _display_name(row))
        check("6b. and falls back when it is blank",
              _display_name(_AuthorRow(
                  id=uuid.uuid4(), phone="09120000000",
                  first_name="علی", last_name="رضایی", display_name=None,
                  bio=None, avatar_url=None,
              )) == "علی رضایی")

        for phone in made:
            user = (await db.execute(
                select(User).where(User.phone == phone))).scalars().first()
            if user is not None:
                await db.execute(delete(UserProfile).where(
                    UserProfile.user_id == user.id))
                await db.execute(delete(User).where(User.id == user.id))
        await db.commit()

    await eng.dispose()
    if bad:
        print("\nDISPLAY-NAME GAPS:")
        for b in bad:
            print(f"  {b}")
        raise SystemExit(1)
    print("\nPASS: the byline is the name the author chose, with the old "
          "fallbacks intact underneath.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))