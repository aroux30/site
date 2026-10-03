"""No negative test may write a file another session owns.

A negative test proves its point by editing real source and restoring it. That
is safe when one session owns the tree and unsafe the moment a second session is
editing the same file: the restore and the other session's edit race, and the
loser is whichever wrote last. In this project that has left half-written
`media_service.py` and `routes.py` on disk three times, each time with the app
failing to boot.

So the ownership map lives here, and this gate fails when a negative test
targets a file in another session's window. Deliberate exceptions are listed with
the reason, so widening one is a visible edit rather than a quiet omission.

The check is on the *destination* a test writes to, not on what it reads — a
test may read anything, and most do, because a gate is useless if it cannot
compare against the real code.

Run:  python scripts/wp-parity/check_no_cross_session_sabotage.py
"""

from __future__ import annotations

import os as _os
_sys_path_insert = _os.path.dirname(__file__)
import sys as _sys
_sys.path.insert(0, _sys_path_insert)
import console_safe  # noqa: F401  — makes stdout safe for non-ASCII

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PARITY = os.path.join(ROOT, "scripts", "wp-parity")

#: Module directory -> the session that owns it. Matched as a *path segment*
#: rather than a substring of the joined string: a path is written as
#: `os.path.join(ROOT, "backend", "app", "modules", "media", ...)`, so the text
#: "/modules/media/" never appears in the source at all. Matching the string
#: form is why this check was silent about every wrapped path.
OWNED_BY_OTHER = {
    "media": "p1-help",
    "users": "p1-help",
    "auth": "p1-help",
    "settings": "p1-help",
    "widgets": "p1-help",
}

#: Frontend and shared paths, still matched as substrings because they are
#: written whole.
OWNED_BY_OTHER_PATHS = {
    "frontend/app/admin/media/": "p1-help",
    "frontend/app/admin/users/": "p1-help",
    "frontend/app/admin/settings/": "p1-help",
    "frontend/app/admin/widgets/": "p1-help",
    "shared/content/widgets.py": "p1-help",
    "frontend/lib/api/media.ts": "p1-help",
    "frontend/components/admin/media/": "p1-help",
}

#: `(test file, reason)` — the few tests allowed to touch a file above. There
#: are none right now, and that is the point: the list is where a deliberate
#: exception would go, and it being empty is easier to notice than it being
#: absent.
EXCEPTIONS: dict[str, str] = {
    # This gate's own negative test embeds the offending path as *data* — a
    # template it writes to a scratch file — so the gate sees its own example
    # and flags it. The exception is the reason it is allowed, not a blanket
    # pass: nothing here is patched in place.
    "negative_test_no_cross_session_sabotage.py": (
        "embeds example paths as data; writes only to a temp file it deletes"
    ),
}

#: A test that writes to a source file names its target in an assignment to one
#: of these. Read-only references (`FIXTURE`, `GATE`, `CLIENT`, `PANEL`) are not
#: in the list, which is why they are spelled out rather than guessed at.
WRITE_TARGET_VARS = ("SERVICE", "ROUTES", "SCHEMA", "ROUTE", "SOURCE")


def failures_for_tests() -> list[str]:
    problems: list[str] = []
    tests = [
        f for f in os.listdir(PARITY)
        if f.startswith("negative_test_") and f.endswith(".py")
    ]
    for name in sorted(tests):
        if name in EXCEPTIONS:
            continue
        path = os.path.join(PARITY, name)
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        for var in WRITE_TARGET_VARS:
            # The assignment can wrap across lines — `os.path.join(ROOT, "a",
            # "b")` over two lines is how this file writes them and how a real
            # test would too — so the statement is read to its closing paren,
            # not just to the end of the line. Matching one line missed every
            # wrapped path, which is most of them.
            for match in re.finditer(
                rf"^{var}\s*=\s*(.*?)\)\s*$", text, re.M | re.S
            ):
                stmt = match.group(0)
                # Only paths joined from ROOT name a source file to write; a
                # path under scripts/ is the gate itself, never a source.
                if "ROOT" not in stmt or '"scripts"' in stmt:
                    continue
                # Segment match for the module directories, so
                # `"app", "modules", "media"` is recognised as media.
                segments = set(re.findall(r'"([A-Za-z0-9_.-]+)"', stmt))
                owned = sorted(segments & set(OWNED_BY_OTHER))
                if owned:
                    problems.append(
                        f"{name} writes to {var} in {owned[0]}/ — owned by "
                        f"{OWNED_BY_OTHER[owned[0]]}"
                    )
                    continue
                flat = stmt.replace('", "', "/").replace('"', "")
                for fragment, owner in OWNED_BY_OTHER_PATHS.items():
                    if fragment in flat:
                        problems.append(
                            f"{name} writes to {var} in {fragment} — owned by {owner}"
                        )
    return problems


def main() -> int:
    if not os.path.isdir(PARITY):
        print(f"FAIL: {PARITY} is missing")
        return 1

    tests = [
        f for f in os.listdir(PARITY)
        if f.startswith("negative_test_") and f.endswith(".py")
    ]
    print(f"  negative tests checked: {len(tests)}")
    print(f"  deliberate exceptions: {len(EXCEPTIONS)}")

    problems = failures_for_tests()
    for p in problems:
        print(f"  FAIL {p}")

    if problems:
        print("\nFAIL: a negative test writes to another session's file.")
        print("Move it out of the way while that session is editing — a sabotage")
        print("and someone's edit race, and the loser is whichever wrote last.")
        return 1
    print("\nPASS: no negative test writes to a file another session owns.")
    return 0


if __name__ == "__main__":
    sys.exit(main())