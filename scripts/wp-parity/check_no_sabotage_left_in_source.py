"""No sabotage marker may survive in production source.

Three times in one session a negative test left its edit behind, and each time
the tree stayed broken rather than failing:

  * `media_service.py` with `return 2560  # sabotage` — the app would not boot;
  * `comment_moderation_token.py` with `if False:  # sabotage: comment binding
    removed` — every comment verified against a disabled check;
  * `comment_service.py` with `pass  # sabotaged: 0 no longer disables` — **no
    comment could be posted at all**, and the message said "more than 0".

The last one is the reason this gate exists rather than a habit. A negative
test's restore is a `finally` block, and a `finally` that does not run, or that
raises before the restore, leaves the tree in a state that imports cleanly and
fails at runtime, in a way nobody is looking for.

So the markers are searched for directly. A comment that *describes* a
sabotage is fine — the tests themselves are full of them, and so are the gates
that check for them. What must not exist is one inside the tree the app runs.

Run:  python scripts/wp-parity/check_no_sabotage_left_in_source.py
"""

from __future__ import annotations

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BACKEND = os.path.join(ROOT, "backend", "app")
FRONTEND_SRC = os.path.join(ROOT, "frontend", "app")

#: The marker, and what it looks like when it is a *survivor* rather than a
#: description. A line whose whole content is the marker — a bare `pass`, an
#: `if False:` — is the dangerous shape; a `# see negative_test_x` above real
#: code is documentation.
#: Both comment syntaxes: `#` in Python and `//` in TypeScript. A gate that
#: only knows the first misses every frontend survivor, which is half the tree.
MARKERS = re.compile(r"[#/]{1,2}\s*(sabotage|sabotaged)\b", re.IGNORECASE)

#: Directories with no application source.
SKIP_DIRS = {"__pycache__", ".venv", "venv", "node_modules", ".next", "out",
             "alembic", "tests"}

failures: list[str] = []


def walk(*bases: str):
    for base in bases:
        for root, dirs, files in os.walk(base):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for name in files:
                if name.endswith((".py", ".ts", ".tsx")):
                    yield os.path.join(root, name)


def _code_before_comment(line: str) -> str:
    """The statement on a line, with any trailing comment removed.

    Split on the marker rather than pattern-matching the line: a regex for
    `pass # sabotage` misses `pass  # sabotage`, and the space between the two
    is the whole gate.
    """
    return line.split("#", 1)[0].split("//", 1)[0].strip().rstrip("{").rstrip(":").strip()


def _is_inert(code: str) -> bool:
    """Whether a statement does nothing — a bare no-op or a pinned guard.

    The shapes a leftover takes: `pass`, `return x`, an assignment of a
    literal, or a guard whose condition is a constant. Anything else that
    mentions a sabotage is documentation describing the test that performs it,
    and there is a lot of that in this tree.
    """
    if not code:
        return False
    if code in {"pass", "return", "raise", "continue", "break"}:
        return True
    # `if False:` (Python) and `if (false) {` (TypeScript) are the two ways a
    # neutered guard looks in the two languages this tree is written in.
    if re.fullmatch(
        r"(if|while)\s*[\(]?\s*(False|True|0|1|false|true)\s*[\)]?", code
    ):
        return True
    return bool(re.fullmatch(r"(return|const|let|var|raise)\s+.*;?", code))


def main() -> int:
    paths = sorted(walk(BACKEND, FRONTEND_SRC))
    print(f"  source files scanned: {len(paths)}")

    for path in paths:
        rel = os.path.relpath(path, ROOT)
        with open(path, encoding="utf-8", errors="replace") as fh:
            # Read whole: a neutralised guard and its marker are often on
            # different lines — `if (false) {` on one, `// sabotage` on the
            # next. Judging each line alone reads that marker as a bare comment
            # and lets the guard through.
            lines = fh.read().splitlines()

        for idx, line in enumerate(lines):
            if not MARKERS.search(line):
                continue
            code = _code_before_comment(line)
            if not code and idx > 0:
                # The marker is on its own line; the statement it describes is
                # the line above.
                code = _code_before_comment(lines[idx - 1])
            if not _is_inert(code):
                continue
            msg = f"{rel}:{idx + 1}  {line.strip()[:80]}"
            print(f"  FAIL {msg}")
            failures.append(msg)

    if failures:
        print("\nFAIL:")
        for f in failures:
            print(f"  {f}")
        print("\nA marker left in source is a negative test whose restore did not")
        print("run. The file imports cleanly and fails at runtime instead.")
        return 1
    print("\nPASS: no sabotage marker survives in the source the app runs.")
    return 0


if __name__ == "__main__":
    sys.exit(main())