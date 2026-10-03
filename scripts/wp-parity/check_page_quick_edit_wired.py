"""Quick edit for CMS pages must be wired, and must actually send the fields.

Two separate failures, and the first is invisible without the second:

  * **not wired.** The dialog exists and imports cleanly while no page list
    renders it. `QuickEditPageDialog` on disk with no caller is a component
    nobody opens, and every check below would pass.
  * **wired but inert.** The dialog opens and saves — and sends nothing, so a
    moderator corrects a title and the row behind the dialog is unchanged. This
    is worse than a missing button, because it reports success.

So this reads the four layers for reachability, then the dialog's body for what
it actually puts in the request. A `title` field that exists but is not in the
payload is the case a "does the component exist" check passes.

Run:  python scripts/wp-parity/check_page_quick_edit_wired.py
"""

from __future__ import annotations

import os as _os
_sys_path_insert = _os.path.dirname(__file__)
import sys as _sys
_sys.path.insert(0, _sys_path_insert)
import console_safe  # noqa: F401  — makes stdout safe for non-ASCII

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PAGE = os.path.join(ROOT, "frontend", "app", "admin", "pages", "page.tsx")
DIALOG = os.path.join(ROOT, "frontend", "components", "admin", "pages",
                      "quick-edit-page-dialog.tsx")

failures: list[str] = []

#: (field, the label a moderator would look for). Each has to reach the API
#: payload — a field rendered but not sent is the inert-dialog failure.
MUST_REACH_API = [
    "title",
    "slug",
    "status",
    "visibility",
    "allow_comments",
    "scheduled_publish_at",
]


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {label}: {ok}")
    if not ok:
        failures.append(f"{label}: {detail}" if detail else label)


def read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def main() -> int:
    for path in (PAGE, DIALOG):
        if not os.path.isfile(path):
            print(f"FAIL: missing {path}")
            return 1
    page, dialog = read(PAGE), read(DIALOG)

    # 1. the component exists and is a component, not a stub
    check("the dialog file exists", bool(dialog))
    check("it exports the dialog",
          "export function QuickEditPageDialog" in dialog)

    # 2. the page list reaches it. Each of these separately: an import with no
    #    render, or state with no trigger, both leave an unreachable dialog.
    check("the pages page imports it", "QuickEditPageDialog" in page)
    check("it holds the target row", "quickEditPage" in page)
    check("it holds the open flag", "quickEditOpen" in page)
    check("it renders the dialog in JSX",
          "<QuickEditPageDialog" in page)
    check("something opens it", "setQuickEditOpen(true)" in page)
    check("and the row list offers a control",
          "setQuickEditPage(page)" in page,
          "no control sets which page is being quick-edited")

    # 3. the dialog sends the fields. Read from the payload literal, so a field
    #    rendered in the form but dropped before the request is caught.
    payload_at = dialog.find("updatePage(")
    check("it calls the update endpoint", payload_at != -1)
    body = dialog[payload_at:payload_at + 1200] if payload_at != -1 else ""
    for field in MUST_REACH_API:
        check(f"'{field}' reaches the request", field in body,
              "present in the form but not in the payload")

    # 4. the save reports honestly and does not claim success on failure
    check("a failed save surfaces a toast", "variant: \"destructive\"" in dialog)
    check("a successful save closes and refreshes",
          "onSaved()" in dialog and "onOpenChange(false)" in dialog)

    if failures:
        print("\nFAIL:")
        for f in failures:
            print(f"  {f}")
        return 1
    print("\nPASS: quick edit for pages is reachable from the list and sends "
          "the fields it shows.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
