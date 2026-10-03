"""WXR import must parse a real WordPress file, not just exist.

The three things a straightforward XML parser gets wrong here are invisible to a
source check and were all found by running a realistic file against the parser:

  * `content:encoded` holds CDATA *with markup in it*. Reading `.text` stops at
    the first child element, so a post containing an `<img>` comes back
    truncated at the image and the rest is gone — silently, and with no error.
  * `0000-00-00 00:00:00` is what WordPress writes for an unscheduled post. It
    is not a date any parser accepts, and importing it lands on year zero.
  * every item carries a `<wp:status>`. Importing them all as published turns
    an author's drafts into live pages, which is the worst possible outcome
    for a migration tool.

So this *runs* the parser against a fixture in WordPress's own shape and asserts
on what came out. A source check would pass with `.text` swapped back in.

The chain is checked as well, because the parser being correct and unreachable
is the same failure as it not existing: route → parse_wxr → the existing
`import_json`, never a second import implementation that drifts.

Run:  python scripts/wp-parity/check_wxr_import_behaviour.py
"""

from __future__ import annotations

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "backend"))
import console_safe  # noqa: F401  — makes stdout safe for non-ASCII

PARSER = os.path.join(ROOT, "backend", "app", "modules", "blog",
                      "application", "wxr_parser.py")
ROUTES = os.path.join(ROOT, "backend", "app", "modules", "blog",
                      "api", "wp_parity_routes.py")
TRANSFER = os.path.join(ROOT, "backend", "app", "modules", "blog",
                        "application", "transfer_service.py")
TAB = os.path.join(ROOT, "frontend", "components", "admin", "blog",
                   "transfer-tab.tsx")
CLIENT = os.path.join(ROOT, "frontend", "lib", "api", "wp-parity.ts")

failures: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {label}: {ok}")
    if not ok:
        failures.append(f"{label}: {detail}" if detail else label)


def read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


#: WordPress's own namespace set, at 1.2. The version in that URI is what a
#: parser must not pin — 1.1 files exist and third-party exporters differ.
WXR = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
     xmlns:excerpt="http://wordpress.org/export/1.2/excerpt/"
     xmlns:content="http://purl.org/rss/1.0/modules/content/"
     xmlns:dc="http://purl.org/dc/elements/1.1/"
     xmlns:wp="http://wordpress.org/export/1.2/">
<channel>
  <title>WordPress Blog</title>
  <link>https://old.example</link>
  <wp:author>
    <wp:author_login><![CDATA[ali]]></wp:author_login>
    <wp:author_display_name><![CDATA[علی رضایی]]></wp:author_display_name>
  </wp:author>
  <item>
    <title>نوشتهٔ منتشرشده</title>
    <dc:creator><![CDATA[ali]]></dc:creator>
    <content:encoded><![CDATA[
      <p>متن CDATA و یک تصویر</p>
      <img src="https://old.example/a.jpg" alt="a" />
      <p>پایان نوشته</p>
    ]]></content:encoded>
    <excerpt:encoded><![CDATA[خلاصه]]></excerpt:encoded>
    <wp:post_id>42</wp:post_id>
    <wp:post_date_gmt><![CDATA[2026-09-01 10:00:00]]></wp:post_date_gmt>
    <wp:status><![CDATA[publish]]></wp:status>
    <wp:post_name><![CDATA[first-post]]></wp:post_name>
    <wp:post_type><![CDATA[post]]></wp:post_type>
    <wp:comment_status><![CDATA[open]]></wp:comment_status>
    <category domain="category" nicename="news"><![CDATA[اخبار]]></category>
    <category domain="post_tag" nicename="tech"><![CDATA[فناوری]]></category>
    <wp:comment>
      <wp:comment_id>7</wp:comment_id>
      <wp:comment_author><![CDATA[مریم]]></wp:comment_author>
      <wp:comment_author_email><![CDATA[m@example.com]]></wp:comment_author_email>
      <wp:comment_author_IP><![CDATA[192.0.2.1]]></wp:comment_author_IP>
      <wp:comment_content><![CDATA[عالی بود]]></wp:comment_content>
      <wp:comment_approved><![CDATA[1]]></wp:comment_approved>
      <wp:comment_type><![CDATA[comment]]></wp:comment_type>
      <wp:comment_parent>0</wp:comment_parent>
      <wp:comment_post_id>42</wp:comment_post_id>
    </wp:comment>
    <wp:comment>
      <wp:comment_id>8</wp:comment_id>
      <wp:comment_author><![CDATA[سارا]]></wp:comment_author>
      <wp:comment_approved><![CDATA[0]]></wp:comment_approved>
      <wp:comment_type><![CDATA[comment]]></wp:comment_type>
      <wp:comment_parent>7</wp:comment_parent>
      <wp:comment_post_id>42</wp:comment_post_id>
    </wp:comment>
  </item>
  <item>
    <title>با فرزند واقعی</title>
    <content:encoded>متن <strong>مهم</strong> و <em>تأکید</em> پایان</content:encoded>
    <wp:post_type><![CDATA[post]]></wp:post_type>
    <wp:status><![CDATA[publish]]></wp:status>
  </item>
  <item>
    <title>پیش‌نویس</title>
    <wp:post_type><![CDATA[post]]></wp:post_type>
    <wp:status><![CDATA[draft]]></wp:status>
    <wp:post_date_gmt><![CDATA[0000-00-00 00:00:00]]></wp:post_date_gmt>
  </item>
  <item>
    <title>یک پیوست</title>
    <wp:post_type><![CDATA[attachment]]></wp:post_type>
  </item>
