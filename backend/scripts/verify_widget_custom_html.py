"""Live check: a custom_html widget renders markup, and only safe markup.

P0 "ویجت: رندر custom_html". The widget rendered its own source as visible
text, so an operator who wanted a promotional block with a link and a bold price
got the HTML printed on the storefront instead. The tempting fix is
``dangerouslySetInnerHTML``, which turns every admin account into a stored-XSS
vector on a page every visitor loads.

So the check is about the *pair*: markup is rendered, and the value in the
database has already been sanitized on the way in. Rendering is the feature;
sanitizing at write time is what makes it safe. Checking only one half passes on
the version that is either useless or exploitable.

Four payloads, each of which must come out inert:

  1. an inline script — removed
  2. an event handler on an allowed tag — removed, because the tag is fine and
     the handler is the whole attack
  3. a ``javascript:`` URL in an allowed href — removed
  4. legitimate markup — kept, because a sanitizer that also eats the feature is
     not a fix

    cd backend && PYTHONPATH=. python scripts/verify_widget_custom_html.py
"""

from __future__ import annotations

import asyncio
import importlib
import io
import json
import pkgutil
import sys
import uuid
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import app.modules as _modules

for _m in pkgutil.walk_packages(_modules.__path__, "app.modules."):
    try:
        importlib.import_module(_m.name)
    except Exception:  # noqa: BLE001
        pass

from app.shared.content.widgets import (  # noqa: E402
    WIDGET_OPTIONS_KEY,
    WidgetService,
)

#: Each payload is (name, markup, must_not_contain, must_contain).
#:
#: ``must_not_contain`` is checked case-insensitively because HTML is, and a
#: guard that matches ``<script>`` exactly does not see ``<ScRiPt>``.
PAYLOADS = [
    (
        "an inline script",
        '<p>hello</p><script>fetch("/api/v1/users/admin/users")</script>',
        ("<script", "fetch("),
        ("hello",),
    ),
    (
        "an event handler on an allowed tag",
        '<p onclick="steal()">price</p>',
        ("onclick", "steal("),
        ("price",),
    ),
    (
        "a javascript: URL",
        '<a href="javascript:alert(1)">click</a>',
        ("javascript:",),
        ("click",),
    ),
    (
        "an iframe",
        '<iframe src="https://evil.example/x"></iframe>',
        ("<iframe",),
        (),
    ),
    (
        "a style tag",
        '<style>body{display:none}</style><p>visible</p>',
        ("<style",),
        ("visible",),
    ),
]

#: Markup that has to survive. A sanitizer that strips the feature along with the
#: payload is the other half of "fixing" this by rendering text again.
LEGITIMATE = '<p>Sale ends <strong>Friday</strong> — <a href="/offers">see offers</a></p>'


def _database_url() -> str:
    for line in open(".env", encoding="utf-8"):
        if line.startswith("DATABASE_URL="):
            return line.split("=", 1)[1].strip().strip("\"'")
    raise SystemExit("DATABASE_URL not found in .env")


