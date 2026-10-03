"""The awaiting-mod count must be on screen, not just in the API.

An endpoint with no consumer is not a feature — it is a route that answers. The
count endpoint can be correct, tested, and guarded, and a moderator still never
learns that a comment is waiting, which is the whole problem it was built for.

So this checks the consumer exists: the client function, the hook that polls
it, and the badge in the bar. Plus the three things that make the badge wrong
in a way no backend test would catch:

  * it must not appear when the count is unknown or zero — an "unknown" badge
    reading 0 tells a moderator the queue is empty when nobody has checked;
  * it must not render for someone who cannot moderate, or it becomes a 403 on
    every poll for every other admin;
  * the badge must not read the moderation list's total, because that list
    paginates and includes notes — both verified in the fixture, and worth
    pinning here so the shortcut is not reintroduced.

Run:  python scripts/wp-parity/check_pending_badge_wired.py
"""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

CLIENT = os.path.join(ROOT, "frontend", "lib", "api", "blog.ts")
HOOK = os.path.join(ROOT, "frontend", "hooks", "use-pending-comment-count.ts")
BAR = os.path.join(ROOT, "frontend", "components", "layout", "admin-bar.tsx")

failures: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {label}: {ok}")
    if not ok:
        failures.append(f"{label}: {detail}" if detail else label)


def read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def main() -> int:
    for path in (CLIENT, HOOK, BAR):
        if not os.path.isfile(path):
            print(f"FAIL: missing {path}")
            return 1
    client, hook, bar = (read(p) for p in (CLIENT, HOOK, BAR))

    # 1. the client function the badge reads through
    check("the client exposes the count", "pendingCommentCount" in client)
    check("it points at the dedicated endpoint",
          "/admin/blog/comments/pending-count" in client)

    # 2. the hook polls it, and swallows failures — a badge that throws takes
    #    the admin chrome down with it
    check("the hook polls the count", "pendingCommentCount()" in hook)
    check("the hook does not throw on failure", "catch" in hook)
    check("it skips the request when the tab is hidden", "document.hidden" in hook)

    # 3. permission gate, so an admin who cannot moderate does not poll a 403
    check("the hook checks a permission before asking",
          "blog:moderate_comments" in hook)
    check("a superuser is included — their permissions list is empty",
          "is_superuser" in hook)

    # 4. the badge itself
    check("the admin bar uses the hook", "usePendingCommentCount" in bar)
    check("the bar renders the count", "pendingCommentCount > 0" in bar)

    # 5. not shown when unknown. `null` is the loaded-but-not-yet-answered
    #    state; rendering it as 0 claims the queue is empty, which is the
    #    failure the badge exists to prevent.
    check("the badge is hidden while the count is unknown",
          "pendingCommentCount !== null" in bar)

    # 6. and it must not be derived from the paginated list's total
    check("the badge does not reuse the moderation list total",
          "pendingCommentCount" not in hook.replace("pendingCommentCount()", "")
          or ".total" not in hook,
          "the count is read from a list total, which paginates")

    if failures:
        print("\nFAIL:")
        for f in failures:
            print(f"  {f}")
        return 1
    print("\nPASS: the awaiting-mod count reaches a badge that only shows a "
          "number somebody actually measured.")
    return 0


if __name__ == "__main__":
    sys.exit(main())