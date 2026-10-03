#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Guard the feed importer end to end: parse, then the chain that must reach it.

A feed importer is four separate things — a parser, a service call, an admin
route, and an admin screen — and every one of them can be "present" while the
feature is dead. The parser can exist with no caller; the route can exist with
no button; the button can exist while the chain never reaches the database. This
gate walks all four links, and it *runs* the parser against real feed documents
rather than grepping for a function name.

What it asserts:

1. **Both feed formats parse.** RSS 2.0 and Atom, because a parser written for
   one is a parser that reports "no entries found" — which reads as an empty
   feed, not as a wrong parser.
2. **The output is the shape the importer reads.** `category_slug`,
   `tag_slugs`, `status`, `title` — the keys `BlogTransferService.import_json`
   actually reads. A dict with the feed's own vocabulary imports cleanly and
   files every post uncategorised.
3. **Every entry becomes a draft.** A feed publishes by definition; importing an
   archive as live posts puts unreviewed content on the storefront.
4. **The feed's own link survives**, because `BlogPost` has no source-URL
   column and it is unrecoverable afterwards if dropped.
5. **A hostile feed's link cannot inject markup.** The link is written into the
   post body as an anchor, so an unescaped `"` in it closes the attribute and
   puts an event handler on every imported post.
6. **The chain is complete.** parser → route → client → screen. A parser with
   no route, or a route with no screen, is the shape this gate exists to end.

Read-only: it parses feeds in memory and reads source. It creates and drops no
database rows.

    python scripts/wp-parity/check_feed_import_chain.py
"""

from __future__ import annotations

import html.parser
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import console_safe  # noqa: F401  — idempotent; makes stdout safe for non-ASCII

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
BACKEND = os.path.join(ROOT, "backend")
FRONTEND = os.path.join(ROOT, "frontend")

sys.path.insert(0, BACKEND)

PARSER = os.path.join(
    BACKEND, "app", "modules", "dataexchange", "application", "feed_parser.py"
)
ROUTES = os.path.join(BACKEND, "app", "modules", "dataexchange", "api", "routes.py")
TRANSFER = os.path.join(
    BACKEND, "app", "modules", "blog", "application", "transfer_service.py"
)
CLIENT = os.path.join(FRONTEND, "lib", "api", "data-exchange.ts")
SCREEN = os.path.join(FRONTEND, "app", "admin", "data-exchange", "page.tsx")

RSS = b"""<?xml version="1.0"?>
<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/"
     xmlns:dc="http://purl.org/dc/elements/1.1/">
<channel>
  <title>Probe feed</title>
  <category>News</category>
  <item>
    <title>Alpha</title>
    <link>https://probe.example/alpha</link>
    <dc:creator>alice</dc:creator>
    <pubDate>Mon, 01 Jan 2024 10:00:00 +0000</pubDate>
    <category>Tech</category>
    <category domain="post_tag">python</category>
    <description>Alpha teaser</description>
    <content:encoded><![CDATA[<p>Alpha body</p>]]></content:encoded>
  </item>
  <item>
    <title>Beta</title>
    <link>https://probe.example/beta</link>
    <description>Beta teaser</description>
    <content:encoded><![CDATA[<p>Beta body</p>]]></content:encoded>
  </item>
  <item><description>no title, must be skipped</description></item>
</channel>
</rss>"""

ATOM = b"""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Atom probe</title>
  <entry>
    <title>Gamma</title>
    <link rel="alternate" href="https://probe.example/gamma"/>
    <id>urn:uuid:1</id>
    <published>2024-02-03T08:30:00Z</published>
    <author><name>bob</name></author>
    <summary>Gamma summary</summary>
    <content type="html">&lt;p&gt;Gamma body&lt;/p&gt;</content>
  </entry>
