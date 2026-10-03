"""Negative test for the comment notification options.

Three sabotages, each aimed at one of the three ways this code went wrong while
looking finished:

  A. Restore the `status == APPROVED` gate around the notify call. This is the
     bug this fixture was written against: the gate made the moderation path
     unreachable, so `moderation_notify` was a switch that could not fire and a
     held comment went silently unnoticed. The fixture must go red.
  B. Delete the age comparison, leaving `close_comments_days_old` readable but
     never applied — the switch that looks implemented because the option
     parses and the default is 0.
  C. Keep the age check on posts only, dropping pages. Nothing notices until
     the oldest thread on the site is on a page.

Run:  python scripts/wp-parity/negative_test_comment_options.py
"""

from __future__ import annotations

import sys as _sys
_sys.path.insert(0, __import__("os").path.dirname(__file__))
import console_safe  # noqa: F401  — makes stdout safe for non-ASCII

import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
FIXTURE = os.path.join(ROOT, ".p1-tests", "comment_options_test.py")
SERVICE = os.path.join(
    ROOT, "backend", "app", "modules", "blog", "application", "comment_service.py"
)

FIXED_NOTIFY_GATE = """        # WordPress fires wp_notify_postauthor for every new comment, approved
        # or held: the two options decide *who* hears about it, not whether the
        # notification happens. Gating on APPROVED here deleted the whole
        # moderation branch — with it, `moderation_notify` was a switch that
        # could not fire, and a comment from a user the system holds went
        # silently unnoticed.
        if resource_type == COMMENT_RESOURCE_BLOG_POST:"""

# The bug, verbatim. Same shape as the original: it reads as a deliberate
# privacy guard, and it silently disables half the feature.
SABOTAGE_NOTIFY_GATE = (
    "        if status == CommentStatus.APPROVED "
    "and resource_type == COMMENT_RESOURCE_BLOG_POST:"
)

FIXED_AGE = "if age_days >= days:"

FIXED_PAGE_GUARD = "            await self._ensure_page_accepts_comments(resource_id)"

# Covering posts but not pages. The oldest conversation on a store is almost
# always on a landing page, so this hole is invisible until someone tries to
# comment on one.
SABOTAGE_PAGE_GUARD = "            pass  # sabotage: pages no longer age-checked"

SABOTAGES = [
    (
        "A: gate the notify call on APPROVED (the real bug)",
        [(FIXED_NOTIFY_GATE, SABOTAGE_NOTIFY_GATE)],
    ),
    (
        "B: read close_comments_days_old but never compare it",
        [(FIXED_AGE, "if False:")],
    ),
    (
        "C: age-check posts but not pages",
        [(FIXED_PAGE_GUARD, SABOTAGE_PAGE_GUARD)],
    ),
]


def run_fixture() -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, FIXTURE],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=600,
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def apply(pairs: list[tuple[str, str]]) -> str | None:
    """Patch the service, refusing to run a sabotage that did not land.

    A negative test whose sabotage silently failed to apply proves nothing: the
    fixture would go red for its own reasons and the green check would still
    pass. So the substitution is verified, not assumed.

    Each anchor is replaced at *every* occurrence — an anchor that appears once
    would let a shared line slip past unexamined, which is exactly what the age
    comparison is: the same statement in two places, and breaking only one of
    them still reads as caught.
    """
    with open(SERVICE, encoding="utf-8") as fh:
        original = fh.read()
    text = original
    for needle, replacement in pairs:
        if needle not in text:
            print(f"FAIL: the anchor for this sabotage was not found, so it was "
                  f"not applied: {needle.splitlines()[0]!r}")
            return None
        text = text.replace(needle, replacement)
    with open(SERVICE, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    return original


def main() -> int:
    if not os.path.isfile(FIXTURE):
        print(f"FAIL: fixture missing at {FIXTURE}")
        return 1

    rc, out = run_fixture()
    if rc != 0:
        print("FAIL: the fixture does not pass on the real code, so a failure "
              "below would prove nothing.")
        print(out.strip()[-900:])
        return 1
    print("fixture passes on the real code")

    for label, pairs in SABOTAGES:
        original = apply(pairs)
        if original is None:
            return 1
        try:
            rc_broken, out_broken = run_fixture()
        finally:
            with open(SERVICE, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(original)

        rc_after, out_after = run_fixture()
        if rc_after != 0:
            print(f"FAIL: {label} — the fixture did not pass again after "
                  f"restoring, so the sabotage was not cleaned up.")
            print(out_after.strip()[-900:])
            return 1

        if rc_broken == 0:
            print(f"FAIL: {label} still passed. The fixture cannot see this bug.")
            return 1

        # Report the assertion that caught it, so a reader can tell the gate is
        # measuring something real rather than crashing on an import error.
        caught = [
            line.strip()
            for line in out_broken.splitlines()
            if "GAPS" in line
        ]
        print(f"  {label} -> caught")
        for line in caught:
            print(f"      {line[:220]}")

    print("\nPASS: every sabotage was caught, and the fixture was green again "
          "after each restore, so it is a real gate.")
    return 0


if __name__ == "__main__":
    sys.exit(main())