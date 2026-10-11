"""Read-only gate: the wishlist/compare switches HIDE the module, not just refuse it.

This is the sibling of ``check_wallet_switch_hiding.py`` and exists for the
same reason. A server-side switch check is structurally blind to "the module is
switched off but the storefront still advertises it": the mutations correctly
422 while the header link, the product-page button and the page itself remain.
That is the defect an operator reported on the wallet, and the same trap applies
to every storefront feature. So this gate reads the CLIENT source.

It checks both halves of the contract:

* every rendering surface is behind the switch; and
* the switch is actually READ from the API (otherwise every guard is checking
  a hard-coded ``true`` and the gate would pass on a page that hides nothing).

Anchors are required to be UNIQUE — a windowed substring search is satisfied by
a guard belonging to a different surface, which is how two of the eight cases in
the wallet gate were silently vacuous.

Read-only: reads files, never builds or serves anything.

    cd backend && PYTHONPATH=. python scripts/check_shop_feature_hiding.py
    cd backend && PYTHONPATH=. python scripts/check_shop_feature_hiding.py --json

Exits 0 when every surface is guarded, 1 when any finding exists.
"""

from __future__ import annotations

import io
import json
import os
import re
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

_SITE = Path(__file__).resolve().parents[2]
# Lets the negative test point the gate at an injected copy of the frontend.
_root = os.environ.get("SHOP_HIDE_GATE_ROOT")
_FRONTEND = Path(_root) if _root else _SITE / "frontend"

_HEADER = "components/layout/header.tsx"
_COMPARE_BAR = "components/compare/floating-compare-bar.tsx"
_PRODUCT_DETAIL = "app/(store)/products/[slug]/page.tsx"
_PRODUCT_LIST = "app/(store)/products/page.tsx"
_ACCOUNT = "components/account/account-dashboard.tsx"
_GUARD = "components/store/feature-guard.tsx"
_ADMIN_SETTINGS = "app/admin/settings/page.tsx"


def _read(rel: str) -> str | None:
    path = _FRONTEND / rel
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def _ctx(text: str, needle: str, before: int = 400, after: int = 400) -> str:
    """The window of source around the LAST occurrence of ``needle``.

    ``rfind`` plus the uniqueness requirement below keeps "there is a guard
    somewhere" from being mistaken for "this surface is guarded".
    """
    i = text.rfind(needle)
    if i < 0:
        return ""
    return text[max(0, i - before) : i + len(needle) + after]


def _require_unique(text: str, needle: str, findings: list[str], where: str) -> None:
    if text.count(needle) != 1:
        findings.append(
            f"{where}: anchor {needle[:50]!r} occurs {text.count(needle)}x — "
            f"the gate can no longer tell this surface from another; update the "
            f"anchor rather than letting the check go vacuous"
        )


