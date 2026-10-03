"""The privacy-policy page selector reaches the storefront page itself.

The option (`privacy.policy_page`), the service, the public endpoint and the
admin card all existed — but `/privacy` hardcoded `slug="privacy"`, so an
operator who designated a different page saw their choice take effect on the
registration/comment links and nowhere on the page those links point at.

This checks the last hop: the storefront page resolves its slug from the
public endpoint rather than a literal, and still falls back to "privacy".

    python scripts/wp-parity/check_privacy_policy_selector.py
"""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(__file__))
import console_safe  # noqa: F401  — idempotent. A plain TextIOWrapper
# here is closed by the next module that wraps stdout, which is how a test
# that imports a guard ends up dying on "I/O operation on closed file".

PAGE = os.path.join(ROOT, "frontend", "app", "(store)", "privacy", "page.tsx")
ROUTES = os.path.join(ROOT, "backend", "app", "modules", "settings", "api", "routes.py")

failures: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {label}: {ok}")
    if not ok:
        failures.append(f"{label}: {detail}" if detail else label)


def main() -> int:
    page = open(PAGE, encoding="utf-8").read() if os.path.isfile(PAGE) else ""
    routes = open(ROUTES, encoding="utf-8").read() if os.path.isfile(ROUTES) else ""

    check("the public policy endpoint exists",
          "/public/privacy-policy" in routes)
    check("the storefront page resolves the slug from the endpoint",
          "fetchPolicySlug" in page and "/settings/public/privacy-policy" in page,
          "the page still hardcodes its slug")
    check("the metadata resolves the same slug, not a literal",
          'fetchCmsPage("privacy")' not in page,
          "generateMetadata still fetches the hardcoded slug")
    check("the shell takes the resolved slug",
          "<CmsPageShell slug={slug}" in page,
          "the resolved slug is not passed to the shell")
    check("the fallback keeps the old behaviour",
          '|| "privacy"' in page,
          "a store with no configured policy loses its page")

    if failures:
        print("\nFAIL:")
        for f in failures:
            print(f"  {f}")
        return 1
    print("\nPASS: the privacy-policy selector reaches the storefront page.")
    return 0


if __name__ == "__main__":
    sys.exit(main())