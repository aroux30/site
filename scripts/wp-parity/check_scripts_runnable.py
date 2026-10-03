"""Guard: the TypeScript checks under scripts/ must run from any directory.

A peer session found that `verify_content_srcset.mts` resolved its paths from
`process.cwd()`, so it passed from the repo root and failed from anywhere else
with a path like `frontend/backend/...` that does not exist. The check was
correct and still unusable, which is the worst combination: it looks like
coverage and is not.

So this runs every `.mts` check twice — once from the repo root, once from a
subdirectory — and fails if either invocation is not a clean pass. It also
asserts no check reads `process.cwd()` for a file path.

    python scripts/wp-parity/check_scripts_runnable.py
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts" / "wp-parity"
# Subdirectory to run from; a check that only works at the root fails here.
ELSEWHERE = ROOT / "frontend"

CWD_USAGE = re.compile(r"process\.cwd\(\)")


def uses_cwd_in_code(src: str) -> bool:
    """True when `process.cwd()` appears in code rather than in a comment.

    The first version matched the raw text, so it flagged the very comment
    explaining that cwd is *not* used — and reported two failures for files
    that were already correct. Comments are stripped first, which is what makes
    the check say something about the code.
    """
    code = "\n".join(line.split("//", 1)[0] for line in src.splitlines())
    # Block comments, in case one is added later.
    code = re.sub(r"/\*.*?\*/", "", code, flags=re.S)
    return CWD_USAGE.search(code) is not None


def checks() -> list[Path]:
    # Everything under *.mts, including the negative tests: they inject
    # snippets into real files and are exactly the scripts a line-ending
    # mismatch breaks.
    return sorted(p for p in SCRIPTS.glob("*.mts"))


def executables() -> list[Path]:
    """The checks this guard runs, as opposed to the tests-of-checks.

    A negative test runs other checks by mutating files first; running one from
    inside another guard would have it fight with whatever else is mid-run.
    """
    return [p for p in checks() if not p.name.startswith("negative_test_")]


def run(script: Path, cwd: Path) -> tuple[int, str]:
    proc = subprocess.run(
        ["npx", "tsx", str(script)],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=600,
        shell=True,  # npx is npx.cmd on Windows
    )
    return proc.returncode, ((proc.stdout or "") + (proc.stderr or "")).strip()


def normalises_line_endings(src: str) -> bool:
    """Whether the script handles CRLF before comparing text.

    A plain substring test on the source, deliberately. The escapes that matter
    (`\\r\\n`, `\\r?\\n`, `split("\\r")`) are present verbatim in the file, and an
    earlier regex version tried to re-interpret them as Python patterns, so it
    never matched the thing it was looking for.

    Matching the marker anywhere is deliberately lenient: the point is to catch
    a test that has lost its normalisation *entirely*, not to police how it is
    spelled.
    """
    code = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    code = "\n".join(line.split("//", 1)[0] for line in code.splitlines())
    return any(marker in code for marker in (r"\r\n", r"\r?\n", r'split("\r'))


def main() -> int:
    failures: list[str] = []
    found = executables()
    if not found:
        print("FAIL: no .mts checks found under scripts/wp-parity — nothing is verified.")
        return 1

    # The static rules apply to every .mts, including the negative tests — which
    # are the ones that break on a line-ending mismatch. An earlier version ran
    # them over `executables()` only, so the rule was unreachable: the tests it
    # was written for were filtered out before it ever saw them.
    for script in checks():
        rel = script.relative_to(ROOT).as_posix()
        src = script.read_text(encoding="utf-8")
        if uses_cwd_in_code(src):
            failures.append(
                f"{rel} resolves paths from process.cwd(), so it only works when "
                f"run from the repo root. Derive them from import.meta.url instead."
            )
        if script.name.startswith("negative_test_") and not normalises_line_endings(src):
            failures.append(
                f"{rel} compares raw text against a snippet it injects, and does "
                f"not normalise line endings. On a CRLF checkout no injection "
                f"will ever match, and the test fails as if its snippet were stale."
            )

    # Prove the line-ending rule can fail, before it is trusted to pass. Done
    # here rather than in a separate test because an earlier standalone helper
    # printed "removed" while changing nothing — its replacement string did not
    # match a CRLF file — and a rule that cannot be seen to fail is not one
    # anybody can rely on.
    if "--self-test" in sys.argv:
        if normalises_line_endings("const x = (s) => s;"):
            print("FAIL: the line-ending rule fires on text that does no such thing.")
            return 1
        marker = chr(92) + "r" + chr(92) + "n"
        if not normalises_line_endings("const n = (s) => s.replace(/" + marker + "/g);"):
            print("FAIL: the line-ending rule misses a script that does normalise.")
            return 1
        print("PASS: the line-ending rule fires on a raw compare and stays quiet on a real one.")
        return 0

    for script in found:
        rel = script.relative_to(ROOT).as_posix()
        for cwd, label in ((ROOT, "repo root"), (ELSEWHERE, "frontend/")):
            code, out = run(script, cwd)
            if code != 0:
                failures.append(
                    f"{rel} exits {code} when run from {label}:\n"
                    + "\n".join(out.splitlines()[-6:])
                )

    for f in failures:
        print("FAIL: %s" % f)
    if failures:
        print("")
        print("%d problem(s)." % len(failures))
        return 1

    print(
        "PASS: %d TypeScript check(s) pass from the repo root and from a "
        "subdirectory, and none resolve paths from the cwd." % len(found)
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
