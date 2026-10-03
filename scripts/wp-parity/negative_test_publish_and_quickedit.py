"""Negative test for check_publish_and_quickedit: prove the gate can fail.

A gate that has never failed cannot be told apart from one that cannot. This
runs the gate with a fixture that fails on purpose, and requires the gate to
report it. Exit 0 only when the gate is genuinely able to fail.

    python scripts/wp-parity/negative_test_publish_and_quickedit.py
"""

from __future__ import annotations

import sys as _sys
_sys.path.insert(0, __import__("os").path.dirname(__file__))
import console_safe  # noqa: F401  — makes stdout safe for non-ASCII

import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(HERE, "check_publish_and_quickedit.py")
SCRIPTS = ("pubdate_test.py", "quickedit_test.py")

# A fixture that exits non-zero and prints a numbered line, which is the exact
# shape the gate parses. A stub that merely printed nothing would let a gate
# with a broken parser pass, so the shape has to be real.
FAILING_FIXTURE = '''
import sys

print("1. injected failure: this check must never be reported as passing")
print("2. injected failure: second line, so the gate's parser is exercised too")
sys.exit(1)
'''


def main() -> int:
    if not os.path.isfile(TARGET):
        print(f"FAIL: gate not found at {TARGET}")
        return 1

    with tempfile.TemporaryDirectory() as tmp:
        # The gate resolves fixtures by walking up from its own file, so the
        # stub tree is built to match that shape: gate at <tmp>/repo/scripts/,
        # fixtures at <tmp>/repo/.p1-tests/. Pointing it anywhere else would make
        # the gate SKIP, and a SKIP looks exactly like a pass.
        repo = os.path.join(tmp, "repo")
        scripts_dir = os.path.join(repo, "scripts", "wp-parity")
        os.makedirs(scripts_dir)
        fake_fixtures = os.path.join(repo, ".p1-tests")
        os.makedirs(fake_fixtures)
        gate_copy = os.path.join(scripts_dir, "check_publish_and_quickedit.py")
        shutil.copyfile(TARGET, gate_copy)
        for name in SCRIPTS:
            with open(os.path.join(fake_fixtures, name), "w", encoding="utf-8") as fh:
                fh.write(FAILING_FIXTURE)

        proc = subprocess.run(
            [sys.executable, gate_copy],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
        )

    out = proc.stdout or ""
    if proc.returncode == 0:
        print("FAIL: the gate passed with failing fixtures. It reports success "
              "whatever the behaviour, so it is not a gate.")
        print(out.strip()[-400:])
        return 1
    if "FAIL" not in out:
        print("FAIL: the gate exited non-zero without saying what failed.")
        print(out.strip()[-400:])
        return 1
    print("PASS: the gate reported the injected failure, so it is a real gate.")
    return 0


if __name__ == "__main__":
    sys.exit(main())