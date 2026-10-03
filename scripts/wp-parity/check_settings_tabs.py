"""The settings screen is grouped into tabs, and every group is reachable.

The page was one long scroll of every settings card — identity, tax, payment
methods, SMS, SMTP, Telegram, security — so "where do I change the SMTP host"
meant scrolling past the tax form. This checks the two things that make the
grouping real rather than decorative:

  * a tab bar exists with the role/aria wiring a screen reader needs;
  * every group id in the bar has a matching content block — a tab that
    switches to nothing is worse than no tab, because the settings it names
    are then unreachable.

Run:  python scripts/wp-parity/check_settings_tabs.py
"""

from __future__ import annotations

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PAGE = os.path.join(ROOT, "frontend", "app", "admin", "settings", "page.tsx")

failures: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {label}: {ok}")
    if not ok:
        failures.append(f"{label}: {detail}" if detail else label)


def main() -> int:
    if not os.path.isfile(PAGE):
        print(f"FAIL: the settings page does not exist at {PAGE}")
        return 1
    src = open(PAGE, encoding="utf-8").read()

    check("the page has a tab bar", 'role="tablist"' in src,
          "no tablist — the page is still one long scroll")

    # The tab ids in the bar. `["general", "عمومی", Store]` style entries.
    bar_ids = re.findall(
        r'\[\s*"(general|content|financial|communication|security)"\s*,',
        src,
    )
    check("the tab bar lists the five groups", len(set(bar_ids)) == 5,
          f"ids={sorted(set(bar_ids))}")

    # A content block per group: `activeTab === "x" && (`.
    block_ids = set(
        re.findall(
            r'activeTab === "(general|content|financial|communication|security)"',
            src,
        )
    )
    missing = sorted(set(bar_ids) - block_ids)
    check("every tab has a content block", not missing,
          f"tabs with nothing behind them: {missing}")

    # State and aria wiring: a tab bar whose selected state never changes is
    # a decorative row of buttons.
    check("the active tab is state, not a constant", "useState" in src and "activeTab" in src)
    check("the tabs expose aria-selected", "aria-selected" in src,
          "a screen reader cannot tell which tab is active")
    check("tabs are buttons with type=button",
          src.count('type="button"') >= 5,
          "a tab inside a form without type=button submits the form")

    if failures:
        print("\nFAIL:")
        for f in failures:
            print(f"  {f}")
        return 1
    print("\nPASS: the settings screen is tabbed, every group is reachable, "
          "and the tab bar is accessible.")
    return 0


if __name__ == "__main__":
    sys.exit(main())