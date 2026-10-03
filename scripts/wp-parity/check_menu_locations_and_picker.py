"""Menu items can be picked from real records, and locations are not fixed.

P1 "منو: آیتم‌های منو فقط لینک سفارشی" and "منو: مکان‌های منو ثابت". Two gaps:

  * the item form was two text boxes, so linking a page meant typing its slug
    and a typo produced a 404 the panel could have prevented;
  * the location was an enum of five, so an operator could not add a sixth —
    and worse, the ORM Enum raised ``LookupError`` reading back any row outside
    the five, so a custom location could be written and never read.

This checks the chain for both: the picker exists and calls a real list, the
location routes accept a custom slug, and the model no longer stores an Enum.

    python scripts/wp-parity/check_menu_locations_and_picker.py
"""

from __future__ import annotations

import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "backend"))
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(__file__))
import console_safe  # noqa: F401  — idempotent. A plain TextIOWrapper
# here is closed by the next module that wraps stdout, which is how a test
# that imports a guard ends up dying on "I/O operation on closed file".

CMS_PAGE = os.path.join(ROOT, "frontend", "app", "admin", "cms", "page.tsx")
CLIENT = os.path.join(ROOT, "frontend", "lib", "api", "content.ts")
MODELS = os.path.join(ROOT, "backend", "app", "modules", "content", "domain", "models.py")
ROUTES = os.path.join(ROOT, "backend", "app", "modules", "content", "api", "routes.py")

failures: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {label}: {ok}")
    if not ok:
        failures.append(f"{label}: {detail}" if detail else label)


def main() -> int:
    cms = open(CMS_PAGE, encoding="utf-8").read() if os.path.isfile(CMS_PAGE) else ""
    client = open(CLIENT, encoding="utf-8").read() if os.path.isfile(CLIENT) else ""
    models = open(MODELS, encoding="utf-8").read() if os.path.isfile(MODELS) else ""
    routes = open(ROUTES, encoding="utf-8").read() if os.path.isfile(ROUTES) else ""

    # 157: the picker.
    check("the menu form has a link-source picker",
          'linkSource' in cms and "برگه" in cms and "نوشته" in cms,
          "no page/post picker on the item form")
    check("the picker loads real pages", "listPages" in cms)
    check("the picker loads real posts", "listPosts" in cms)
    check("picking fills the URL", "pickOption" in cms)

    # 158: free locations.
    check("the client exposes menu locations",
          "listMenuLocations" in client and "/content/menus/locations" in client)
    check("the admin can add a location from the panel",
          "newLocation" in cms and "افزودن مکان" in cms)
    check("the location list route exists", "/menus/locations" in routes)
    # The literal route must precede the parameterized one or it is swallowed.
    loc_index = routes.find('"/menus/locations"')
    param_index = routes.find('"/menus/{location}"')
    check("the literal locations route precedes the parameterized one",
          0 <= loc_index < param_index,
          f"literal at {loc_index}, param at {param_index}")
    check("the model stores location as a plain slug, not an Enum",
          "location: Mapped[str]" in models and "location: Mapped[MenuLocation]" not in models,
          "the column is still an Enum — a custom location cannot be read back")

    # Behaviour: a custom location round-trips through the real app.
    import asyncio

    from sqlalchemy import delete, select

    import app.main  # noqa: F401
    from httpx import ASGITransport, AsyncClient
    from app.core.database.session import _build_engine, async_sessionmaker
    from app.core.security.jwt import create_access_token
    from app.modules.content.domain.models import SiteMenu
    from app.modules.users.domain.models import User

    async def behaviour() -> list[str]:
        problems: list[str] = []
        eng = _build_engine()
        Session = async_sessionmaker(eng, expire_on_commit=False)
        try:
            async with Session() as db:
                admin = (
                    await db.execute(
                        select(User).where(User.is_superuser == True).limit(1)
                    )
                ).scalars().first()
            token = create_access_token(
                str(admin.id), {"roles": ["super_admin"], "permissions": ["*"]}
            )
            headers = {"Authorization": f"Bearer {token}"}
            async with AsyncClient(
                transport=ASGITransport(app=app.main.app), base_url="http://test"
            ) as http:
                r = await http.post(
                    "/api/v1/content/admin/menus",
                    headers=headers,
                    json={"location": "campaign_bar", "title": "Sale", "url": "/sale"},
                )
                if r.status_code not in (200, 201):
                    problems.append(f"create custom location -> {r.status_code}")
                    return problems
                item_id = r.json().get("id")
                r2 = await http.get("/api/v1/content/menus/campaign_bar")
                if r2.status_code != 200 or not r2.json():
                    problems.append(f"read custom location -> {r2.status_code}")
                r3 = await http.post(
                    "/api/v1/content/admin/menus",
                    headers=headers,
                    json={"location": "bad location!", "title": "x", "url": "/x"},
                )
                if r3.status_code not in (400, 422):
                    problems.append(f"invalid location accepted -> {r3.status_code}")
                if item_id:
                    await http.delete(
                        f"/api/v1/content/admin/menus/{item_id}", headers=headers
                    )
        finally:
            async with Session() as db:
                await db.execute(delete(SiteMenu).where(SiteMenu.location == "campaign_bar"))
                await db.commit()
            await eng.dispose()
        return problems

    problems = asyncio.run(behaviour())
    check("a custom location round-trips and an invalid one is refused",
          not problems, "; ".join(problems))

    if failures:
        print("\nFAIL:")
        for f in failures:
            print(f"  {f}")
        return 1
    print("\nPASS: menu items can be picked from real pages/posts, and menu "
          "locations are operator-extensible.")
    return 0


if __name__ == "__main__":
    sys.exit(main())