async def main() -> int:
    engine = create_async_engine(_database_url())
    session = async_sessionmaker(engine, expire_on_commit=False)
    failures: list[str] = []
    original = None

    try:
        async with session() as db:
            original = await SiteOptionsGet(db, WIDGET_OPTIONS_KEY)

        area = "verify-%s" % uuid.uuid4().hex[:8]
        widgets = [
            {
                "id": uuid.uuid4().hex,
                "type": "custom_html",
                "title": name,
                "config": {"content": markup},
            }
            for name, markup, _, _ in PAYLOADS
        ]
        widgets.append(
            {
                "id": uuid.uuid4().hex,
                "type": "custom_html",
                "title": "legitimate",
                "config": {"content": LEGITIMATE},
            }
        )

        # Written through the real service — not through sanitize_html directly —
        # because what ships is the service, and a check that cleans the value
        # itself proves nothing about the path a widget actually takes.
        async with session() as db:
            await WidgetService.update_area(db, area, widgets)
            await db.commit()

        async with session() as db:
            stored_raw = await SiteOptionsGet(db, WIDGET_OPTIONS_KEY)
        stored = json.loads(stored_raw)[area]["widgets"]

        by_title = {w.get("title"): (w.get("config") or {}).get("content", "") for w in stored}
        for name, _, must_not, must in PAYLOADS:
            value = by_title.get(name, "")
            lowered = value.lower()
            leaked = [t for t in must_not if t.lower() in lowered]
            missing = [t for t in must if t.lower() not in lowered]
            if leaked:
                failures.append(
                    "%s survived into the database: %s. The storefront renders this "
                    "value as markup on a page every visitor loads." % (name, ", ".join(leaked))
                )
            elif missing:
                failures.append(
                    "%s was stripped along with the payload (%s missing); a "
                    "sanitizer that eats the feature is the same as not shipping it"
                    % (name, ", ".join(missing))
                )
            else:
                print("PASS: %s is inert in storage" % name)

        legit = by_title.get("legitimate", "")
        for needed in ("<strong>", 'href="/offers"', "Friday"):
            if needed.lower() not in legit.lower():
                failures.append(
                    "legitimate markup lost %r in storage, so a sanitized "
                    "custom_html widget still cannot do the job it exists for" % needed
                )
        if not failures:
            print("PASS: legitimate markup survives intact")

        # 2. And the read path returns what was written. A write that sanitizes
        #    and a read that re-serializes differently would mean the guarantee
        #    only holds on the first fetch.
        async with session() as db:
            reread = await WidgetService.get_all_areas(db)
        if reread.get(area, {}).get("widgets") != stored:
            failures.append(
                "what comes back from get_all_areas differs from what was written; "
                "the sanitized value is not what a reader will actually render"
            )
        else:
            print("PASS: the read path returns the sanitized value unchanged")

        # 3. And a text widget is not mangled. "a < b" is prose, not markup, and
        #    running it through an HTML sanitizer would alter it for no benefit.
        async with session() as db:
            await WidgetService.update_area(
                db,
                area,
                [
                    {
                        "id": uuid.uuid4().hex,
                        "type": "text",
                        "title": "prose",
                        "config": {"content": "a < b and 3 > 2"},
                    }
                ],
            )
            await db.commit()
            prose_raw = await SiteOptionsGet(db, WIDGET_OPTIONS_KEY)
        prose = json.loads(prose_raw)[area]["widgets"][0]["config"]["content"]
        if prose != "a < b and 3 > 2":
            failures.append(
                "a text widget's content came back as %r; only custom_html bodies "
                "are HTML, and sanitizing prose mangles it" % prose
            )
        else:
            print("PASS: a text widget's prose is left alone")

        # 4. And the storefront renders the value as markup. Read from the source
        #    rather than asserted: this check runs in the backend, and the one
        #    thing that must not drift is the component's decision.
        widget_area = (
            Path(__file__).resolve().parents[2]
            / "frontend"
            / "components"
            / "layout"
            / "widget-area.tsx"
        )
        if widget_area.is_file():
            src = widget_area.read_text(encoding="utf-8")
            case = src.split('case "custom_html":', 1)[-1].split("case ", 1)[0]
            if "dangerouslySetInnerHTML" not in case:
                failures.append(
                    "the storefront still renders custom_html as text, so the "
                    "widget type does nothing an operator asked for"
                )
            else:
                print("PASS: the storefront renders custom_html as markup")
        else:
            failures.append("the widget-area component is missing")
    finally:
        async with session() as db:
            from app.modules.settings.application.site_options_service import (
                SiteOptionsService,
            )

            if original is None:
                await db.execute(
                    text("DELETE FROM site_options WHERE option_key = :k"),
                    {"k": WIDGET_OPTIONS_KEY},
                )
            else:
                await SiteOptionsService.set(db, WIDGET_OPTIONS_KEY, original)
            await db.commit()
        print("restored the widget areas")
        await engine.dispose()

    for f in failures:
        print("FAIL: %s" % f)
    if failures:
        return 1
    print("")
    print("PASS: custom_html renders markup, and what is stored is already safe.")
    return 0


async def SiteOptionsGet(db, key):  # noqa: N802 — a local alias, not a class
    from app.modules.settings.application.site_options_service import SiteOptionsService

    return await SiteOptionsService.get(db, key)


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))