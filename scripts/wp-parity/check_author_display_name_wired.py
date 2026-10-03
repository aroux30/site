"""The byline must read `display_name`, at every hop that carries it.

This was handed to me twice before being done, and the reason it kept coming
back is that all three hops can be present while the feature is still absent:

  * the row has the field, the query selects it, and the constructor never
    passes it — the shape that was actually in the tree. Every check that asks
    "does the column exist" says yes.
  * the formatter prefers it, and the archive still shows first+last, because
    the value never arrived.

So this checks the *chain* rather than the pieces: the field on the row, the
column in the query, the argument at the construction site, and the preference
in the formatter. Removing any one of them has to show up.

Run:  python scripts/wp-parity/check_author_display_name_wired.py
"""

from __future__ import annotations

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import console_safe  # noqa: F401  — makes stdout safe for non-ASCII

SERVICE = os.path.join(ROOT, "backend", "app", "modules", "blog",
                       "application", "author_service.py")
MODEL = os.path.join(ROOT, "backend", "app", "modules", "users",
                     "domain", "models.py")

failures: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {label}: {ok}")
    if not ok:
        failures.append(f"{label}: {detail}" if detail else label)


def main() -> int:
    with open(SERVICE, encoding="utf-8") as fh:
        service = fh.read()
    with open(MODEL, encoding="utf-8") as fh:
        model = fh.read()

    # 0. the column exists at all — without it there is nothing to read
    check("user_profiles has display_name", "display_name" in model)

    # 1. the row carries it. A field that is selected but has nowhere to live
    #    is the first way this goes missing.
    slots = re.search(r"__slots__\s*=\s*\(([^)]*)\)", service)
    check("the author row has the field",
          slots is not None and "display_name" in slots.group(1))

    # 2. the query reads it
    check("the author query selects it",
          "UserProfile.display_name" in service)

    # 3. the construction site passes it — the hop that was actually missing
    #    while every other check said the feature was there.
    construct = re.search(r"return _AuthorRow\((.*?)\n\s*\)", service, re.S)
    check("the author row is built with it",
          construct is not None and "display_name" in construct.group(1),
          "the field exists on the row and in the query, but the constructor "
          "never fills it — which is the state this gate was written for")

    # 4. the formatter prefers it over first+last
    #
    # Sliced to the next top-level `def`, not with a `\n(?=\S)` lookahead:
    # that stops at the first non-blank line *inside* the body, which cut the
    # slice before the fallbacks and made this gate report a formatter missing
    # fields it plainly had.
    m = re.search(r"\ndef _display_name\(", service)
    body = ""
    if m:
        rest = service[m.end():]
        nxt = re.search(r"\n(?:def |class )", rest)
        body = rest[:nxt.start()] if nxt else rest
    check("the byline prefers it", "display_name" in body)
    chosen_at = body.find("display_name")
    fallback_at = body.find("first_name")
    check("and prefers it before falling back",
          chosen_at != -1 and fallback_at != -1 and chosen_at < fallback_at,
          "the fallback is consulted before the chosen name")

    # 5. the fallbacks survive. Removing them would leave an empty byline for
    #    every author who never set one.
    check("the first+last fallback is kept",
          "first_name" in body and "last_name" in body)
    # The phone tail is *used*, not merely mentioned: a gate that only looks
    # for the word passes while the fallback has been removed and the word
    # survives in a comment — which is exactly how the first version of this
    # check behaved.
    check("the phone fallback is actually returned",
          re.search(r"return\s+.*\bphone\b", body) is not None,
          "the word appears but nothing returns it")

    if failures:
        print("\nFAIL:")
        for f in failures:
            print(f"  {f}")
        return 1
    print("\nPASS: the byline is the name the author chose, carried through "
          "every hop.")
    return 0


if __name__ == "__main__":
    sys.exit(main())