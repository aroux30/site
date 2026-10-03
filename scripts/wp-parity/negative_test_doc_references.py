"""Negative test for check_doc_references.py — prove the guard can actually fail.

The guard shipped after a peer session found a dead reference in a docstring
(`check_content_srcset.py`, a file that never existed, credited with the check
that actually protects the code). Its own first run then produced fifteen false
failures, because the codebase writes paths relative to several roots and
mentions siblings by bare name.

So all three are exercised here: a bare dead name, a path-shaped dead name, and
— the one that matters most — a *live* reference under each of the relative
forms the codebase uses, which must not be reported.

    python scripts/wp-parity/negative_test_doc_references.py
"""

from __future__ import annotations

import sys as _sys
_sys.path.insert(0, __import__("os").path.dirname(__file__))
import console_safe  # noqa: F401  — makes stdout safe for non-ASCII

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GUARD = ROOT / "scripts" / "wp-parity" / "check_doc_references.py"
# A file the guard already scans, so the injection is seen without touching
# anything whose contents matter.
TARGET = ROOT / "frontend" / "lib" / "content-responsive-images.ts"


def run() -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, str(GUARD)], capture_output=True, text=True, timeout=300
    )
    return proc.returncode, (proc.stdout + proc.stderr).strip()


# (label, text appended to the file, expect_fail)
# (label, text appended to the file, expect_fail). Kept as a flat list of
# tuples with no comments inside them: a comment placed between the elements of
# a tuple makes ast/CPython drop the leading element, and the case silently
# loses its label.
# (label, text appended to the file, expect_fail). Kept as a flat list with
# no comments between the elements of a tuple: a comment there makes CPython
# drop the leading element, so the case silently loses its label. The newline
# is built at runtime for the same reason - a literal \n inside the injected
# text is what we append, and writing it here as an escape has to survive being
# written through a patch.
NL = chr(10)  # a literal newline in a source string would break the escape
CASES = [
    ("a bare filename that does not exist", "See `totally_absent_guard.py`." + NL, True),
    ("a path-shaped reference that does not exist",
     "See `scripts/wp-parity/no_such_check.py`." + NL, True),
    ("a real file named as a sibling module would name it",
     "See `sanitize-html.ts`." + NL, False),
    ("the same real file named from the frontend root",
     "See `lib/sanitize-html.ts`." + NL, False),
    ("a real file under a module's own folder, by basename",
     "See `media.ts`." + NL, False),
    ("an elided path, which is shorthand rather than a claim",
     "See `.../domain/models.py`." + NL, False),
]


def main() -> int:
    original = TARGET.read_text(encoding="utf-8")

    def restore() -> None:
        TARGET.write_text(original, encoding="utf-8")

    try:
        code, out = run()
        if code != 0:
            print(
                "FAIL: the guard is red on the current tree, so a red result below "
                "would prove nothing.\n%s" % out[-600:]
            )
            return 2
        print("[0/%d] guard passes on the current tree" % (len(CASES) + 1))

        for i, (label, text, expect_fail) in enumerate(CASES, start=1):
            TARGET.write_text(original + "\n" + text, encoding="utf-8")
            try:
                code, out = run()
            finally:
                restore()

            if expect_fail and code == 0:
                print("FAIL: guard passed while %s — it cannot see this." % label)
                return 1
            if not expect_fail and code != 0:
                print("FAIL: guard reported a live reference while %s:\n%s" % (label, out[-400:]))
                return 1
            verdict = "fails on" if expect_fail else "stays quiet for"
            print("[%d/%d] correctly %s: %s" % (i, len(CASES) + 1, verdict, label))

        code, out = run()
        if code != 0:
            print("FAIL: guard still red after restore.\n%s" % out[-400:])
            return 1
        print("[%d/%d] guard is green again after restore" % (len(CASES) + 1, len(CASES) + 1))
    finally:
        restore()

    print("")
    print("PASS: the doc-reference guard catches dead names and does not cry wolf.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
