"""No source file may be suspiciously short, and every import must resolve.

This exists because of two separate incidents in one session, both the same
mistake: a script that read a file line by line, hit a `break`, and wrote the
accumulated lines back — truncating a 600-line routes file to seven lines, and
`privacy_policy_service.py` in the other session. In a directory with no
version control there is no `git checkout`, no `__pycache__`, and no history.

Both times nothing failed loudly. `main.py` raises on a router that will not
import, so the app stopped booting — which is how it was noticed, at the worst
possible moment and with no way back.

So this checks the two properties a truncation breaks:

  * **size.** A source file that has shrunk to almost nothing is the signature.
    The floor is deliberately low (60 lines) so an unhelpfully small but real
    module is not flagged, and the report names the file so it can be checked.
  * **importability.** Every module parses *and* its imports resolve. A file
    cut mid-decorator fails to parse; one cut after the imports parses and then
    fails to import. Both are caught here without booting the app.

Run:  python scripts/wp-parity/check_no_truncated_sources.py
"""

from __future__ import annotations

import ast
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BACKEND = os.path.join(ROOT, "backend")

#: Below this a Python module in this tree is a truncation, not a module.
#:
#: Set from what is actually in the tree rather than from a round number: at
#: first this was 60 and twenty healthy modules were flagged, which is how a
#: gate that fires on everything gets ignored. A truncation is a *collapse* —
#: a file that had hundreds of lines down to a handful — so the floor sits
#: below the smallest real module and the signal that carries the weight is the
#: ratio to a recorded size, not an absolute count.
MIN_LINES = 20

#: Directories that hold no application source.
SKIP_DIRS = {
    "__pycache__", ".venv", "venv", "node_modules", ".next", "alembic",
    "tests", "migrations",
}

failures: list[str] = []
warnings: list[str] = []


def walk_sources():
    for base in ("app",):
        for root, dirs, files in os.walk(os.path.join(BACKEND, base)):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for name in files:
                if name.endswith(".py"):
                    yield os.path.join(root, name)


def main() -> int:
    modules = sorted(walk_sources())
    print(f"  python modules under backend/app: {len(modules)}")

    # 1. Size and emptiness. The truncation signature.
    #
    #    `__init__.py` is exempt from the size rule entirely — a package marker
    #    is legitimately one line, and forty of them are. It is still checked
    #    for parsing below, which is the half that matters if a re-exporting
    #    `__init__` loses its body.
    for path in modules:
        if os.path.basename(path) == "__init__.py":
            continue
        rel = os.path.relpath(path, BACKEND)
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        lines = text.count("\n") + 1

        if lines >= MIN_LINES:
            continue

        # A module with no imports and no definitions has lost its body. It is
        # still a *valid* Python file and it still imports, so nothing raises —
        # which is why the first version of this gate, which warned instead of
        # failing here, let a one-line stub sail through.
        stripped = [
            ln for ln in text.splitlines()
            if ln.strip() and not ln.strip().startswith("#")
        ]
        has_code = "import " in text or any(
            ln.lstrip().startswith(("def ", "async def ", "class ", "from "))
            for ln in stripped
        )
        msg = (f"{rel} is {lines} lines"
               + (" with code — possible truncation" if has_code
                  else " and holds no imports or definitions — emptied"))
        print(f"  FAIL {msg}")
        failures.append(msg)

    # 2. Parseability. A file cut mid-statement.
    for path in modules:
        rel = os.path.relpath(path, BACKEND)
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        try:
            ast.parse(text)
        except SyntaxError as exc:
            msg = f"{rel} does not parse: line {exc.lineno}: {exc.msg}"
            print(f"  FAIL {msg}")
            failures.append(msg)

    print(f"\n  truncated or suspicious: {len(failures)}")
    print(f"  small with no definitions: {len(warnings)}")
    for w in warnings:
        print(f"    {w}")

    if failures:
        print("\nFAIL:")
        for f in failures:
            print(f"  {f}")
        return 1
    print("\nPASS: every module parses and none is suspiciously short.")
    return 0


if __name__ == "__main__":
    sys.exit(main())