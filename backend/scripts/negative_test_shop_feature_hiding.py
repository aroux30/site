"""Negative test: prove check_shop_feature_hiding.py can actually fail.

A gate that cannot fail is not a gate. This re-injects the wishlist/compare
disabling defect into a throwaway copy of the frontend and asserts the gate
reports it. The real source is never touched — the gate is redirected at the
copy via the SHOP_HIDE_GATE_ROOT override.

The baseline matters: if the real frontend were already red, every injection
below would "fail the gate" for an unrelated reason and the test would prove
nothing.

    cd backend && PYTHONPATH=. python scripts/negative_test_shop_feature_hiding.py
"""

from __future__ import annotations

import io
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

_BACKEND = Path(__file__).resolve().parents[1]
_GATE = _BACKEND / "scripts" / "check_shop_feature_hiding.py"
_REAL_FRONTEND = _BACKEND.parent / "frontend"

_COPY_PATHS = (
    "app/admin/settings/page.tsx",
    "components/layout/header.tsx",
    "components/compare/floating-compare-bar.tsx",
    "components/account/account-dashboard.tsx",
    "components/store/feature-guard.tsx",
    "app/(store)/products/[slug]/page.tsx",
    "app/(store)/products/page.tsx",
    "app/(store)/compare/page.tsx",
    "app/(store)/favorites/page.tsx",
)

def _src(*lines: str) -> str:
    """Join source lines into the exact needle an injection targets.

    These anchors are multi-line JSX/TS fragments, so writing them as single
    literals would put most of them over the line limit and hurt readability.
    Joining keeps each line short while still matching the file byte-for-byte.
    """
    return "\n".join(lines)


