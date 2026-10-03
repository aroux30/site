"""Negative test: the privacy-policy check can actually fail.

A verification script that only ever prints PASS is a gate that cannot fail, and
a gate that cannot fail is not a gate. This breaks each property the check
depends on, one at a time, and requires the check to go red for the stated
reason.

The two failures worth the trouble are the ones that are invisible from the
outside: a *published but private* page, and a route registered after the
`/{key}` catch-all. Both produce the same symptom a store with no policy
produces — no link on the consent form — so a check that only staged "nothing
configured" would pass on both.

    cd backend && PYTHONPATH=. python scripts/negative_test_privacy_policy.py
"""

from __future__ import annotations

import io
import os
import subprocess
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BACKEND = Path(__file__).resolve().parents[1]
CHECK = BACKEND / "scripts" / "verify_privacy_policy.py"
SERVICE = (
    BACKEND / "app" / "modules" / "settings" / "application" / "privacy_policy_service.py"
)
ROUTES = BACKEND / "app" / "modules" / "settings" / "api" / "routes.py"

#: The privacy route, decorator through body. Needed whole because swapping only
#: the decorator would leave the handler where it is — a different defect, where
#: the endpoint serves the wrong function rather than being matched too late.
PRIVACY_ROUTE = '''@router.get(
    "/public/privacy-policy",
    response_model=PrivacyPolicyResponse,
    summary="The published privacy policy page",
)
async def get_privacy_policy(
    db: AsyncSession = Depends(get_db),
) -> PrivacyPolicyResponse:
    """Return the privacy policy page, or empty fields when none is published.

    Public and unauthenticated on purpose: this is called from the registration,
    comment and checkout forms, before anyone has an account. It carries no
    personal data — a title and a URL — so there is nothing to protect here.

    Declared above ``/{key}`` deliberately. FastAPI matches in declaration order,
    so a route registered after it would be captured as a setting named
    "privacy-policy" and return 404 for every caller, which reads as "this store
    has no privacy policy" on a store that has one.
    """
    policy = await PrivacyPolicyService.get_policy(db)
    if policy is None:
        return PrivacyPolicyResponse()
    return PrivacyPolicyResponse(**policy)


'''

#: The catch-all itself, decorator through body. This is the block the privacy
#: route has to land *after* — swapping it with the privacy block is what
#: reproduces the defect. Swapping with the admin listing route instead does
#: nothing: that route already sits above the catch-all, so both orders put the
#: privacy endpoint before it. Which is what a first attempt at this case did,
#: and why it reported the guard green on a file it had not actually broken.
CATCH_ALL_ROUTE = '''@router.get(
    "/{key}",
    response_model=SettingResponse,
    summary="Get setting by key (admin)",
    dependencies=[Depends(RequirePermissions("settings:read"))],
)
async def get_setting(
    key: str,
    db: AsyncSession = Depends(get_db),
) -> SettingResponse:
    """Get a single setting."""
    setting = await SettingsService.get_by_key(db, key)
    return SettingResponse.model_validate(setting)


'''

# (name, file, original, broken, expected substring in the check's output)
CASES: list[tuple[str, Path, str, str, str]] = [
    (
        "a draft page is accepted as the policy",
        SERVICE,
        "        if page.status != PageStatus.PUBLISHED:",
        "        if False:",
        "a draft page resolves as the privacy policy",
    ),
    (
        "only the draft is rejected, so a private page is linkable",
        SERVICE,
        "        if page.visibility != PageVisibility.PUBLIC:",
        "        if False:",
        "a published-but-private page resolves as the privacy policy",
    ),
    (
        "the configured slug is ignored, so nothing ever resolves",
        SERVICE,
        "            await SiteOptionsService.get(db, PRIVACY_POLICY_OPTION, \"\") or \"\"",
        "            \"\" or \"\"",
        "does not resolve",
    ),
    (
        # A duplicate registration is the realistic way the order changes without
# anyone moving a block: FastAPI matches the *first* registered path for a
# given rule, so declaring the privacy route twice — once correctly above the
# catch-all and once below it — leaves the storefront working and the endpoint
# permanently unreachable from any caller that has not already matched. The
# check reads the app's route table, so the duplicate shows up as the route
# appearing after the catch-all.
        "the route is registered after the /{key} catch-all",
        ROUTES,
        CATCH_ALL_ROUTE,
        CATCH_ALL_ROUTE + PRIVACY_ROUTE,
        "is declared after /{key}",
    ),
]