def _check_header(findings: list[str]) -> None:
    text = _read(_HEADER)
    if text is None:
        findings.append(f"{_HEADER}: not found under {_FRONTEND}")
        return

    # The switch state must reach the header at all.
    if "useShopFeatures()" not in text:
        findings.append(f"{_HEADER}: does not read the feature switches")

    # 1. The desktop icon links.
    # 1. The desktop icon links. Two wishlist links exist (the icon and the
    #    mobile menu), so they are checked separately with distinct anchors
    #    rather than through a uniqueness requirement that could not hold.
    _require_unique(text, 'href="/compare"', findings, _HEADER)
    compare_icon = _ctx(text, 'href="/compare"', before=120, after=120)
    if "shopFeatures.compare" not in compare_icon:
        findings.append(
            f"{_HEADER}: the compare icon link is not behind the switch"
        )

    # Both wishlist links must be guarded; a header that hides the desktop icon
    # but leaves the mobile menu entry is the same defect one breakpoint later.
    unguarded_fav = 0
    for match in re.finditer(r'href="/account/favorites"', text):
        window = text[max(0, match.start() - 200) : match.end() + 60]
        if "shopFeatures.wishlist" not in window:
            unguarded_fav += 1
    if unguarded_fav:
        findings.append(
            f"{_HEADER}: {unguarded_fav} wishlist link(s) render while the "
            f"module is off"
        )

    # 2. The nav link list — this is the fallback/CMS menu, and filtering only
    #    the fallback would let an operator re-enable a disabled module by
    #    adding the link in the CMS menu.
    #
    #    Presence is not wiring: the helper could exist while the nav list never
    #    calls it, which is exactly what the negative test injects. Require the
    #    CALL on the navigationLinks assignment, not just the definition.
    if "isFeatureGatedLink" not in text:
        findings.append(
            f"{_HEADER}: nav links are not filtered by the switch — a CMS menu "
            f"entry would still link to a disabled module"
        )
    nav_assignment = _ctx(text, "fallbackNavigationLinks\n  ).filter", before=300, after=200)
    if not nav_assignment:
        # Fall back to a looser anchor in case the formatting shifted.
        nav_assignment = _ctx(text, "fallbackNavigationLinks", before=200, after=400)
    if "isFeatureGatedLink(link.href" not in nav_assignment:
        findings.append(
            f"{_HEADER}: the navigation link list is built without calling "
            f"isFeatureGatedLink — the helper exists but nothing uses it"
        )

    # 3. The header renders the nav THREE separate times — the mobile list, the
    #    desktop CMS menu, and the desktop fallback — and each one builds its
    #    own list. Filtering only the already-filtered `navigationLinks` variable
    #    leaves the other two open, so an operator who switched a module off
    #    could keep it reachable simply by having a CMS menu — which is exactly
    #    the state this store is in. Every render site must filter for itself.
    render_site = _ctx(text, ": navigationLinks", before=500, after=600)
    if "isFeatureGatedLink(link.href" not in render_site:
        findings.append(
            f"{_HEADER}: the rendered mobile nav list is not filtered — with a "
            f"CMS menu configured the unfiltered `mobileMenu` branch is used, so "
            f"a disabled module stays reachable"
        )

    desktop_nav = _ctx(text, ": fallbackNavigationLinks", before=200, after=600)
    if "isFeatureGatedLink(link.href" not in desktop_nav:
        findings.append(
            f"{_HEADER}: the DESKTOP nav does not filter its links — it is a "
            f"separate render from the mobile list, so filtering one leaves the "
            f"other advertising a disabled module"
        )

    cms_branch = _ctx(text, "? cmsMenu", before=100, after=300)
    if "isFeatureGatedLink(item.url" not in cms_branch:
        findings.append(
            f"{_HEADER}: the CMS menu branch is not filtered — an operator can "
            f"keep a disabled module reachable by having a CMS menu configured"
        )


def _check_compare_bar(findings: list[str]) -> None:
    text = _read(_COMPARE_BAR)
    if text is None:
        findings.append(f"{_COMPARE_BAR}: not found under {_FRONTEND}")
        return
    guard = _ctx(text, "products.length === 0", before=200, after=80)
    if "shopFeatures.compare" not in guard:
        findings.append(
            f"{_COMPARE_BAR}: the floating bar still renders while compare is off"
        )


def _check_product_pages(findings: list[str]) -> None:
    for rel, label, needle in (
        (_PRODUCT_DETAIL, "compare", 'aria-label={inCompare ? "حذف از لیست مقایسه"'),
        (_PRODUCT_DETAIL, "wishlist", 'aria-label="افزودن به علاقه‌مندی‌ها"'),
        (_PRODUCT_LIST, "compare", 'aria-label={inCompare ? "حذف از مقایسه"'),
    ):
        text = _read(rel)
        if text is None:
            findings.append(f"{rel}: not found under {_FRONTEND}")
            continue
        # Every occurrence of a compare/wishlist toggle must be guarded, so
        # check them all rather than the first. The window is wide because the
        # guard sits BEFORE a multi-line Button whose className spans several
        # lines — a narrower window saw the aria-label but not the guard and
        # reported a false positive.
        unguarded = 0
        for match in re.finditer(re.escape(needle), text):
            window = text[max(0, match.start() - 1400) : match.end() + 200]
            if f"shopFeatures.{label}" not in window:
                unguarded += 1
        if unguarded:
            findings.append(
                f"{rel}: {unguarded} {label} toggle(s) render while the module is off"
            )


def _check_account(findings: list[str]) -> None:
    text = _read(_ACCOUNT)
    if text is None:
        findings.append(f"{_ACCOUNT}: not found under {_FRONTEND}")
        return

    _require_unique(text, 'label: "علاقه‌مندی‌ها"', findings, _ACCOUNT)
    nav = _ctx(text, 'label: "علاقه‌مندی‌ها"', before=200, after=60)
    if "shopFeatures.wishlist" not in nav:
        findings.append(
            f"{_ACCOUNT}: the wishlist nav entry is not behind the switch"
        )

    tab = _ctx(text, 'activeTab === "wishlist"', before=120, after=60)
    if "shopFeatures.wishlist" not in tab:
        findings.append(f"{_ACCOUNT}: the wishlist tab is not behind the switch")