_CASES: dict[str, tuple[str, str, str]] = {
    # The header stops reading the switches entirely — every guard below then
    # checks a hard-coded value. This is the subtlest case and the reason the
    # gate checks that the read exists at all.
    "header_ignores_switches": (
        "components/layout/header.tsx",
        "const shopFeatures = useShopFeatures();",
        "const shopFeatures = { wishlist: true, compare: true };",
    ),
    "header_compare_link_shown": (
        "components/layout/header.tsx",
        "{shopFeatures.compare && (\n                <Link href=\"/compare\"",
        "{\n                <Link href=\"/compare\"",
    ),
    "header_wishlist_link_shown": (
        "components/layout/header.tsx",
        '{shopFeatures.wishlist && (\n                <Link href="/account/favorites"',
        '{\n                <Link href="/account/favorites"',
    ),
    # The nav filter removed: a CMS menu entry would still link to a disabled
    # module even though both icon links are hidden.
    # The desktop nav's own filter (separate from the mobile list's).
    "desktop_nav_unfiltered": (
        "components/layout/header.tsx",
        ": fallbackNavigationLinks\n"
        "                    .filter((link) =>"
        " isFeatureGatedLink(link.href, shopFeatures))",
        ": fallbackNavigationLinks",
    ),
    # The admin panel toggle must really save. This is the bug the owner hit by
# clicking: the query result and the state shared one name, so the sync effect
# reverted the checkbox immediately after a SUCCESSFUL save.
    "admin_toggle_name_collision": (
        "app/admin/settings/page.tsx",
        _src(
            "  const {",
            "    loading: shopFeaturesLoading,",
            "    data: shopFeaturesData,",
            "    reload: reloadShopFeatures,",
        ),
        _src(
            "  const {",
            "    loading: shopFeaturesLoading,",
            "    shopFeatures,",
            "    reload: reloadShopFeatures,",
        ),
    ),
    "admin_toggle_effect_depends_on_state": (
        "app/admin/settings/page.tsx",
        "  }, [shopFeaturesLoading, shopFeaturesData]);",
        "  }, [shopFeaturesLoading, shopFeatures]);",
    ),
    "admin_toggle_no_reload": (
        "app/admin/settings/page.tsx",
        "      reloadShopFeatures();\n",
        "",
    ),
    # A CMS menu entry must not resurrect a disabled module either.
    "cms_menu_entry_unfiltered": (
        "components/layout/header.tsx",
        "                    .filter((item) =>"
        " isFeatureGatedLink(item.url, shopFeatures))",
        "",
    ),
    "floating_bar_shown": (
        "components/compare/floating-compare-bar.tsx",
        "    !shopFeatures.compare ||\n",
        "",
    ),
    # The real bug this store had: the rendered nav list uses `mobileMenu` when
    # a CMS menu is configured, and that branch was unfiltered — so the link
    # stayed on screen even with compare switched off. Injecting it must turn the
    # gate red, or the gate would repeat the mistake it exists to catch.
    "cms_menu_branch_unfiltered": (
        "components/layout/header.tsx",
        ").filter((link) =>"
        " isFeatureGatedLink(link.href, shopFeatures)).map((link) => (",
        ").map((link) => (",
    ),
    "mobile_list_unfiltered": (
        "components/layout/header.tsx",
        _src(
            "                  : navigationLinks",
            "                  // The CMS menu needs the same filter as the fallback: the",
            "                  // filter on navigationLinks only covers the non-CMS branch, so",
            "                  // without this an operator could keep /compare reachable by",
            "                  // having a CMS menu configured at all.",
            "                ).filter((link) =>"
            " isFeatureGatedLink(link.href, shopFeatures)).map((link) => (",
        ),
        _src(
            "                  : navigationLinks",
            "                ).map((link) => (",
        ),
    ),
    "account_nav_shown": (
        "components/account/account-dashboard.tsx",
        _src(
            "...(shopFeatures.wishlist",
            '      ? [{ key: "wishlist" as const, label: "علاقه‌مندی‌ها", icon: Heart,'
            " badge: wishlist.length }]",
            "      : []),",
        ),
        _src(
            '    { key: "wishlist" as const, label: "علاقه‌مندی‌ها", icon: Heart,'
            " badge: wishlist.length },",
        ),
    ),
    "product_detail_compare_shown": (
        "app/(store)/products/[slug]/page.tsx",
        _src(
            "{shopFeatures.compare && (",
            "                    <Button",
            '                      variant="outline"',
            '                      size="icon"',
            "                      onClick={handleToggleCompare}",
        ),
        _src(
            "{",
            "                    <Button",
            '                      variant="outline"',
            '                      size="icon"',
            "                      onClick={handleToggleCompare}",
        ),
    ),
    "product_list_compare_shown": (
        "app/(store)/products/page.tsx",
        _src(
            "{shopFeatures.compare && (",
            "              <button",
            '                type="button"',
            "                onClick={handleToggleCompare}",
        ),
        _src(
            "{",
            "              <button",
            '                type="button"',
            "                onClick={handleToggleCompare}",
        ),
    ),
    # The page guard stops redirecting, so a deep link still lands on the page.
    "page_guard_does_not_redirect": (
        "components/store/feature-guard.tsx",
        'if (resolved && !enabled) router.replace("/");',
        "void resolved; void enabled;",
    ),
    "compare_page_unguarded": (
        "app/(store)/compare/page.tsx",
        '<FeatureGuard feature="compare">\n      <ComparePageInner />\n    </FeatureGuard>',
        "<ComparePageInner />",
    ),
    "favorites_page_unguarded": (
        "app/(store)/favorites/page.tsx",
        '<FeatureGuard feature="wishlist">\n      <FavoritesPageInner />\n    </FeatureGuard>',
        "<FavoritesPageInner />",
    ),
}


def _run_gate(root: Path) -> int:
    env = dict(os.environ)
    env["SHOP_HIDE_GATE_ROOT"] = str(root)
    proc = subprocess.run(
        [sys.executable, str(_GATE), "--json"],
        capture_output=True, text=True, encoding="utf-8", env=env, cwd=str(_BACKEND),
    )
    return proc.returncode


def main() -> int:
    # Baseline: the real tree must be clean, otherwise every injection below
    # would "fail the gate" for a reason unrelated to the injection.
    if _run_gate(_REAL_FRONTEND) != 0:
        print("FAIL: the gate is already red on the real frontend; injections "
              "would prove nothing.")
        return 1
    print("PASS baseline: real frontend is green.")

    failures: list[str] = []

    for name, (rel, old, new) in _CASES.items():
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for p in _COPY_PATHS:
                dest = root / p
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(_REAL_FRONTEND / p, dest)

            target = root / rel
            text = target.read_text(encoding="utf-8")
            if old not in text:
                failures.append(f"{name}: injection anchor not found ({old[:60]!r})")
                continue
            target.write_text(text.replace(old, new, 1), encoding="utf-8")

            rc = _run_gate(root)
            if rc == 0:
                failures.append(f"{name}: gate did NOT fail on the injected defect")
            else:
                print(f"PASS negative: {name} -> gate failed as expected (rc={rc})")

    if failures:
        print("\nFAIL: negative test did not prove the gate can fail:")
        for f in failures:
            print("  -", f)
        return 1
    print(f"\nALL {len(_CASES)} NEGATIVE CASES PASSED: the gate fails on every "
          f"injected defect.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
