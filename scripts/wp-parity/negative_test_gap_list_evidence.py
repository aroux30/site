"""Negative test for check_gap_list_evidence's stale-pointer checks.

The gate's whole job is to notice that the document has drifted from the tree.
So the sabotage is the two ways it was failing to, both found live rather than
imagined:

  A. A pointer past the end of its file. The file exists, the line parses, and
     the claim it supported is about code that was deleted months ago. A gate
     that only asks "does this file exist" passes it — which is what the gate
     did.
  B. A pointer to a file that was renamed. The storefront robots metadata
     file became a route handler under a directory named after its old stem:
     the basename changed, so a name search finds nothing and the pointer is
     simply missing. Without a stem search the gate reported it as unreadable,
     which is a different and much less useful statement than "this file moved
     to there".

And the pair of cases that must *not* be flagged, because a check that fires on
everything tells an operator nothing:

  C. A path that does not exist anywhere is reported as unreadable, not as a
     move — otherwise the move report fills with typos.
  D. A file that still exists is never reported as moved, whatever shares its
     basename.

Run:  python scripts/wp-parity/negative_test_gap_list_evidence.py
"""

from __future__ import annotations

import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import console_safe  # noqa: F401  — makes stdout safe for non-ASCII

GATE = os.path.join(HERE, "check_gap_list_evidence.py")

failures: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {label}: {ok}")
    if not ok:
        failures.append(f"{label}: {detail}" if detail else label)


def load():
    spec = importlib.util.spec_from_file_location("gap_gate", GATE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    # The module has to import cleanly before anything else can be said about
    # it; a gate that will not import is not a gate.
    try:
        g = load()
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: the gate does not import: {exc}")
        return 1

    # A file to point at, and its real length.
    sample = "scripts/wp-parity/check_gap_list_evidence.py"
    with open(os.path.join(g.ROOT, sample), encoding="utf-8") as fh:
        length = sum(1 for _ in fh)

    # A: a line past the end of the file.
    check("a pointer past the end of its file is refused",
          g.resolve(sample, length + 50) is None)
    check("and a line inside it is not",
          g.resolve(sample, min(5, length)) is not None)

    # B: a file that was renamed under Next's convention.
    moved = g.moved_elsewhere("frontend/app/robots.ts")
    check("a renamed route is found at its new path",
          moved is not None and moved.endswith("robots.txt/route.ts"),
          str(moved))
    check("the old pointer resolves to nothing",
          g.resolve("frontend/app/robots.ts", None) is None)

    # C: a path that never existed is not a move.
    check("a path that exists nowhere is not reported as moved",
          g.moved_elsewhere("frontend/app/definitely-not-here.ts") is None)

    # D: a file that still exists is never a move, even with a sibling of the
    #    same name somewhere else.
    check("a file that still exists is never reported as moved",
          g.moved_elsewhere(sample) is None)

    # And the gate itself still passes on the real tree.
    import subprocess

    proc = subprocess.run(
        [sys.executable, GATE], capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=600,
    )
    check("the gate still passes on the real tree", proc.returncode == 0,
          (proc.stdout or "")[-200:])

    if failures:
        print("\nFAIL:")
        for f in failures:
            print(f"  {f}")
        return 1
    print("\nPASS: the gate sees a pointer past EOF and a renamed file, and "
          "does not cry wolf about a typo.")
    return 0


if __name__ == "__main__":
    sys.exit(main())