def _check_page_guard(findings: list[str]) -> None:
    """The pages themselves must redirect, not render and then fail."""
    guard = _read(_GUARD)
    if guard is None:
        findings.append(f"{_GUARD}: not found under {_FRONTEND}")
        return
    if 'router.replace("/")' not in guard:
        findings.append(
            f"{_GUARD}: the page guard does not redirect when a feature is off"
        )

    for rel, label in (
        ("app/(store)/compare/page.tsx", "compare"),
        ("app/(store)/favorites/page.tsx", "wishlist"),
    ):
        text = _read(rel)
        if text is None:
            findings.append(f"{rel}: not found under {_FRONTEND}")
            continue
        if f'<FeatureGuard feature="{label}">' not in text:
            findings.append(
                f"{rel}: the page is not wrapped in FeatureGuard, so a deep link "
                f"still lands on a page for a disabled module"
            )


def _check_admin_toggle(findings: list[str]) -> None:
    """The admin toggle must actually save, not just flip a local boolean.

    The bug this pins: the page destructured the query result as
    ``shopFeatures``, the SAME name as the state variable holding the checkbox
    values. The syncing effect therefore read the state (not the fetched data),
    re-ran on every ``setShopFeatures`` and reset the checkbox to its pre-click
    value — so a click showed a red "save failed" toast and left the box on,
    while the PUT had in fact succeeded. Every API-level test passed; only a
    real click on the panel exposed it.
    """
    text = _read(_ADMIN_SETTINGS)
    if text is None:
        findings.append(f"{_ADMIN_SETTINGS}: not found under {_FRONTEND}")
        return

    # The query result must NOT be bound to the same identifier as the state.
    if re.search(r"^\s*const \[shopFeatures, setShopFeatures\]", text, re.MULTILINE) and re.search(
        r"^\s*\}\s*=\s*useAdminQuery", text, re.MULTILINE
    ):
        # Look for `shopFeatures,` appearing as a destructured query key.
        if re.search(r"^\s*data:\s*shopFeatures\s*,", text, re.MULTILINE) or re.search(
            r"^\s*shopFeatures,\s*$", text, re.MULTILINE
        ):
            findings.append(
                f"{_ADMIN_SETTINGS}: the query result is destructured as "
                f"`shopFeatures`, the same name as the state variable — the "
                f"syncing effect then reads state, re-runs on every setState and "
                f"reverts the toggle. Use a distinct name (e.g. shopFeaturesData)"
            )

    # The effect must depend on the FETCHED data, not on the state it writes.
    effect = _ctx(text, "shopFeaturesLoading || !shopFeaturesData", before=200, after=400)
    if not effect:
        findings.append(
            f"{_ADMIN_SETTINGS}: the feature-sync effect does not guard on the "
            f"fetched data (`shopFeaturesLoading || !shopFeaturesData`)"
        )
    if "}, [shopFeaturesLoading, shopFeaturesData]);" not in text:
        findings.append(
            f"{_ADMIN_SETTINGS}: the feature-sync effect does not list the "
            f"fetched data in its dependency array — depending on the state it "
            f"writes would loop"
        )

    # A successful save must refresh from the server, not trust local state.
    if "reloadShopFeatures()" not in text:
        findings.append(
            f"{_ADMIN_SETTINGS}: a successful save does not reload the switches "
            f"from the server"
        )


def main() -> int:
    as_json = "--json" in sys.argv
    findings: list[str] = []

    _check_header(findings)
    _check_compare_bar(findings)
    _check_product_pages(findings)
    _check_account(findings)
    _check_page_guard(findings)
    _check_admin_toggle(findings)

    ok = not findings
    if as_json:
        print(json.dumps({
            "gate": "shop_feature_hiding",
            "ok": ok,
            "measured": True,
            "root": str(_FRONTEND),
            "findings": findings,
        }, ensure_ascii=False))
    else:
        if ok:
            print("PASS: every wishlist/compare surface is hidden when its switch is off.")
        else:
            print(f"FAIL: {len(findings)} unguarded surface(s):")
            for f in findings:
                print(f"  - {f}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