def run_check() -> tuple[int, str]:
    # The child inherits this process's whole environment and only adds
    # PYTHONPATH: a hand-built env drops SystemRoot, and the Windows socket layer
    # then fails to load at import time -- which looks like a broken check rather
    # than a broken environment.
    proc = subprocess.run(
        [sys.executable, str(CHECK)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=BACKEND,
        env={**os.environ, "PYTHONPATH": "."},
    )
    return proc.returncode, proc.stdout + proc.stderr


def main() -> int:
    saved: dict[Path, str] = {}
    try:
        return _run(saved)
    finally:
        # The outermost restore, and the reason this function is split in two.
        # The per-case `finally` covers an exception raised by the *check*, but a
        # failure before the loop starts -- the baseline run going red, an
        # interrupt, a missing marker -- returns without ever entering it, and
        # left an injected defect on disk. That is how a broken test suite becomes
        # a broken tree: the next run then fails for a reason that has nothing to
        # do with the code it is testing.
        for path, original in saved.items():
            if path.read_text(encoding="utf-8") != original:
                path.write_text(original, encoding="utf-8")
                print("restored %s" % path.name)


def _run(saved: dict[Path, str]) -> int:
    failures: list[str] = []
    missing: list[str] = []

    # The block constants have to match the source byte for byte, or the case
    # silently becomes a no-op and the guard "passes" on a file it never broke.
    # Checked up front rather than discovered as four confusing failures.
    routes_source = ROUTES.read_text(encoding="utf-8")
    for label, block in (("privacy", PRIVACY_ROUTE), ("catch-all", CATCH_ALL_ROUTE)):
        if block not in routes_source:
            missing.append(
                "the %s route block in this file does not match routes.py, so the "
                "ordering case would not inject anything -- update it for the "
                "current source" % label
            )
    if missing:
        for m in missing:
            print("FAIL: %s" % m)
        return 1

    print("baseline (unbroken tree):")
    code, out = run_check()
    if code != 0:
        print(out)
        print(
            "FAIL: the check does not pass on the unbroken tree, so a red run below "
            "would mean nothing"
        )
        return 1
    print("  PASS as expected")
    print("")

    for name, path, original, broken, expected in CASES:
        source = path.read_text(encoding="utf-8")
        if original not in source:
            failures.append(
                "%s: the marker to break is not in %s, so this case would prove "
                "nothing -- update it for the current source" % (name, path.name)
            )
            continue
        path.write_text(source.replace(original, broken, 1), encoding="utf-8")
        try:
            code, out = run_check()
        finally:
            path.write_text(source, encoding="utf-8")

        if code == 0:
            failures.append("%s: the check still passed" % name)
            print("  FAIL %s -- the check still passed" % name)
        elif expected not in out:
            failures.append(
                "%s: the check went red, but not for this reason -- expected %r in "
                "the output" % (name, expected)
            )
            print("  FAIL %s -- red for the wrong reason" % name)
            print("    " + out.strip().replace("\n", "\n    "))
        else:
            print("  PASS %s -> check went red for the right reason" % name)

    code, out = run_check()
    if code != 0:
        print(out)
        failures.append("the check is red again after restoring every file")
    else:
        print("")
        print("PASS: the tree is green again after every injection was reverted.")

    if failures:
        print("")
        for f in failures:
            print("FAIL: %s" % f)
        return 1
    print("")
    print("PASS: every defect this check targets makes it go red, for its own reason.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
