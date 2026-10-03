"""The admin bar links to the editor of the object you are looking at.

P2 "داشبورد: نوار مدیریت در فرانت". The bar existed with generic navigation
(products/orders/users/blog/settings), but WordPress's core affordance is the
*contextual* one: "Edit Page" for the page in front of you. Without it an
operator checking a change still had to find the object by hand.

This checks the mapping and the two links it depends on:

  * `/blog/<slug>` -> the blog list, searched by the slug's words (the list
    searches titles, and a slug is the slugified title);
  * `/products/<slug>` -> the products list, searched by slug (the list now
    matches slug as well as name/sku/brand);
  * `/<slug>` -> the pages list, searched by slug (the CMS list searches
    title OR slug server-side);
  * storefront routes that are not objects (cart, checkout, ...) get no link —
    a link on the cart would point at nothing.

    python scripts/wp-parity/check_admin_bar_contextual.py
"""

from __future__ import annotations

import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "backend"))
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(__file__))
import console_safe  # noqa: F401  — idempotent; a plain TextIOWrapper
# here is closed by any later module that wraps stdout.

BAR = os.path.join(ROOT, "frontend", "components", "layout", "admin-bar.tsx")
PRODUCTS = os.path.join(ROOT, "frontend", "app", "admin", "products", "page.tsx")

failures: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {label}: {ok}")
    if not ok:
        failures.append(f"{label}: {detail}" if detail else label)


def main() -> int:
    bar = open(BAR, encoding="utf-8").read() if os.path.isfile(BAR) else ""
    products = open(PRODUCTS, encoding="utf-8").read() if os.path.isfile(PRODUCTS) else ""

    check("the bar computes a contextual edit target",
          "editTargetFor" in bar, "no contextual mapping in the bar")
    # The render condition, anchored: a sabotage that guards the block with
    # `false &&` left the old substring check green. The gate has to match
    # `{editTarget && (` at the start of its own line, which a disabled guard
    # does not produce.
    check("the bar renders the contextual link",
          re.search(r"^\s*\{editTarget && \(", bar, re.M) is not None
          and "editTarget.href" in bar,
          "the mapping exists but no link renders (or the render is disabled)")
    check("storefront non-object routes are excluded",
          "RESERVED" in bar, "the link would appear on the cart and checkout")
    check("the blog slug is searched as words",
          "replace(/-/g, \" \")" in bar,
          "a whole slug would not match the title search")

    # The products list must match slugs, or the link lands on nothing.
    check("the products list matches slug",
          "item.slug" in products,
          "the admin bar links by slug but the list cannot match one")
    check("the products list reads the search param",
          'get("search")' in products,
          "the ?search= the bar sends is ignored")
    check("the products type carries the slug",
          "slug?: string" in products or "slug: p.slug" in products,
          "slug never reaches the filter")

    if failures:
        print("\nFAIL:")
        for f in failures:
            print(f"  {f}")
        return 1
    print("\nPASS: the admin bar links to the editor of the object on screen, "
          "and the products list can be reached by its slug.")
    return 0


if __name__ == "__main__":
    sys.exit(main())