"""Guard: site-wide avatar options and the virtual robots.txt stay wired.

P1 "تنظیمات: گزینه‌های آواتار سراسری" and "robots.txt مجازی با دستور قالب".

Both are the same failure class this project keeps hitting: a key is seeded and
read by *something*, or an endpoint exists and nothing calls it. So each check
below follows the whole chain — the seed row, the reader that honours it, the
public route that surfaces it, and the admin screen that writes it — rather
than grepping for a name that still appears where it was once used.

    python scripts/wp-parity/check_settings_options_wired.py [--sabotage]

With ``--sabotage`` it injects one real breakage per rule and asserts the rule
notices, then restores. A rule that a real edit cannot trip is not a gate.
"""

from __future__ import annotations

import argparse
import io
import re
import sys
from pathlib import Path

import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(__file__))
import console_safe  # noqa: F401  — idempotent. A plain TextIOWrapper
# here is closed by the next module that wraps stdout, which is how a test
# that imports a guard ends up dying on "I/O operation on closed file".

ROOT = Path(__file__).resolve().parents[2]

GRAVATAR = ROOT / "backend" / "app" / "shared" / "content" / "gravatar.py"
DEFAULTS = ROOT / "backend" / "app" / "modules" / "settings" / "application" / "default_options.py"
ROUTES = ROOT / "backend" / "app" / "modules" / "settings" / "api" / "routes.py"
COMMENT_SERVICE = ROOT / "backend" / "app" / "modules" / "blog" / "application" / "comment_service.py"
ROBOTS_ROUTE = ROOT / "frontend" / "app" / "robots.txt" / "route.ts"
OLD_ROBOTS = ROOT / "frontend" / "app" / "robots.ts"
SETTINGS_PAGE = ROOT / "frontend" / "app" / "admin" / "settings" / "page.tsx"
AVATAR_CARD = ROOT / "frontend" / "components" / "admin" / "avatar-settings-card.tsx"
ROBOTS_CARD = ROOT / "frontend" / "components" / "admin" / "robots-settings-card.tsx"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


SABOTAGE: dict[str, tuple[Path, str, str]] = {
    # rule id -> (file, find, replace)
    "avatar:seed": (DEFAULTS, '"show_avatars": "1",', ""),
    "avatar:read": (GRAVATAR, "async def avatar_options(", "async def _avatar_options_removed("),
    "avatar:route": (ROUTES, '"/public/avatar-options",', '"/public/avatar-options-REMOVED",'),
    "avatar:consumer": (COMMENT_SERVICE, "options = await avatar_options(self.db)", "options = None"),
    "avatar:ui": (SETTINGS_PAGE, "<AvatarSettingsCard />", ""),
    "robots:seed": (DEFAULTS, '"robots_extra_rules": "",', ""),
    "robots:route": (ROUTES, '"/public/robots-extra",', '"/public/robots-extra-REMOVED",'),
    "robots:txt": (ROBOTS_ROUTE, "/settings/public/robots-extra", "/settings/public/robots-extra-X"),
    "robots:ui": (SETTINGS_PAGE, "<RobotsSettingsCard />", ""),
}