</channel>
</rss>
"""


def main() -> int:
    for path in (PARSER, ROUTES, TRANSFER, TAB, CLIENT):
        if not os.path.isfile(path):
            print(f"FAIL: missing {path}")
            return 1

    from app.modules.blog.application.wxr_parser import parse_wxr

    parsed = parse_wxr(WXR)

    # 1. markup inside CDATA survives whole. `.text` would stop at <p> and
    #    return only "متن" — a shorter string, no error, a post missing its
    #    second half.
    body = parsed["posts"][0]["content"]
    check("CDATA content survives whole",
          "پایان نوشته" in body, f"truncated at {len(body)} chars")
    check("a tag inside the CDATA survives", "<img" in body)

    # The case the reader is for: real child elements. ElementTree turns CDATA
    # into a plain string, so `itertext()` and `.text` agree there — the two
    # only differ when the content is actual markup, which some exporters emit.
    # With `.text` this string stops after the first word and the rest of the
    # post is gone with no error raised.
    child = next((p for p in parsed["posts"] if p["title"] == "با فرزند واقعی"), None)
    check("content that is real child markup is found", child is not None)
    if child:
        text = child["content"]
        check("text after the first child element survives", "مهم" in text,
              f"truncated at {text!r}")
        check("and after the second one too", "پایان" in text,
              f"truncated at {text!r}")

    # 2. the unscheduled date is not a date
    drafts = [p for p in parsed["posts"] if p["status"] == "draft"]
    check("the zero-date post is the draft one", len(drafts) == 1,
          f"{len(drafts)} drafts")
    if drafts:
        check("0000-00-00 becomes no date, not year zero",
              drafts[0]["published_at"] is None,
              str(drafts[0]["published_at"]))

    # 3. a draft stays a draft
    check("a draft is not imported as published", len(drafts) == 1,
          str([p["status"] for p in parsed["posts"]]))

    # 4. non-post types are excluded
    check("attachments are not posts",
          not any("پیوست" == p["title"] for p in parsed["posts"]),
          f"{[p['title'] for p in parsed['posts']]}")

    # 5. taxonomy and authors survive, because a migration that loses the
    #    category names has to redo them by hand
    check("categories are collected",
          [c["name"] for c in parsed["categories"]] == ["اخبار"])
    check("tags are kept separate from categories",
          [t["name"] for t in parsed["tags"]] == ["فناوری"])
    check("the author's display name comes from the author block",
          parsed["posts"][0]["author_name"] == "علی رضایی",
          str(parsed["posts"][0]["author_name"]))

    # 6. comments: approved, held, and threaded
    statuses = sorted(c["status"] for c in parsed["comments"])
    check("an unapproved comment stays pending",
          statuses == ["approved", "pending"], str(statuses))
    check("a reply keeps its parent",
          any(c["parent"] == "7" for c in parsed["comments"]))
    check("a comment's address is carried",
          any(c["author"] == "m@example.com" for c in parsed["comments"]))

    # 7. The chain, from the operator's hands inward. A parser, a route and a
    #    client method still leave the feature unreachable if no page calls it —
    #    and that is how this shipped the first time: the whole backend existed
    #    and the transfer tab only accepted JSON, so an operator with a WordPress
    #    file had nothing to click.
    tab = read(TAB)
    client = read(CLIENT)

    check("the transfer tab accepts an XML file",
          'accept="text/xml,application/xml,.xml"' in tab,
          "the operator cannot pick a WXR file")
    check("it has a separate handler, not a JSON fallback",
          "handleImportWxr" in tab)
    check("and that handler posts the file rather than parsing it as JSON",
          "blogTransferApi.importWxr(file)" in tab
          and "JSON.parse" not in tab.split("const handleImportWxr")[1].split("const ")[0],
          "the WXR handler parses the file instead of sending it")
    check("the tab imports the tab, not an alias of something else",
          "useRef<HTMLInputElement>" in tab and "wxrRef" in tab)

    check("the client has an importWxr method", "importWxr" in client)
    check("it sends multipart — an XML body cannot be a JSON dict",
          "FormData" in client and "multipart/form-data" in client)
    check("to the WXR route", "/admin/blog/import/wxr" in client)
    check("and the JSON route stays for JSON",
          '"/admin/blog/import"' in client)

    # The parser being correct and unreachable is the same failure as it not
    # existing.
    routes = read(ROUTES)
    check("the route exists", '"/import/wxr"' in routes)
    check("and calls the parser", "parse_wxr(raw)" in routes)
    check("then hands off to the existing import_json",
          "BlogTransferService.import_json" in routes)
    check("a second import implementation is not written here",
          "def import_wxr" not in routes)
    check("the export carries comments now",
          '"comments": comments_data' in read(TRANSFER))

    # 8. a file that is not XML fails loudly rather than importing nothing
    try:
        parse_wxr(b"this is not xml at all")
        raised = False
    except ValueError:
        raised = True
    check("a non-XML file is refused, not silently empty", raised)

    # A well-formed document with no <channel>: ElementTree is happy, and the
    # only thing standing between it and an empty import is the check below.
    # The previous version of this test passed a fragment with no root element
    # at all, which fails to parse — so it proved nothing about the guard.
    try:
        parse_wxr('<?xml version="1.0"?><rss version="2.0"></rss>')
        no_channel = False
    except ValueError:
        no_channel = True
    check("a file with no channel is refused", no_channel)

    if failures:
        print("\nFAIL:")
        for f in failures:
            print(f"  {f}")
        return 1
    print("\nPASS: a WordPress file imports with its markup, its dates, its "
          "drafts and its threads intact.")
    return 0


if __name__ == "__main__":
    sys.exit(main())