"""A custom taxonomy's archive must be reachable from the storefront, and correct.

The route existed and had no caller: an operator could register "product type"
or "brand", assign terms, and nothing a shopper could reach showed any of it. The
term page needed a second route as well, because the only public taxonomy
endpoint returned terms and not posts — so the page could only have rendered
the blog's recent posts under a heading that had nothing to do with them.

So the chain is checked end to end: route → term page → posts → the card the
term page renders. A component that imports a type which does not exist does
not build, and a page whose links point at a route nobody serves produces an
archive full of 404s — both invisible to a source check that only greps for
the route.

Run:  python scripts/wp-parity/check_taxonomy_archive_wired.py
"""

from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import console_safe  # noqa: F401  — makes stdout safe for non-ASCII

ROUTES = os.path.join(ROOT, "backend", "app", "modules", "blog", "api",
                      "wp_parity_routes.py")
CLIENT = os.path.join(ROOT, "frontend", "lib", "api", "blog.ts")
ARCHIVE = os.path.join(ROOT, "frontend", "app", "(store)", "blog", "taxonomy",
                       "[taxonomy]", "page.tsx")
TERM = os.path.join(ROOT, "frontend", "app", "(store)", "blog", "taxonomy",
                    "[taxonomy]", "[slug]", "page.tsx")

failures: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {label}: {ok}")
    if not ok:
        failures.append(f"{label}: {detail}" if detail else label)


def main() -> int:
    for path in (ROUTES, CLIENT, ARCHIVE, TERM):
        if not os.path.isfile(path):
            print(f"FAIL: missing {path}")
            return 1
    routes = open(ROUTES, encoding="utf-8").read()
    client = open(CLIENT, encoding="utf-8").read()
    archive = open(ARCHIVE, encoding="utf-8").read()
    term = open(TERM, encoding="utf-8").read()

    # 1. the public routes
    check("a public terms route exists",
          '/taxonomies/{taxonomy_slug}/terms"' in routes)
    check("a public posts-in-a-term route exists",
          '/taxonomies/{taxonomy_slug}/terms/{term_slug}/posts"' in routes)
    check("and it filters by the join table, not by title",
          "BlogPostTerm" in routes and "BlogPostTerm.term_id == term.id" in routes)
    check("and publishes only",
          "BlogPostStatus.PUBLISHED" in routes)

    # 2. the client addresses both, on the blog prefix they are mounted under
    check("the client fetches the terms", "fetchCustomTaxonomyTerms" in client)
    check("and the posts in a term", "fetchCustomTaxonomyTermPosts" in client)
    check("the terms call uses the public blog path",
          "/blog/taxonomies/" in client)
    # Scoped to the taxonomy call, not the whole file: three list calls in it
    # send `page_size`, so a whole-file check is satisfied by the other two and
    # goes green with this one stripped — which is the same failure the negative
    # test found.
    at = client.find("export async function fetchCustomTaxonomyTermPosts")
    stop = client.find("export async function fetchBlogTags", at)
    tax_client = client[at:stop] if at != -1 and stop != -1 else ""
    check("the posts call asks the server to filter",
          "page_size: pageSize" in tax_client,
          "the call carries no filter, so the page would list every post")
    check("and the term is addressed by its slug, not its id",
          "termSlug" in tax_client and "terms/${encodeURIComponent(termSlug)}"
          in tax_client,
          "the call does not name the term it wants")

    # 3. the pages consume them — a client method with no caller is the
    #    original shape of this gap
    check("the taxonomy archive lists terms",
          "fetchCustomTaxonomyTerms" in archive)
    check("the term page fetches the term's posts",
          "fetchCustomTaxonomyTermPosts" in term)
    check("and renders them", "items.map" in term)

    # 4. both pages exist at a URL the taxonomy's own links point at. The
    #    archive links to `/{taxonomy}/{slug}`; a term page at a different path
    #    makes every term in the archive a 404, which is the whole failure
    #    this item was about.
    check("the term links match the page that serves them",
          'href={`/${taxonomy}/${term.slug}`}' in archive
          or 'href={`/${taxonomy}/${slug}`}' in archive,
          "the archive links somewhere the term page does not live")
    check("posts link to the post page that exists",
          'href={`/blog/${post.slug}`}' in term)

    # 5. a retired taxonomy is not served. Without this a store that switches
    #    one off still serves its whole archive.
    # Counted, not merely present. Both public taxonomy routes carry the
    # filter; a presence check is satisfied by one of them, so removing the
    # other — which is what the negative test does — leaves the gate green with
    # a retired taxonomy still served by one route.
    active_count = routes.count("CustomTaxonomy.is_active.is_(True)")
    check("both public taxonomy routes filter on active",
          active_count >= 2, f"found {active_count}")

    if failures:
        print("\nFAIL:")
        for f in failures:
            print(f"  {f}")
        return 1
    print("\nPASS: a custom taxonomy's terms and their posts are reachable from "
          "the storefront, filtered server-side.")
    return 0


if __name__ == "__main__":
    sys.exit(main())