</feed>"""

# A feed whose <link> tries to close the attribute it will be written into.
XSS_LINK = (
    b'<?xml version="1.0"?><rss version="2.0"><channel><title>Hostile</title>'
    b"<item><title>Evil</title>"
    b"<link>https://x.example/&quot; onmouseover=&quot;alert(1)</link>"
    b"<description>d</description></item></channel></rss>"
)


def _read(path: str) -> str:
    return open(path, encoding="utf-8").read() if os.path.isfile(path) else ""


def main() -> int:
    failures: list[str] = []

    for label, path in (
        ("the parser", PARSER),
        ("the routes", ROUTES),
        ("the importer", TRANSFER),
        ("the API client", CLIENT),
        ("the admin screen", SCREEN),
    ):
        if not os.path.isfile(path):
            failures.append(f"{label} is missing: {path}")
    if failures:
        for line in failures:
            print("  - %s" % line)
        print("\nFAIL: the chain is not present, so nothing was checked.")
        return 1

    try:
        from app.modules.dataexchange.application.feed_parser import parse_feed
    except Exception as exc:  # noqa: BLE001
        print("FAIL: the parser could not be imported: %s" % exc)
        return 1

    # ── 1. both formats parse ───────────────────────────────────────────────
    rss = parse_feed(RSS)
    atom = parse_feed(ATOM)

    if len(rss["posts"]) != 2:
        failures.append(
            "the RSS feed yielded %d posts, expected 2 — the untitled entry "
            "must be skipped and the other two kept" % len(rss["posts"])
        )
    if len(atom["posts"]) != 1:
        failures.append(
            "the Atom feed yielded %d posts, expected 1. An Atom-only parser "
            "reads as an empty feed, not as a wrong parser." % len(atom["posts"])
        )

    alpha = rss["posts"][0] if rss["posts"] else {}
    gamma = atom["posts"][0] if atom["posts"] else {}

    # ── 2. the shape `import_json` reads ───────────────────────────────────
    for key in ("title", "content", "status", "category_slug", "tag_slugs"):
        if key not in alpha:
            failures.append(
                "the parsed post has no %r. BlogTransferService.import_json "
                "reads that key; a dict without it imports cleanly and files "
                "the post wrong." % key
            )
    if alpha.get("category_slug") != "Tech":
        failures.append(
            "the per-item <category> did not reach category_slug (got %r) — an "
            "import where every post lands uncategorised looks successful"
            % alpha.get("category_slug")
        )
    if alpha.get("tag_slugs") != ["python"]:
        failures.append(
            "the post_tag category did not reach tag_slugs (got %r)"
            % alpha.get("tag_slugs")
        )
    # The full body, not the teaser: the fixture's description is
    # "Alpha teaser" and its `content:encoded` is "Alpha body", so either can
    # be asserted by name. Checking for a tag would only prove the fixture was
    # written the way the assertion expects.
    if "Alpha body" not in str(alpha.get("content", "")):
        failures.append(
            "content:encoded did not win over the plain-text description — "
            "otherwise every post imports as its teaser"
        )
    if "Alpha teaser" in str(alpha.get("content", "")):
        failures.append(
            "the plain-text description was imported as the body; a feed's "
            "description is a teaser in every real feed"
        )
    if "Gamma body" not in str(gamma.get("content", "")):
        failures.append(
            "the Atom <content> element was not read; only <summary> was, so "
            "every Atom post imports as its teaser"
        )

    # ── 3. drafts, never published ─────────────────────────────────────────
    if alpha.get("status") != "draft":
        failures.append(
            "imported entries are %r, not 'draft'. A feed publishes by "
            "definition; importing an archive as live posts puts unreviewed "
            "content on the storefront." % alpha.get("status")
        )

    # ── 4. the source link survives ────────────────────────────────────────
    if "probe.example/alpha" not in str(alpha.get("content", "")):
        failures.append(
            "the feed's own link was dropped. BlogPost has no source-URL "
            "column, so once the import is done there is no way to recover "
            "where a post came from."
        )

    # ── 5. a hostile link cannot inject markup ─────────────────────────────
    try:
        hostile_body = parse_feed(XSS_LINK)["posts"][0]["content"]
    except Exception as exc:  # noqa: BLE001
        failures.append("the hostile-feed probe raised instead of parsing: %s" % exc)
        hostile_body = ""

    if hostile_body:
        handlers: list[tuple[str, str, str]] = []

        class Collector(html.parser.HTMLParser):
            def handle_starttag(self, tag, attrs):  # noqa: ANN001
                for key, value in attrs:
                    if key.lower().startswith("on"):
                        handlers.append((tag, key, value or ""))

        collector = Collector()
        collector.feed(hostile_body)
        if handlers:
            failures.append(
                "a feed <link> produced live event-handler attributes %s in the "
                "imported body. The link comes from a feed this store has never "
                "seen and is written into an anchor, so an unescaped quote "
                "closes the attribute and puts a handler on every imported "
                "post." % handlers
            )

    # ── 6. the chain reaches the screen ────────────────────────────────────
    routes = _read(ROUTES)
    client = _read(CLIENT)
    screen = _read(SCREEN)

    for label, haystack, needle, why in (
        ("the routes", routes, "/import/feed", "an admin route for the importer"),
        ("the routes", routes, "import_json", "a call into the importer"),
        ("the API client", client, "previewFeed", "the preview call"),
        ("the API client", client, "importFeed", "the import call"),
        ("the admin screen", screen, "previewFeed(", "a control that runs it"),
        ("the admin screen", screen, "importFeed(", "a control that runs it"),
    ):
        if needle not in haystack:
            failures.append(
                "%s has no %r, so %s is missing. A parser with no route, or a "
                "route with no button, is a complete feature nobody can reach."
                % (label, needle, why)
            )

    if failures:
        print("FAIL: %d problem(s) with the feed importer:\n" % len(failures))
        for line in failures:
            print("  - %s" % line)
        return 1

    print(
        "PASS: RSS and Atom both parse, the output is the shape import_json "
        "reads, entries land as drafts with their source link, a hostile link "
        "cannot inject markup, and parser → route → client → screen is complete."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())