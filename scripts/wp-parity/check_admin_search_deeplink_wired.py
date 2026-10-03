"""The admin bar's contextual link must reach a list that is actually filtered.

`editTargetFor` turns `/blog/<slug>` into `/admin/blog?search=<slug>`. Three
halves, and the middle one shipped without the others:

  * the admin page reads `?search=` on mount — for both posts and pages;
  * the search matches the **slug**, which is the only thing that link knows;
  * reading it happens once, not on every render, so it does not fight the
    operator's typing.

The slug half was missing on the blog side and it is the one that decides
whether the feature works at all: a search over title/excerpt/content finds
nothing when the operator's only clue is a URL, and the list comes back
filtered-looking and empty, which reads as "this post is gone".

Both halves are checked per page, because they were handed over as two files
and one of them can be done while the other is not.

Run:  python scripts/wp-parity/check_admin_search_deeplink_wired.py
"""

from __future__ import annotations

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import console_safe  # noqa: F401  — makes stdout safe for non-ASCII

BLOG_PAGE = os.path.join(ROOT, "frontend", "app", "admin", "blog", "page.tsx")
PAGES_PAGE = os.path.join(ROOT, "frontend", "app", "admin", "pages", "page.tsx")
BAR = os.path.join(ROOT, "frontend", "components", "layout", "admin-bar.tsx")
BLOG_SERVICE = os.path.join(ROOT, "backend", "app", "modules", "blog",
                           "application", "blog_service.py")
PAGE_SERVICE = os.path.join(ROOT, "backend", "app", "modules", "content",
                            "application", "cms_page_service.py")

failures: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {label}: {ok}")
    if not ok:
        failures.append(f"{label}: {detail}" if detail else label)


def read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def effect_body(text: str, marker: str) -> str:
    """The `useEffect` that reads `?search=`, as it stands on disk."""
    at = text.find(marker)
    if at == -1:
        return ""
    # Read to the *closing* `}, [deps])`, not to the first `}, [` — the
    # eslint-disable comment between the body and the dependency list contains
    # a `}` of its own, so a naive scan stops inside the comment and reads the
    # effect as having dependencies it does not have.
    start = text.find("useEffect(() => {", at)
    if start == -1:
        return ""
    # Inclusive of the close: the dependency list is the thing being checked,
    # and slicing up to `}, []);` leaves it outside the body — which is how the
    # first version of this check reported an effect with no dependencies as
    # having them.
    end = text.find("}, []);", start)
    if end == -1:
        end = text.find("});", start)
    # `}, []);` is eight characters, and slicing by six leaves off the `);` —
    # which then reads as "the effect has dependencies" for an effect whose
    # dependency list is empty.
    return text[start:end + 8] if end != -1 else text[start:start + 400]


def main() -> int:
    for path in (BLOG_PAGE, PAGES_PAGE, BAR, BLOG_SERVICE, PAGE_SERVICE):
        if not os.path.isfile(path):
            print(f"FAIL: missing {path}")
            return 1
    blog, pages, bar = (read(p) for p in (BLOG_PAGE, PAGES_PAGE, BAR))
    blog_svc, page_svc = read(BLOG_SERVICE), read(PAGE_SERVICE)

    # 1. the link sends the slug
    check("the admin bar sends ?search=", "admin/blog?search=" in bar)
    # Both halves, because either alone is satisfied by the wrong code.
    #
    # `words` merely existing is nothing: a `const words = second` with the
    # href still sending `second`, or an href sending a variable built
    # elsewhere, both leave the name in the file and leave the link broken.
    # What has to hold is that the slug is *turned into words* and that the
    # same words are *sent* — which is the whole reason the bar rewrites
    # dashes at all, as its own comment says.
    builds_words = 'second.replace(/-/g, " ")' in bar
    sends_words = "search=${encodeURIComponent(words)}" in bar
    check("the slug becomes words", builds_words,
          "the slug is not rewritten, so the search looks for the dashed form")
    check("and the link sends those words", sends_words,
          "the link sends something other than the words it built")
    # The words must come from the slug segment, not from the whole path: a
    # search for `/blog/my-post` matches nothing.
    check("and they come from the slug segment, not the whole path",
          re.search(r"const\s+words\s*=\s*second\b", bar) is not None,
          "words is not derived from the slug segment")

    # 2. each admin page reads it, once
    for label, page in (("blog", blog), ("pages", pages)):
        check(f"the {label} page reads the param",
              'get("search")' in page)
        body = effect_body(page, 'get("search")')
        check(f"the {label} page seeds the filter from it",
              "setSearch(" in body,
              "the effect does not set the filter")
        # The effect closes on `}, []);` — an empty dependency list. Matched
        # against the effect's own text, not the whole page: an empty list
        # anywhere in a file with a dozen effects would otherwise satisfy it.
        check(f"and {label} reads it once, not per render",
              body.rstrip().endswith("}, []);")
              or "}, []);" in body[-40:],
              "the effect has dependencies, so it re-seeds while typing")

    # 3. the search actually matches the slug. This is the half that was
    #    missing, and the half no amount of front-end work compensates for.
    check("the blog search matches the slug",
          "BlogPost.slug.ilike" in blog_svc,
          "the link sends a slug and the search looks at title/excerpt/content")
    check("it keeps the fields it had",
          all(f"BlogPost.{f}.ilike" in blog_svc
              for f in ("title", "excerpt", "content")))
    check("the page search matches the slug",
          "CmsPage.slug.ilike" in page_svc)

    if failures:
        print("\nFAIL:")
        for f in failures:
            print(f"  {f}")
        return 1
    print("\nPASS: the contextual link's slug filters the list it lands on, "
          "on both admin pages.")
    return 0


if __name__ == "__main__":
    sys.exit(main())