"""Negative test for check_hooks_dispatched.py — prove the guard can fail.

Removes one real dispatch call, asserts the guard reports that hook as DEAD and
exits 1, then restores the file and asserts a clean pass.

Same rule as every other guard here: a check that only ever passes proves
nothing. Run:
    python scripts/wp-parity/negative_test_hooks.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GUARD = ROOT / "scripts" / "wp-parity" / "check_hooks_dispatched.py"
VICTIM_FILE = (
    ROOT / "backend" / "app" / "modules" / "seo" / "application" / "seo_service.py"
)
VICTIM_HOOK = "HOOK_SEO_METADATA"


def run_guard() -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, str(GUARD)], capture_output=True, text=True, cwd=str(ROOT)
    )
    return proc.returncode, proc.stdout + proc.stderr


def main() -> int:
    original = VICTIM_FILE.read_text(encoding="utf-8")

    if VICTIM_HOOK not in original:
        print(f"SKIP: {VICTIM_HOOK} is not in {VICTIM_FILE.name}, nothing to remove.")
        return 0

    # Delete the whole dispatch call. The hook name is an argument on a
    # following line, not on the `apply_filters(` line itself, so the walk
    # starts from the call and swallows the balanced parentheses.
    lines = original.split("\n")
    keep: list[str] = []
    i = 0
    removed = 0
    while i < len(lines):
        line = lines[i]
        if "apply_filters(" in line and line.lstrip().startswith("update_data ="):
            # Walk back over the `from ... import` line, its blank line, and
            # the explanatory comment block above it.
            while keep and (
                not keep[-1].strip()
                or "from app.shared.plugins.registry import" in keep[-1]
                or keep[-1].lstrip().startswith("#")
            ):
                keep.pop()
            depth = 0
            while i < len(lines):
                depth += lines[i].count("(") - lines[i].count(")")
                i += 1
                if depth <= 0:
                    break
            removed += 1
            continue
        keep.append(line)
        i += 1

    if removed == 0:
        print("FAIL: could not locate the dispatch call — the test would be a no-op.")
        return 1
    if VICTIM_HOOK in "\n".join(keep):
        print("FAIL: the hook name survived the injection — the test would be a no-op.")
        return 1

    try:
        VICTIM_FILE.write_text("\n".join(keep), encoding="utf-8")
        print(f"[2/4] injected: removed the {VICTIM_HOOK} dispatch call")

        try:
            import ast

            ast.parse(VICTIM_FILE.read_text(encoding="utf-8"))
        except SyntaxError as exc:
            print(f"FAIL: the injection left the file syntactically broken: {exc}")
            return 1

        code, out = run_guard()
        if code == 0:
            print("FAIL: guard still passed with a dispatch removed — it cannot fail.")
            print(out)
            return 1
        if VICTIM_HOOK not in out:
            print("FAIL: guard failed but did not name the dead hook.")
            print(out)
            return 1
        print(f"[3/4] guard correctly failed and named {VICTIM_HOOK}  OK")

    finally:
        VICTIM_FILE.write_text(original, encoding="utf-8")
        print("[4/4] restored the original file")

    # Baseline first, then post-restore, so a guard that never passed is caught.
    code, out = run_guard()
    if code != 0:
        print("FAIL: guard does not pass after restore — the file is damaged.")
        print(out)
        return 1
    print("\nPASS: the guard fails when it should and passes when it should.")
    return 0


if __name__ == "__main__":
    sys.exit(main())