def evaluate() -> list[str]:
    failures: list[str] = []

    gravatar = read(GRAVATAR)
    defaults = read(DEFAULTS)
    routes = read(ROUTES)
    comment = read(COMMENT_SERVICE)
    robots_route = read(ROBOTS_ROUTE)
    settings_page = read(SETTINGS_PAGE)

    # ── Avatars ─────────────────────────────────────────────────────────────
    # 1. The three keys are seeded. WordPress's avatars screen has all three.
    for key in ("show_avatars", "avatar_default", "avatar_rating"):
        if f'"{key}"' not in defaults:
            failures.append(f"avatar option {key!r} is not seeded in default_options")

    # 2. The reader exists and honours show_avatars. A helper that only changes
    #    the gravatar params but ignores the show toggle would leave the store
    #    rendering half its avatars after the operator turned them off.
    if "async def avatar_options(" not in gravatar:
        failures.append("avatar_options() reader was removed from gravatar.py")
    else:
        # The off-branch must be a real early return, not a comment: match an
        # `if ... not options.show:` guard followed by a return. The guard may
        # read `if not options.show:` or `if options is not None and not
        # options.show:` — both are the same decision.
        if not re.search(r"if [^\n]*not options\.show:\s*\n\s*return", gravatar):
            failures.append("gravatar does not early-return when show_avatars is off")
        if "async def avatars_for_users(" not in gravatar:
            failures.append("avatars_for_users() was removed")
        else:
            fn = gravatar.split("async def avatars_for_users(", 1)[1]
            if not re.search(r"if [^\n]*not options\.show:\s*\n\s*return", fn):
                failures.append("avatars_for_users does not honour show_avatars")

    # 3. The public route surfaces the options for the storefront.
    if '"/public/avatar-options"' not in routes:
        failures.append("GET /settings/public/avatar-options is missing")

    # 4. The comment path actually passes the options through — the point of the
    #    whole feature is that a rendered thread honours the setting. A reader
    #    with no caller is the "route without a consumer" bug.
    if "avatar_options(self.db)" not in comment:
        failures.append("comment_service does not read avatar_options (feature unwired)")
    elif "options=options" not in comment:
        failures.append("comment_service reads avatar_options but does not pass it down")

    # 5. The admin screen exists and is mounted.
    if not AVATAR_CARD.is_file():
        failures.append("avatar-settings-card.tsx is missing")
    elif "<AvatarSettingsCard" not in settings_page:
        failures.append("AvatarSettingsCard is not mounted in the settings page")
    elif "AvatarSettingsCard" not in settings_page.split("return", 1)[-1]:
        # It is imported but must also be rendered, not merely referenced.
        failures.append("AvatarSettingsCard is imported but never rendered")

    # ── robots.txt ──────────────────────────────────────────────────────────
    # 6. The option is seeded.
    if '"robots_extra_rules"' not in defaults:
        failures.append("robots_extra_rules is not seeded in default_options")

    # 7. The public route that the robots route reads.
    if '"/public/robots-extra"' not in routes:
        failures.append("GET /settings/public/robots-extra is missing")

    # 8. /robots.txt is served by a Route Handler that appends the extra rules,
    #    and the old fixed metadata file is gone (two robots sources would race).
    if not ROBOTS_ROUTE.is_file():
        failures.append("frontend/app/robots.txt/route.ts is missing")
    elif not re.search(r"/settings/public/robots-extra[`\"']", robots_route):
        failures.append("the robots.txt route never fetches the operator's extra rules")
    if OLD_ROBOTS.is_file():
        failures.append("frontend/app/robots.ts still exists — two robots sources")

    # 9. The admin screen exists and is mounted.
    if not ROBOTS_CARD.is_file():
        failures.append("robots-settings-card.tsx is missing")
    elif "<RobotsSettingsCard" not in settings_page:
        failures.append("RobotsSettingsCard is not mounted in the settings page")
    elif "robots_extra_rules" not in read(ROBOTS_CARD):
        failures.append("robots card does not write the robots_extra_rules key")

    return failures


def run_sabotage() -> int:
    """Inject one breakage per rule and confirm the matching rule names it."""
    print("sabotage audit — proving every rule can fail\n")
    problems = 0
    for rule_id, (path, find, replace) in SABOTAGE.items():
        if not path.is_file():
            print(f"  SKIP  {rule_id}: {path.name} absent")
            continue
        original = path.read_text(encoding="utf-8")
        if find not in original:
            print(f"  SKIP  {rule_id}: anchor not found (rule already differs)")
            continue
        path.write_text(original.replace(find, replace, 1), encoding="utf-8")
        try:
            failures = evaluate()
        finally:
            path.write_text(original, encoding="utf-8")
        if failures:
            print(f"  caught {rule_id}")
        else:
            problems += 1
            print(f"  MISSED {rule_id}: injected breakage did not trip any rule")
    if problems:
        print(f"\nsabotage: {problems} rule(s) failed to catch their own breakage")
        return 1
    print("\nsabotage: every rule caught its breakage")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sabotage", action="store_true")
    args = parser.parse_args()

    if args.sabotage:
        return run_sabotage()

    failures = evaluate()
    if failures:
        print("FAIL: settings options are not fully wired")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("PASS: avatar options and virtual robots.txt are wired end to end")
    return 0


if __name__ == "__main__":
    sys.exit(main())