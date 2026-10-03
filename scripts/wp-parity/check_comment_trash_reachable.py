"""The comment trash must stay reachable from the panel, not just in the API.

A filter was once removed from the moderation table with the comment "nothing
in the codebase ever writes CommentStatus.TRASH" — while the bulk trash button
in that same panel writes it through the same endpoint. The result was a working
trash with no way to see it, which is the shape of bug a route-level test
cannot catch: every endpoint behaved, and the feature was still unusable.

So this reads the component source. Cheap, and it fails on exactly the class of
regression that happened: a state the backend can produce and the UI cannot
reach.

Run:  python scripts/wp-parity/check_comment_trash_reachable.py
"""

from __future__ import annotations

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PANEL = os.path.join(
    ROOT, "frontend", "components", "admin", "blog", "comments-moderation-tab.tsx"
)
CLIENT = os.path.join(ROOT, "frontend", "lib", "api", "blog.ts")

failures: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {label}: {ok}")
    if not ok:
        failures.append(f"{label}: {detail}" if detail else label)


def main() -> int:
    for path in (PANEL, CLIENT):
        if not os.path.isfile(path):
            print(f"FAIL: missing {path}")
            return 1
    with open(PANEL, encoding="utf-8") as fh:
        panel = fh.read()
    with open(CLIENT, encoding="utf-8") as fh:
        client = fh.read()

    # 1. the trash filter exists. The regression being guarded against is its
    #    absence, so this asserts the option is there rather than counting.
    #    Anchored after the spam option, not by counting: a second
    #    `<option value="trash">` lives in the per-row edit dialog, and a count
    #    would pass with the filter gone and the dialog's option still present.
    spam = '<option value="spam">اسپم / جفنگ</option>'
    i = panel.find(spam)
    # The window has to span the explanatory comment that sits between the two
    # options, so it is sized generously rather than to the current distance —
    # a tight window would fail the moment someone reflowed that comment.
    check("the status filter offers the trash",
          i != -1 and '<option value="trash">' in panel[i:i + 1200],
          "the trash option is not in the status filter "
          "(it may be present in the edit dialog only)")

    # 2. restore is offered as a bulk action. Trash without a way back is the
    #    one-way door; the button and the filter together are what close it.
    check("a bulk restore action exists", 'id: "restore"' in panel)
    check("and it calls the restore endpoint",
          re.search(r'runBulk\("restore"', panel) is not None)

    # 3. the local action union must admit it, or TypeScript would have blocked
    #    the call — checked here because a loosened union is how a new action
    #    sneaks in without the client supporting it.
    union = re.search(
        r'action:\s*((?:"[a-z]+"\s*\|\s*)*"[a-z]+")\s*,', panel)
    check("the local action type includes restore",
          union is not None and "restore" in union.group(1),
          union.group(1) if union else "no union found")

    # 4. the client sends it.
    client_actions = re.search(
        r'bulkComments:.*?action:\s*((?:"[a-z]+"\s*\|\s*)*"[a-z]+")', client, re.S)
    check("the client accepts restore",
          client_actions is not None and "restore" in client_actions.group(1),
          client_actions.group(1) if client_actions else "no client union found")

    # 5. the stale claim must not come back. Its presence is what produced the
    #    original bug, so it is worth failing on explicitly — but only the old
    #    wording. The replacement comment explains why the option is back, and
    #    a blanket "ever writes" ban would forbid that.
    check("the old justification for removing the filter is gone",
          "nothing in the codebase ever writes" not in panel.lower()
          and "this filter could only ever return an" not in panel.lower(),
          "the comment claiming TRASH is never written is back")

    if failures:
        print("\nFAIL:")
        for f in failures:
            print(f"  {f}")
        return 1
    print("\nPASS: the comment trash is filterable and reversible from the panel.")
    return 0


if __name__ == "__main__":
    sys.exit(main())