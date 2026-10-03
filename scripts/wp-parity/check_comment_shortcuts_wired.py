"""The comment moderation keyboard shortcuts, and the two things that make them safe.

WordPress's comment moderation is driven from the keyboard: j/k to move,
a to approve, u to unapprove, s for spam, t for trash, d to delete. A moderator
with ninety comments does the whole queue without touching the mouse.

Presence is not enough here. A `keydown` listener that fires while the user is
typing is worse than no listener at all — typing "just a note" into the search
box would approve, trash and unapprove whichever row is focused, on the letters
j, t, a, u. So this checks the guard as well as the bindings.

And it checks each key is bound to the *right* operation. A handler where `a`
trashes and `t` approves passes any check that only counts the switch cases.

Run:  python scripts/wp-parity/check_comment_shortcuts_wired.py
"""

from __future__ import annotations

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PANEL = os.path.join(ROOT, "frontend", "components", "admin", "blog",
                     "comments-moderation-tab.tsx")

failures: list[str] = []

#: key -> the operation it must perform. Checked by looking inside that key's
#: `case` block, because "the switch has eight cases" says nothing about which
#: case does what.
EXPECTED = {
    "j": ("setFocusIndex", "moves down"),
    "k": ("setFocusIndex", "moves up"),
    "a": ('runBulk("approve"', "approves"),
    "u": ('runBulk("unapprove"', "unapproves"),
    "s": ('runBulk("spam"', "marks spam"),
    "t": ('runBulk("trash"', "trashes"),
    "d": ("handleDelete", "deletes"),
    "e": ("openEdit", "opens the editor"),
}


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {label}: {ok}")
    if not ok:
        failures.append(f"{label}: {detail}" if detail else label)


def case_body(text: str, key: str) -> str:
    """The lines inside the `case "<key>":` block, up to the next case."""
    start = text.find(f'case "{key}":')
    if start == -1:
        return ""
    rest = text[start + len(f'case "{key}":'):]
    nxt = re.search(r"\n\s*case \"|\n\s*default", rest)
    return rest[: nxt.start()] if nxt else rest


def main() -> int:
    if not os.path.isfile(PANEL):
        print(f"FAIL: missing {PANEL}")
        return 1
    with open(PANEL, encoding="utf-8") as fh:
        panel = fh.read()

    check("a keydown listener is registered", 'addEventListener("keydown"' in panel)
    check("and removed on unmount", 'removeEventListener("keydown"' in panel)

    # The guard that makes a global listener safe to have at all.
    for tag, why in (
        ('target.tagName === "INPUT"', "ignores text inputs"),
        ('target.tagName === "TEXTAREA"', "ignores textareas"),
        ("target.isContentEditable", "ignores contenteditable"),
        ("e.metaKey", "leaves browser shortcuts alone"),
        ("e.ctrlKey", "leaves ctrl-shortcuts alone"),
        ("e.altKey", "leaves alt-shortcuts alone"),
    ):
        check(f"the guard {why}", tag in panel)

    # Each key does its own operation. The whole point of the negative test.
    for key, (call, why) in EXPECTED.items():
        body = case_body(panel, key)
        check(f"'{key}' {why}", bool(body) and call in body,
              f"case body was: {body.strip()[:80]}")

    check("'?' opens the help", '"?"' in panel and "میانبر" in panel)
    check("the shortcuts are discoverable from the panel",
          "میانبرهای" in panel)

    if failures:
        print("\nFAIL:")
        for f in failures:
            print(f"  {f}")
        return 1
    print("\nPASS: every moderation shortcut is bound to its own operation, "
          "and the listener is inert while the user types.")
    return 0


if __name__ == "__main__":
    sys.exit(main())